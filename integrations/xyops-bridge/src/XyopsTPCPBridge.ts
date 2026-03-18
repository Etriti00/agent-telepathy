/**
 * XyopsTPCPBridge — connects xyops job scheduler to TPCP multi-agent network.
 *
 * Role in the agency:
 *  - Aura/Paperclip send TASK_REQUEST to 'xyops-agent' -> xyops jobs are created
 *  - xyops webhooks on job completion -> TPCP STATE_SYNC back to requester
 *  - Periodic health checks -> TPCP BROADCAST alert if any service goes down
 */

import EventEmitter from "events";
import express, { Request, Response } from "express";
import http from "http";

import { config } from "./config.js";
import {
  AgencyHealthReport,
  CreateAlertParams,
  JobStatus,
  JobStatusUpdate,
  ScheduleJobRequest,
  XyopsInboundMessage,
  XyopsWebhookPayload,
} from "./schemas.js";

// ---------------------------------------------------------------------------
// Optional TPCP — graceful simulation mode if tpcp-sdk not installed
// ---------------------------------------------------------------------------
let TPCPNode: any = null;
let TPCP_AVAILABLE = false;

async function tryLoadTpcp(): Promise<boolean> {
  try {
    const m = await import("tpcp-sdk");
    TPCPNode = m.RelayTPCPNode ?? m.TPCPNode;
    return true;
  } catch {
    console.warn("[XyopsBridge] tpcp-sdk not found — simulation mode active.");
    return false;
  }
}

interface PendingJob {
  jobId: string;
  senderAgentId: string;
  description?: string;
  createdAt: number;
}

interface ServiceHealth {
  name: string;
  url: string;
  status: "healthy" | "degraded" | "down";
  lastCheckedAt: number;
}

// ---------------------------------------------------------------------------
// Bridge class
// ---------------------------------------------------------------------------
export class XyopsTPCPBridge extends EventEmitter {
  private node: any = null;
  private server: http.Server | null = null;
  private readonly app = express();
  private readonly pendingJobs = new Map<string, PendingJob>();
  private readonly serviceHealth = new Map<string, ServiceHealth>();
  private cleanupTimer: NodeJS.Timeout | null = null;

  constructor() {
    super();
    this.app.use(express.json());
  }

  // -----------------------------------------------------------------------
  // Lifecycle
  // -----------------------------------------------------------------------

  async start(): Promise<void> {
    TPCP_AVAILABLE = await tryLoadTpcp();
    if (TPCP_AVAILABLE) await this._initTpcp();
    this._startWebhookServer();
    this._startHealthMonitor();
    this._scheduleCleanup();
    await this._registerMonitoring();
    console.log("[XyopsBridge] Started" + (TPCP_AVAILABLE ? "" : " (simulation mode)"));
  }

  async stop(): Promise<void> {
    if (this.cleanupTimer) clearInterval(this.cleanupTimer);
    try { await this.node?.stopListening?.(); } catch { /* ignore */ }
    await new Promise<void>((r) => (this.server ? this.server.close(() => r()) : r()));
    console.log("[XyopsBridge] Stopped");
  }

  // -----------------------------------------------------------------------
  // TPCP init
  // -----------------------------------------------------------------------

  private async _initTpcp(): Promise<void> {
    this.node = new TPCPNode(
      {
        agent_id: "xyops-agent",
        framework: "xyops",
        public_key: "",
        capabilities: ["job_scheduling", "monitoring", "automation"],
        modality: ["text"],
      },
      config.tpcp.relayUrl,
    );
    await this.node.startListening();

    const deadline = Date.now() + 10_000;
    while (!this.node["_adnsRegistered"] && Date.now() < deadline)
      await new Promise((r) => setTimeout(r, 100));
    if (!this.node["_adnsRegistered"])
      throw new Error("[XyopsBridge] ADNS registration timeout — relay unreachable?");

    this.node.on("message", (env: any) =>
      this._handleInboundTpcp(env).catch((e: unknown) =>
        console.error("[XyopsBridge] TPCP handler error:", e)
      )
    );
    console.log(`[XyopsBridge] TPCP registered as 'xyops-agent' at ${config.tpcp.relayUrl}`);
  }

  // -----------------------------------------------------------------------
  // Inbound TPCP messages
  // -----------------------------------------------------------------------

