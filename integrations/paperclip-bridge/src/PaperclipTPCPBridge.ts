/**
 * PaperclipTPCPBridge
 * ===================
 * The core bridge that connects Paperclip (service delivery orchestrator)
 * to the TPCP network, enabling real-time communication with Aura-App.
 *
 * Responsibilities:
 * 1. Register Paperclip as a TPCP node
 * 2. Receive ProjectRequest messages from Aura via TPCP
 * 3. Create tickets in Paperclip via REST API
 * 4. Poll Paperclip for ticket status changes
 * 5. Send ProjectStatusUpdate messages back to Aura via TPCP
 * 6. Maintain shared CRDT state between both systems
 */

import axios, { AxiosInstance } from "axios";
import stableStringify from "fast-json-stable-stringify";
import { config } from "./config.js";
import {
  PaperclipCreateTicketRequest,
  PaperclipTicket,
  ProjectRequest,
  ProjectStatus,
  ProjectStatusUpdate,
  ServiceType,
} from "./schemas.js";

// ---------------------------------------------------------------------------
// TPCP TypeScript SDK — loaded from the tpcp-ts package in the monorepo
// ---------------------------------------------------------------------------
let TPCPNode: any;
let Intent: any;
let AgentIdentity: any;
let TPCP_AVAILABLE = false;

try {
  // Try to load the local tpcp-ts build
  const tpcpModule = await import("tpcp-sdk");
  TPCPNode = tpcpModule.RelayTPCPNode ?? tpcpModule.TPCPNode;
  Intent = tpcpModule.Intent;
  AgentIdentity = null; // not a class in tpcp-sdk, identity is inline
  TPCP_AVAILABLE = true;
} catch {
  console.warn(
    "[PaperclipBridge] tpcp-ts not found — bridge will run in simulation mode.\n" +
      "Build it: cd ../../tpcp-ts && npm install && npm run build"
  );
}

// ---------------------------------------------------------------------------
// Paperclip API role/priority mappings
// ---------------------------------------------------------------------------

const SERVICE_TO_ROLE: Record<ServiceType, string> = {
  website_landing: "Frontend Developer",
  website_ecommerce: "Full-Stack Developer",
  website_portfolio: "Frontend Developer",
  webapp_saas: "Full-Stack Developer",
  webapp_internal_tool: "Full-Stack Developer",
  webapp_dashboard: "Full-Stack Developer",
  automation_email: "Automation Engineer",
  automation_crm: "Automation Engineer",
  automation_data_pipeline: "Data Engineer",
  automation_scraper: "Automation Engineer",
  automation_reporting: "Automation Engineer",
};

const PRIORITY_MAP: Record<string, PaperclipCreateTicketRequest["priority"]> =
  {
    low: "low",
    normal: "medium",
    high: "high",
    urgent: "urgent",
  };

// ---------------------------------------------------------------------------
// Ticket status → project status mapping
// ---------------------------------------------------------------------------

const TICKET_TO_PROJECT_STATUS: Record<string, ProjectStatus> = {
  open: "received",
  in_progress: "in_progress",
  in_review: "review",
  done: "delivered",
  closed: "completed",
  cancelled: "cancelled",
};

// ---------------------------------------------------------------------------
// Main bridge class
// ---------------------------------------------------------------------------

export class PaperclipTPCPBridge {
  private node: any = null;
  private auraAgentId: string | null = null;
  private paperclipApi: AxiosInstance;
  private simulationMode: boolean;

  /** Maps request_id → Paperclip ticket_id */
  private requestToTicket = new Map<string, string>();
  /** Maps Paperclip ticket_id → last known status */
  private ticketStatusCache = new Map<string, string>();
  /** Maps Paperclip ticket_id → original ProjectRequest */
  private ticketToRequest = new Map<string, ProjectRequest>();

  private pollInterval: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.simulationMode = !TPCP_AVAILABLE;

