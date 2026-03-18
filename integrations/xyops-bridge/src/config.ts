import dotenv from "dotenv";
dotenv.config();

export const config = {
  // TPCP settings
  tpcp: {
    relayUrl: process.env.TPCP_RELAY_URL ?? "ws://localhost:8765",
    port: parseInt(process.env.XYOPS_TPCP_PORT ?? "8102", 10),
    privateKeyB64: process.env.TPCP_PRIVATE_KEY_XYOPS,
    auraAgentId: process.env.AURA_AGENT_ID ?? "aura-agent",
    paperclipAgentId: process.env.PAPERCLIP_AGENT_ID ?? "paperclip-agent",
  },

  // xyops REST API settings
  xyops: {
    apiUrl: process.env.XYOPS_URL ?? "http://localhost:5522",
    apiKey: process.env.XYOPS_API_KEY ?? "",
    // Webhook port that xyops will call back to this bridge
    webhookPort: parseInt(process.env.XYOPS_WEBHOOK_PORT ?? "3002", 10),
    webhookPath: process.env.XYOPS_WEBHOOK_PATH ?? "/xyops/webhook",
    // Prefix for jobs created by this bridge (for idempotency filtering)
    jobPrefix: process.env.XYOPS_JOB_PREFIX ?? "tpcp:",
  },

  // Scheduled agency jobs (cron expressions)
  schedule: {
    // Daily lead hunt — runs Aura's campaign pipeline
    leadHuntCron: process.env.LEAD_HUNT_CRON ?? "0 9 * * *",       // 9:00 AM daily
    // Weekly status report — summarizes projects in Paperclip
    statusReportCron: process.env.STATUS_REPORT_CRON ?? "0 8 * * 1", // 8:00 AM Monday
    // Health check — monitors all services
    healthCheckCron: process.env.HEALTH_CHECK_CRON ?? "*/5 * * * *", // Every 5 min
  },

  // Service health check endpoints
  healthChecks: {
    tpcpRelay: process.env.TPCP_RELAY_HEALTH ?? "http://localhost:8765/health",
    paperclip: process.env.PAPERCLIP_URL ?? "http://localhost:3000",
    aura: process.env.AURA_HEALTH_URL ?? "http://localhost:8100/health",
    ollama: process.env.OLLAMA_URL ?? "http://localhost:11434",
  },

  bridge: {
    logLevel: process.env.LOG_LEVEL ?? "info",
    // How long to keep job→sender mappings in memory (ms)
    jobTtlMs: parseInt(process.env.JOB_TTL_MS ?? "86400000", 10), // 24h
  },
} as const;

export type Config = typeof config;