  private async _handleInboundTpcp(envelope: any): Promise<void> {
    const raw = envelope?.payload;
    if (!raw) return;

    const parsed = XyopsInboundMessage.safeParse(
      typeof raw === "string" ? JSON.parse(raw) : raw
    );
    if (!parsed.success) {
      console.warn("[XyopsBridge] Unknown TPCP message:", raw);
      return;
    }

    const msg = parsed.data;
    const sender: string = envelope?.header?.sender_id ?? "unknown";

    if (msg.type === "schedule_job") {
      await this._handleScheduleJob(msg, sender);
    } else if (msg.type === "create_alert") {
      await this._createXyopsAlert({
        title: msg.title,
        expression: msg.expression,
        message: msg.message,
      });
    } else if (msg.type === "get_job_status") {
      const job = await this._getXyopsJob(msg.xyops_job_id);
      if (job) {
        await this._sendTpcpUpdate(sender, {
          type: "job_status_update",
          job_id: msg.xyops_job_id,
          xyops_job_id: msg.xyops_job_id,
          status: this._codeToStatus(job.code ?? -1),
          progress_pct: Math.round((job.progress ?? 0) * 100),
          description: job.description,
          updated_at: new Date().toISOString(),
        } satisfies JobStatusUpdate);
      }
    }
  }

  // -----------------------------------------------------------------------
  // Job scheduling
  // -----------------------------------------------------------------------

  private async _handleScheduleJob(
    msg: ScheduleJobRequest,
    senderAgentId: string,
  ): Promise<void> {
    console.log(
      `[XyopsBridge] Scheduling '${msg.event}' for ${senderAgentId} (corr: ${msg.job_id})`
    );
    const xyopsJobId = await this._createXyopsJob(msg.event, {
      ...(msg.params ?? {}),
      tpcp_job_id: msg.job_id,
      tpcp_sender: senderAgentId,
    });
    if (!xyopsJobId) {
      console.error("[XyopsBridge] Failed to create xyops job");
      return;
    }
    if (msg.notify_sender) {
      this.pendingJobs.set(xyopsJobId, {
        jobId: msg.job_id,
        senderAgentId,
        description: msg.description,
        createdAt: Date.now(),
      });
    }
    console.log(`[XyopsBridge] xyops job ${xyopsJobId} created`);
  }

  // -----------------------------------------------------------------------
  // xyops REST API calls
  // -----------------------------------------------------------------------

  private async _createXyopsJob(
    event: string,
    params: Record<string, unknown>,
  ): Promise<string | null> {
    const url = new URL(`${config.xyops.apiUrl}/api/app/create_job/v1`);
    url.searchParams.set("event", event);
    for (const [k, v] of Object.entries(params))
      if (v != null) url.searchParams.set(k, String(v));
    try {
      const res = await fetch(url.toString(), {
        headers: { "X-API-Key": config.xyops.apiKey },
      });
      if (!res.ok) {
        console.error(`[XyopsBridge] create_job ${res.status}: ${await res.text()}`);
        return null;
      }
      const data = (await res.json()) as any;
      return data?.job?.id ?? data?.id ?? null;
    } catch (err) {
      console.error("[XyopsBridge] create_job error:", err);
      return null;
    }
  }

  private async _getXyopsJob(jobId: string): Promise<any | null> {
    try {
      const res = await fetch(
        `${config.xyops.apiUrl}/api/app/get_jobs/v1?id=${encodeURIComponent(jobId)}`,
        { headers: { "X-API-Key": config.xyops.apiKey } },
      );
      const data = (await res.json()) as any;
      return data?.jobs?.[0] ?? null;
    } catch {
      return null;
    }
  }