    this.paperclipApi = axios.create({
      baseURL: config.paperclip.apiUrl,
      headers: {
        Authorization: `Bearer ${config.paperclip.apiKey}`,
        "Content-Type": "application/json",
      },
      timeout: 30_000,
    });
  }

  // --------------------------------------------------------------------------
  // Lifecycle
  // --------------------------------------------------------------------------

  async start(): Promise<void> {
    if (!this.simulationMode) {
      await this._startTPCPNode();
    }
    this._startPolling();
    console.log("[PaperclipBridge] Started");
  }

  async stop(): Promise<void> {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
    if (this.node) {
      await this.node.stop?.();
    }
    console.log("[PaperclipBridge] Stopped");
  }

  // --------------------------------------------------------------------------
  // TPCP node setup
  // --------------------------------------------------------------------------

  private async _startTPCPNode(): Promise<void> {
    const identity: typeof AgentIdentity = {
      agent_id: crypto.randomUUID(),
      framework: "Paperclip",
      capabilities: [
        "website_building",
        "webapp_development",
        "automation",
        "project_management",
        "agent_orchestration",
      ],
      public_key: "",
    };

    this.node = new TPCPNode(
      identity,
      config.tpcp.relayUrl
    );

    // Register handlers
    this.node.on("message", (envelope: any) => this._handleMessage(envelope));
    this.node.on("onStateSync", (state: any) =>
      this._handleStateSync(state)
    );

    await this.node.startListening();

    console.log(
      `[PaperclipBridge] TPCP node started on port ${config.tpcp.port}`
    );
  }

  // --------------------------------------------------------------------------
  // Incoming TPCP message handlers
  // --------------------------------------------------------------------------

  private async _handleMessage(envelope: any): Promise<void> {
    try {
      const intent = envelope.header?.intent ?? envelope.intent;

      if (intent === "TASK_REQUEST" || intent === 4) {
        await this._handleTaskRequest(envelope);
      } else if (intent === "HANDSHAKE" || intent === 0) {
        await this._handleHandshake(envelope);
      } else if (intent === "CRITIQUE" || intent === 5) {
        await this._handleCritique(envelope);
      }
    } catch (err) {
      console.error("[PaperclipBridge] Error handling message:", err);
    }
  }

  private async _handleHandshake(envelope: any): Promise<void> {
    const senderId =
      envelope.header?.sender_id ?? envelope.sender_id;
    if (senderId && !this.auraAgentId) {
      this.auraAgentId = senderId;
      console.log(`[PaperclipBridge] Aura-App registered: ${this.auraAgentId}`);
    }
  }

  private async _handleTaskRequest(envelope: any): Promise<void> {
    const payload = envelope.payload;
    const raw: string =
      typeof payload === "string"
        ? payload
        : payload?.content ?? stableStringify(payload);

    let data: unknown;
    try {
      data = JSON.parse(raw);
    } catch {
      data = payload;
    }

    const parseResult = ProjectRequest.safeParse(data);
    if (!parseResult.success) {
      console.error(
        "[PaperclipBridge] Invalid ProjectRequest:",
        parseResult.error.flatten()
      );
      return;
    }

    const request = parseResult.data;
    console.log(
      `[PaperclipBridge] New project request: ${request.company_name} → ${request.service_type}`
    );

    // Acknowledge receipt
    await this._sendStatusUpdate({
      request_id: request.request_id,
      lead_id: request.lead_id,
      status: "received",
      message: `Project received. Creating Paperclip ticket for ${request.service_type}...`,
      progress_pct: 5,
    });

    // Create ticket in Paperclip
    await this._createPaperclipTicket(request);
  }

  private async _handleCritique(envelope: any): Promise<void> {
    const payload = envelope.payload;
    const raw =
      typeof payload === "string"
        ? payload
        : payload?.content ?? stableStringify(payload);

    let data: any;
    try {
      data = JSON.parse(raw);
    } catch {
      return;
    }

    if (data.type === "revision_request") {
      const ticketId = this.requestToTicket.get(data.request_id);
      if (!ticketId) return;

      console.log(
        `[PaperclipBridge] Revision requested for ticket ${ticketId}: ${data.feedback}`
      );
      await this._addTicketComment(
        ticketId,
        `Revision requested by Aura-App:\n\n${data.feedback}`
      );
    }
  }

  private async _handleStateSync(state: any): Promise<void> {
    // Merge any project context updates from Aura into local awareness
    for (const [key, entry] of Object.entries(state)) {
      if (key.startsWith("project:") && key.endsWith(":request")) {
        const value = (entry as any)?.value ?? entry;
        if (value) {
          const req = ProjectRequest.safeParse(value);
          if (req.success) {
            const ticketId = this.requestToTicket.get(req.data.request_id);
            if (ticketId) {
              this.ticketToRequest.set(ticketId, req.data);
            }
          }
        }
      }
    }
  }

  // --------------------------------------------------------------------------
  // Paperclip ticket management
  // --------------------------------------------------------------------------

  private async _createPaperclipTicket(request: ProjectRequest): Promise<void> {
    const role = SERVICE_TO_ROLE[request.service_type];
    const priority = PRIORITY_MAP[request.priority] ?? "medium";

    const description = this._buildTicketDescription(request);

    const ticketData: PaperclipCreateTicketRequest = {
      title: `[${request.service_type.toUpperCase()}] ${request.company_name}`,
      description,
      companyId: config.paperclip.companyId,
      goalId: config.paperclip.goalId,
      priority,
      metadata: {
        aura_request_id: request.request_id,
        aura_lead_id: request.lead_id,
        service_type: request.service_type,
        budget_usd: request.budget_usd,
        contact_email: request.contact_email,
        contact_name: request.contact_name,
        role_needed: role,
        ...request.metadata,
      },
    };

    if (this.simulationMode) {
      const simulatedTicketId = `sim_${Date.now()}`;
      console.log(
        `[PaperclipBridge] [SIM] Would create Paperclip ticket: ${ticketData.title} → ${simulatedTicketId}`
      );
      this.requestToTicket.set(request.request_id, simulatedTicketId);
      this.ticketToRequest.set(simulatedTicketId, request);
      await this._sendStatusUpdate({
        request_id: request.request_id,
        lead_id: request.lead_id,
        paperclip_ticket_id: simulatedTicketId,
        status: "scoping",
        message: `[Simulation] Ticket created. ${role} agent assigned.`,
        progress_pct: 10,
      });
      return;
    }

    try {
      const response = await this.paperclipApi.post<PaperclipTicket>(
        "/api/tickets",
        ticketData
      );
      const ticket = response.data;

      this.requestToTicket.set(request.request_id, ticket.id);
      this.ticketToRequest.set(ticket.id, request);
      this.ticketStatusCache.set(ticket.id, "open");

      console.log(
        `[PaperclipBridge] Ticket created: ${ticket.id} for ${request.company_name}`
      );

      // Write to shared CRDT so Aura knows the ticket ID
      if (this.node) {
        this.node.sharedMemory?.set(
          `project:${request.request_id}:ticket_id`,
          ticket.id
        );
      }

      await this._sendStatusUpdate({
        request_id: request.request_id,
        lead_id: request.lead_id,
        paperclip_ticket_id: ticket.id,
        status: "scoping",
        message: `Paperclip ticket created. ${role} agent will pick this up on next heartbeat.`,
        progress_pct: 10,
      });
    } catch (err: any) {
      console.error(
        "[PaperclipBridge] Failed to create Paperclip ticket:",
        err.message
      );
      await this._sendStatusUpdate({
        request_id: request.request_id,
        lead_id: request.lead_id,
        status: "cancelled",
        message: `Failed to create Paperclip ticket: ${err.message}`,
        progress_pct: 0,
      });
    }
  }

  private _buildTicketDescription(request: ProjectRequest): string {
    const lines: string[] = [
      `## Project: ${request.service_type.replace(/_/g, " ").toUpperCase()}`,
      "",
      `**Client:** ${request.company_name}`,
      `**Contact:** ${request.contact_name ?? "N/A"} (${request.contact_email})`,
      `**Budget:** $${request.budget_usd.toLocaleString()}`,
      `**Priority:** ${request.priority}`,
    ];

    if (request.deadline_iso) {
      lines.push(
        `**Deadline:** ${new Date(request.deadline_iso).toLocaleDateString()}`
      );
    }

    lines.push("", "### Requirements", request.requirements);

    if (request.research_notes) {
      lines.push(
        "",
        "### Research Notes (from Aura-App)",
        request.research_notes
      );
    }

    if (request.existing_website) {
      lines.push("", `**Existing site:** ${request.existing_website}`);
    }

    if (request.industry || request.company_size) {
      lines.push(
        "",
        `**Industry:** ${request.industry ?? "N/A"} | **Size:** ${request.company_size ?? "N/A"}`
      );
    }

    lines.push(
      "",
      "---",
      "_This ticket was automatically created by the Aura-App → Paperclip integration._",
      `_Aura Request ID: ${request.request_id}_`
    );

    return lines.join("\n");
  }

  private async _addTicketComment(
    ticketId: string,
    comment: string
  ): Promise<void> {
    if (this.simulationMode) {
      console.log(`[PaperclipBridge] [SIM] Comment on ${ticketId}: ${comment}`);
      return;
    }
    try {
      await this.paperclipApi.post(`/api/tickets/${ticketId}/comments`, {
        content: comment,
      });
    } catch (err: any) {
      console.error(
        `[PaperclipBridge] Failed to add comment to ticket ${ticketId}:`,
        err.message
      );
    }
  }

  // --------------------------------------------------------------------------
  // Status polling
  // --------------------------------------------------------------------------

  private _startPolling(): void {
    this.pollInterval = setInterval(
      () => this._pollTicketStatuses(),
      config.bridge.pollIntervalMs
    );
  }

  private async _pollTicketStatuses(): Promise<void> {
    if (this.requestToTicket.size === 0) return;

    for (const [requestId, ticketId] of this.requestToTicket.entries()) {
      const request = this.ticketToRequest.get(ticketId);
      if (!request) continue;

      const lastStatus = this.ticketStatusCache.get(ticketId);

      if (lastStatus === "closed" || lastStatus === "completed") {
        continue; // No need to poll finished tickets
      }

      if (this.simulationMode) continue;

      try {
        const resp = await this.paperclipApi.get<PaperclipTicket>(
          `/api/tickets/${ticketId}`
        );
        const ticket = resp.data;
        const newStatus = ticket.status;

        if (newStatus !== lastStatus) {
          this.ticketStatusCache.set(ticketId, newStatus);
          const projectStatus =
            TICKET_TO_PROJECT_STATUS[newStatus] ?? "in_progress";

          const update: Omit<ProjectStatusUpdate, "updated_at"> = {
            request_id: requestId,
            lead_id: request.lead_id,
            paperclip_ticket_id: ticketId,
            status: projectStatus,
            message: this._statusMessage(projectStatus, request.company_name),
            progress_pct: this._statusToProgress(projectStatus),
          };

          // If ticket is delivered, try to get the deliverable URL from metadata
          if (
            projectStatus === "delivered" ||
            projectStatus === "completed"
          ) {
            const deliverableUrl = (ticket.metadata as any)?.deliverable_url;
            if (deliverableUrl) {
              (update as any).deliverable_url = deliverableUrl;
              (update as any).deliverable_type =
                (ticket.metadata as any)?.deliverable_type ?? "other";
            }
            const agentNotes = (ticket.metadata as any)?.agent_notes;
            if (agentNotes) {
              update.agent_notes = agentNotes;
            }
          }

          await this._sendStatusUpdate(update);
        }
      } catch (err: any) {
        console.error(
          `[PaperclipBridge] Error polling ticket ${ticketId}:`,
          err.message
        );
      }
    }
  }

  private _statusMessage(status: ProjectStatus, company: string): string {
    const messages: Record<ProjectStatus, string> = {
      received: `Project request received for ${company}.`,
      scoping: `Scoping requirements for ${company}'s project.`,
      in_progress: `Agents are actively working on ${company}'s project.`,
      review: `${company}'s project is in review.`,
      delivered: `${company}'s project is ready for delivery!`,
      revision_requested: `Revision in progress for ${company}'s project.`,
      completed: `${company}'s project is complete. 🎉`,
      cancelled: `${company}'s project was cancelled.`,
    };
    return messages[status] ?? `Status: ${status}`;
  }

  private _statusToProgress(status: ProjectStatus): number {
    const map: Record<ProjectStatus, number> = {
      received: 5,
      scoping: 10,
      in_progress: 50,
      review: 80,
      delivered: 95,
      revision_requested: 70,
      completed: 100,
      cancelled: 0,
    };
    return map[status] ?? 0;
  }

  // --------------------------------------------------------------------------
  // Sending updates back to Aura
  // --------------------------------------------------------------------------

  private async _sendStatusUpdate(
    update: Omit<ProjectStatusUpdate, "updated_at">
  ): Promise<void> {
    const fullUpdate: ProjectStatusUpdate = {
      ...update,
      updated_at: new Date().toISOString(),
    } as ProjectStatusUpdate;

    console.log(
      `[PaperclipBridge] Status update → Aura: ${fullUpdate.request_id} [${fullUpdate.status}] ${fullUpdate.progress_pct}%`
    );

    if (this.simulationMode || !this.node || !this.auraAgentId) {
      console.log("[PaperclipBridge] [SIM]", JSON.stringify(fullUpdate, null, 2));
      return;
    }

    // Write to shared CRDT
    this.node.sharedMemory?.set(
      `project:${fullUpdate.request_id}:status`,
      fullUpdate
    );

    // Serialize CRDT state and broadcast via STATE_SYNC
    const state = this.node.sharedMemory?.serializeState?.() ?? {};
    await this.node.sendMessage(this.auraAgentId, Intent.STATE_SYNC, {
      crdt_type: "LWW-Map",
      state,
      vector_clock: {},
    });
  }
}
