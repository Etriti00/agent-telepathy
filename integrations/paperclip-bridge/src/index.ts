#!/usr/bin/env node
/**
 * Paperclip TPCP Bridge — Entry Point
 *
 * Usage:
 *   npm run dev                   → starts both bridge + Ollama adapter
 *   npm run start:bridge          → bridge only (TPCP ↔ Paperclip)
 *   npm run start:ollama          → Ollama adapter only (webhook server)
 */

import { config } from "./config.js";
import { PaperclipTPCPBridge } from "./PaperclipTPCPBridge.js";
import { startOllamaAdapter } from "./OllamaAdapter.js";

const mode = process.argv.find((a) => a.startsWith("--mode="))?.split("=")[1];

async function main() {
  console.log("=".repeat(60));
  console.log("  Paperclip × Aura Integration — TPCP Bridge");
  console.log("=".repeat(60));
  console.log(`  Mode:             ${mode ?? "full (bridge + ollama)"}`);
  console.log(`  TPCP relay:       ${config.tpcp.relayUrl}`);
  console.log(`  TPCP port:        ${config.tpcp.port}`);
  console.log(`  Paperclip API:    ${config.paperclip.apiUrl}`);
  console.log(`  Ollama API:       ${config.ollama.baseUrl}`);
  console.log(`  Webhook port:     ${config.paperclip.webhookPort}`);
  console.log("=".repeat(60));

  if (!config.paperclip.apiKey && mode !== "ollama-adapter") {
    console.warn(
      "\n⚠️  PAPERCLIP_API_KEY not set — bridge will run in simulation mode.\n" +
        "   Get your key from Paperclip: http://localhost:3000/settings/api\n"
    );
  }

  if (!config.paperclip.companyId && mode !== "ollama-adapter") {
    console.warn(
      "⚠️  PAPERCLIP_COMPANY_ID not set — set this to your Paperclip company ID.\n"
    );
  }

  const tasks: Promise<void>[] = [];

  if (mode !== "ollama-adapter") {
    const bridge = new PaperclipTPCPBridge();
    tasks.push(bridge.start());
  }

  if (mode !== "bridge") {
    tasks.push(startOllamaAdapter(config.paperclip.webhookPort));
  }

  await Promise.all(tasks);

  console.log("\n✓ Ready! Waiting for messages from Aura-App...\n");

  // Keep alive
  process.on("SIGINT", () => {
    console.log("\n[Bridge] Shutting down...");
    process.exit(0);
  });
}

main().catch((err) => {
  console.error("[Bridge] Fatal error:", err);
  process.exit(1);
});