  private async _createXyopsAlert(params: CreateAlertParams): Promise<void> {
    try {
      const res = await fetch(`${config.xyops.apiUrl}/api/app/create_alert/v1`, {
        method: "POST",
        headers: {
          "X-API-Key": config.xyops.apiKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(params),
      });
      if (!res.ok) console.error(`[XyopsBridge] create_alert ${res.status}`);
    } catch (err) {
      console.error("[XyopsBridge] create_alert error:", err);
    }
  }

  // -----------------------------------------------------------------------
  // Webhook server (xyops calls this endpoint on job events)
  // -----------------------------------------------------------------------

  private _startWebhookServer(): void {
    this.app.post(config.xyops.webhookPath, (req: Request, res: Response) => {
      this._handleXyopsWebhook(req.body).catch((e) =>
        console.error("[XyopsBridge] Webhook error:", e)
      );
      res.sendStatus(200);
    });

    this.app.get("/health", (_req, res) =>
      res.json({ status: "ok", service: "xyops-tpcp-bridge" })
    );

    this.server = this.app.listen(config.xyops.webhookPort, () =>
      console.log(
        `[XyopsBridge] Webhook :${config.xyops.webhookPort}${config.xyops.webhookPath}`
      )
    );
  }

  private async _handleXyopsWebhook(body: unknown): Promise<void> {
    const parsed = XyopsWebhookPayload.safeParse(body);
    if (!parsed.success) {
      console.warn("[XyopsBridge] Invalid webhook payload");
      return;
    }
    const payload = parsed.data;
    const pending = this.pendingJobs.get(payload.id);
    const status = this._codeToStatus(payload.code);
    console.log(`[XyopsBridge] xyops job ${payload.id} -> ${status}`);
    this.emit("job:complete", payload);

    if (pending && TPCP_AVAILABLE) {
      await this._sendTpcpUpdate(pending.senderAgentId, {
        type: "job_status_update",
        job_id: pending.jobId,
        xyops_job_id: payload.id,
        status,
        progress_pct: Math.round(
          (payload.progress ?? (status === "success" ? 1 : 0)) * 100
        ),
        description: payload.description ?? pending.description,
        perf: payload.perf,
        updated_at: new Date().toISOString(),
      } satisfies JobStatusUpdate);
      this.pendingJobs.delete(payload.id);
    }
  }

  // -----------------------------------------------------------------------
  // TPCP outbound helpers
  // -----------------------------------------------------------------------

  private async _sendTpcpUpdate(
    targetAgentId: string,
    data: JobStatusUpdate | AgencyHealthReport,
  ): Promise<void> {
    if (!TPCP_AVAILABLE || !this.node) {
      console.log(`[XyopsBridge][SIM] -> ${targetAgentId}:`, JSON.stringify(data));
      return;
    }
    const ws = this.node["_adnsWs"];
    if (!ws || ws.readyState !== 1) {
      console.warn("[XyopsBridge] Relay not open — cannot send update");
      return;
    }
    ws.send(
      JSON.stringify({
        header: {
          message_id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          sender_id: "xyops-agent",
          receiver_id: targetAgentId,
          intent: "STATE_SYNC",
          ttl: 30,
          protocol_version: "0.4",
        },
        payload: data,
        signature: this.node.identityManager?.signPayload(data) ?? "",
      })
    );
  }

  // -----------------------------------------------------------------------
  // Health monitoring
  // -----------------------------------------------------------------------

  private _startHealthMonitor(): void {
    const check = async () => {
      const services: Record<string, "healthy" | "degraded" | "down"> = {};
      for (const [name, url] of Object.entries(config.healthChecks)) {
        const status = await this._checkServiceHealth(url as string);
        services[name] = status;
        this.serviceHealth.set(name, {
          name,
          url: url as string,
          status,
          lastCheckedAt: Date.now(),
        });
      }
      const report: AgencyHealthReport = {
        type: "agency_health",
        timestamp: new Date().toISOString(),
        services,
        active_jobs: 0,
        failed_jobs_24h: 0,
      };
      if (Object.values(services).some((s) => s === "down")) {
        console.warn("[XyopsBridge] Service(s) down — broadcasting TPCP health alert");
        await this._sendTpcpUpdate("00000000-0000-0000-0000-000000000000", report);
      }
      this.emit("health:report", report);
    };

    check().catch(console.error);
    setInterval(() => check().catch(console.error), 5 * 60 * 1000);
  }

  private async _checkServiceHealth(
    url: string,
  ): Promise<"healthy" | "degraded" | "down"> {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 5_000);
      const res = await fetch(url, { signal: ctrl.signal });
      clearTimeout(t);
      return res.ok ? "healthy" : res.status < 500 ? "degraded" : "down";
    } catch {
      return "down";
    }
  }

  private async _registerMonitoring(): Promise<void> {
    const webhookUrl = process.env.XYOPS_BRIDGE_PUBLIC_URL
      ? `${process.env.XYOPS_BRIDGE_PUBLIC_URL}${config.xyops.webhookPath}`
      : `http://localhost:${config.xyops.webhookPort}${config.xyops.webhookPath}`;

    await this._createXyopsAlert({
      title: "TPCP Agency Health Alert",
      expression: "[job.total_errors] > 0",
      message: "Agency service failure. Check TPCP relay, Aura, and Paperclip.",
      notify_web_hooks: [webhookUrl],
    });
    console.log(`[XyopsBridge] Monitoring registered. Webhook: ${webhookUrl}`);
  }

  // -----------------------------------------------------------------------
  // Utilities
  // -----------------------------------------------------------------------

  private _codeToStatus(code: number): JobStatus {
    if (code === 0) return "running";
    if (code > 0) return "success";
    return "error";
  }

  private _scheduleCleanup(): void {
    this.cleanupTimer = setInterval(() => {
      const cutoff = Date.now() - config.bridge.jobTtlMs;
      for (const [id, job] of this.pendingJobs)
        if (job.createdAt < cutoff) this.pendingJobs.delete(id);
    }, 60_000);
  }

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /** Programmatically schedule an xyops job (bypasses TPCP) */
  async scheduleJob(
    event: string,
    params: Record<string, unknown> = {},
    notifyAgent?: string,
  ): Promise<string | null> {
    const correlationId = crypto.randomUUID();
    const xyopsJobId = await this._createXyopsJob(event, {
      ...params,
      tpcp_job_id: correlationId,
    });
    if (xyopsJobId && notifyAgent) {
      this.pendingJobs.set(xyopsJobId, {
        jobId: correlationId,
        senderAgentId: notifyAgent,
        createdAt: Date.now(),
      });
    }
    return xyopsJobId;
  }

  getHealthReport(): Record<string, ServiceHealth> {
    return Object.fromEntries(this.serviceHealth);
  }
}
