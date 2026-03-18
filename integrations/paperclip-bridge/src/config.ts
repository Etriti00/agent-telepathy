import dotenv from "dotenv";
dotenv.config();

export const config = {
  // TPCP settings
  tpcp: {
    relayUrl: process.env.TPCP_RELAY_URL ?? "ws://localhost:8765",
    port: parseInt(process.env.PAPERCLIP_TPCP_PORT ?? "8101", 10),
    auraPort: parseInt(process.env.AURA_TPCP_PORT ?? "8100", 10),
    privateKeyB64: process.env.TPCP_PRIVATE_KEY,
  },

  // Paperclip REST API settings
  paperclip: {
    apiUrl: process.env.PAPERCLIP_URL ?? "http://localhost:3000",
    apiKey: process.env.PAPERCLIP_API_KEY ?? "",
    companyId: process.env.PAPERCLIP_COMPANY_ID ?? "",
    goalId: process.env.PAPERCLIP_GOAL_ID, // Optional: link all projects to a goal
    webhookPort: parseInt(process.env.PAPERCLIP_WEBHOOK_PORT ?? "3001", 10),
  },

  // Ollama settings
  ollama: {
    baseUrl: process.env.OLLAMA_URL ?? "http://localhost:11434",
    defaultCodeModel: process.env.OLLAMA_CODE_MODEL ?? "codellama:13b",
    defaultContentModel: process.env.OLLAMA_CONTENT_MODEL ?? "llama3:8b",
    defaultReviewModel: process.env.OLLAMA_REVIEW_MODEL ?? "deepseek-coder:6.7b",
    // If a task is too complex for local models, escalate to Claude
    escalationModel: process.env.ESCALATION_MODEL ?? "claude-sonnet-4-6",
    escalationApiKey: process.env.ANTHROPIC_API_KEY ?? "",
    // Cost threshold in USD: escalate if estimated token cost > this
    escalationThresholdUsd: parseFloat(
      process.env.OLLAMA_ESCALATION_THRESHOLD ?? "0.05"
    ),
  },

  // Bridge settings
  bridge: {
    // How often to check Paperclip for ticket status changes (ms)
    pollIntervalMs: parseInt(process.env.POLL_INTERVAL_MS ?? "15000", 10),
    logLevel: process.env.LOG_LEVEL ?? "info",
  },
} as const;

export type Config = typeof config;
