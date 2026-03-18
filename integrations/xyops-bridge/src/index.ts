#!/usr/bin/env node
/**
 * xyops-bridge entry point
 *
 * Starts the XyopsTPCPBridge service which:
 *   1. Registers as 'xyops-agent' on the TPCP relay
 *   2. Listens for job scheduling requests from Aura/Paperclip via TPCP
 *   3. Creates jobs in xyops via REST API
 *   4. Receives xyops webhooks on job completion and sends TPCP updates back
 *   5. Monitors all agency services and broadcasts health alerts
 */

import { XyopsTPCPBridge } from "./XyopsTPCPBridge.js";

const bridge = new XyopsTPCPBridge();

bridge.on("health:report", (report) => {
  const statuses = Object.entries(report.services)
    .map(([k, v]) => `${k}:${v}`)
    .join(" | ");
  console.log(`[Health] ${report.timestamp} — ${statuses}`);
});

bridge.on("job:complete", (payload) => {
  const status = payload.code > 0 ? "success" : payload.code === 0 ? "running" : "error";
  console.log(`[Job] ${payload.id} completed — ${status}`);
});

async function main(): Promise<void> {
  await bridge.start();

  const shutdown = async (signal: string) => {
    console.log(`\n[XyopsBridge] ${signal} received — shutting down`);
    await bridge.stop();
    process.exit(0);
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

main().catch((err) => {
  console.error("[XyopsBridge] Fatal error:", err);
  process.exit(1);
});
