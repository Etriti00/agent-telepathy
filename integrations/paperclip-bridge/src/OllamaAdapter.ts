/**
 * Ollama Agent Adapter for Paperclip
 * ====================================
 * This runs as a lightweight HTTP server that Paperclip treats as a
 * "HTTP Webhook" agent. When Paperclip sends a heartbeat, this server:
 *
 * 1. Reads the task and its goal context
 * 2. Routes it to the appropriate Ollama model (or escalates to Claude)
 * 3. Returns the result to Paperclip
 *
 * Register in Paperclip UI:
 *   - Adapter: HTTP Webhook
 *   - URL: http://localhost:3001/heartbeat
 *   - Role: "Ollama Developer Agent"
 *
 * Cost routing:
 *   Code gen        → codellama:13b       (free)
 *   Content/copy    → llama3:8b           (free)
 *   Code review     → deepseek-coder:6.7b (free)
 *   Complex/client  → claude-sonnet-4-6   (paid, ~$0.003/req)
 */

import Anthropic from "@anthropic-ai/sdk";
import axios from "axios";
import express, { Request, Response } from "express";
import { config } from "./config.js";

interface PaperclipHeartbeat {
  agent_id: string;
  task?: {
    id: string;
    title: string;
    description: string;
    goal_ancestry?: string[];
    metadata?: Record<string, unknown>;
  };
  context?: Record<string, unknown>;
  preferred_model?: string;
}

interface HeartbeatResponse {
  status: "completed" | "needs_approval" | "failed" | "escalate_to_claude";
  output: string;
  model_used: string;
  tokens_used?: number;
  escalation_reason?: string;
}

// ---------------------------------------------------------------------------
// Task classification → model routing
// ---------------------------------------------------------------------------

function classifyTask(task: PaperclipHeartbeat["task"]): {
  modelType: "code" | "content" | "review" | "planning";
  shouldEscalate: boolean;
  escalationReason?: string;
} {
  if (!task) {
    return { modelType: "planning", shouldEscalate: false };
  }

  const text = `${task.title} ${task.description}`.toLowerCase();

  // Signals that need Claude for quality/client-facing work
  const clientFacingSignals = [
    "proposal",
    "client email",
    "final review",
    "architecture decision",
    "security audit",
    "performance optimization",
    "complex algorithm",
    "production deploy",
  ];
  if (clientFacingSignals.some((s) => text.includes(s))) {
    return {
      modelType: "planning",
      shouldEscalate: true,
      escalationReason: "Client-facing or complex task requires Claude",
    };
  }

  // Code generation
  if (
    text.match(
      /\b(implement|create|build|generate|write|code|function|component|api|endpoint|schema|migration|test)\b/
    )
  ) {
    return { modelType: "code", shouldEscalate: false };
  }

  // Content / copy
  if (
    text.match(
      /\b(copy|content|text|description|landing|headline|email|blog|readme|docs|documentation)\b/
    )
  ) {
    return { modelType: "content", shouldEscalate: false };
  }

  // Code review
  if (text.match(/\b(review|check|validate|verify|lint|audit|debug|fix)\b/)) {
    return { modelType: "review", shouldEscalate: false };
  }

  // Default: planning/analysis
  return { modelType: "planning", shouldEscalate: false };
}

function selectOllamaModel(modelType: string): string {
  const { ollama } = config;
  switch (modelType) {
    case "code":
      return ollama.defaultCodeModel;
    case "content":
      return ollama.defaultContentModel;
    case "review":
      return ollama.defaultReviewModel;
    default:
      return ollama.defaultContentModel;
  }
}

// ---------------------------------------------------------------------------
// Model inference
// ---------------------------------------------------------------------------

async function runOllama(
  model: string,
  prompt: string
): Promise<{ output: string; tokensUsed: number }> {
  const response = await axios.post(
    `${config.ollama.baseUrl}/api/generate`,
    {
      model,
      prompt,
      stream: false,
      options: {
        temperature: 0.3,
        num_predict: 4096,
      },
    },
    { timeout: 120_000 }
  );

  return {
    output: response.data.response ?? "",
    tokensUsed: response.data.eval_count ?? 0,
  };
}

async function runClaude(prompt: string): Promise<{ output: string; tokensUsed: number }> {
  const client = new Anthropic({ apiKey: config.ollama.escalationApiKey });
  const msg = await client.messages.create({
    model: config.ollama.escalationModel,
    max_tokens: 4096,
    messages: [{ role: "user", content: prompt }],
  });

  const text =
    msg.content
      .filter((b) => b.type === "text")
      .map((b) => (b as any).text)
      .join("") ?? "";

  return {
    output: text,
    tokensUsed: msg.usage.input_tokens + msg.usage.output_tokens,
  };
}

// ---------------------------------------------------------------------------
// Prompt builder
// ---------------------------------------------------------------------------

function buildPrompt(heartbeat: PaperclipHeartbeat): string {
  const { task, context } = heartbeat;
  if (!task) return "No task provided.";

  const goalContext =
    task.goal_ancestry?.length
      ? `\nGoal context: ${task.goal_ancestry.join(" → ")}`
      : "";

  const projectContext = context
    ? `\nProject context:\n${JSON.stringify(context, null, 2)}`
    : "";

  const serviceType = (task.metadata?.service_type as string) ?? "";
  const companyName = (task.metadata?.company_name as string) ?? "";
  const requirements = (task.metadata?.requirements as string) ?? "";

  let systemHint = "";
  if (serviceType.startsWith("website") || serviceType.startsWith("webapp")) {
    systemHint =
      "You are an expert web developer. Prefer Next.js, Tailwind CSS, TypeScript. Write production-quality code.";
  } else if (serviceType.startsWith("automation")) {
    systemHint =
      "You are an expert automation engineer. Prefer Python, n8n workflows, and clean, well-commented scripts.";
  } else {
    systemHint =
      "You are an expert software developer and business analyst. Be precise and practical.";
  }

  return `${systemHint}

Task: ${task.title}
${goalContext}

Description:
${task.description}

${companyName ? `Client: ${companyName}` : ""}
${requirements ? `Requirements:\n${requirements}` : ""}
${projectContext}

Please complete this task with production-quality output. Include all necessary code, explanations, and next steps.`;
}

// ---------------------------------------------------------------------------
// Express server
// ---------------------------------------------------------------------------

export function createOllamaAdapterServer() {
  const app = express();
  app.use(express.json());

  // Health check
  app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok", mode: "ollama-adapter" });
  });

  // Paperclip heartbeat endpoint
  app.post("/heartbeat", async (req: Request, res: Response) => {
    const heartbeat = req.body as PaperclipHeartbeat;

    if (!heartbeat.task) {
      res.json({
        status: "completed",
        output: "No task assigned. Ready for work.",
        model_used: "none",
      } satisfies HeartbeatResponse);
      return;
    }

    console.log(
      `[OllamaAdapter] Heartbeat received: ${heartbeat.task.title} (agent: ${heartbeat.agent_id})`
    );

    const { modelType, shouldEscalate, escalationReason } = classifyTask(
      heartbeat.task
    );
    const prompt = buildPrompt(heartbeat);

    try {
      let output: string;
      let tokensUsed: number;
      let modelUsed: string;

      if (shouldEscalate && config.ollama.escalationApiKey) {
        console.log(
          `[OllamaAdapter] Escalating to Claude: ${escalationReason}`
        );
        modelUsed = config.ollama.escalationModel;
        ({ output, tokensUsed } = await runClaude(prompt));
      } else if (shouldEscalate) {
        // No Claude API key — fall back to best local model
        console.log(
          "[OllamaAdapter] Escalation requested but no API key — using local model"
        );
        modelUsed = config.ollama.defaultCodeModel;
        ({ output, tokensUsed } = await runOllama(modelUsed, prompt));
      } else {
        modelUsed = selectOllamaModel(modelType);
        console.log(`[OllamaAdapter] Using ${modelUsed} for ${modelType}`);
        ({ output, tokensUsed } = await runOllama(modelUsed, prompt));
      }

      const response: HeartbeatResponse = {
        status: "completed",
        output,
        model_used: modelUsed,
        tokens_used: tokensUsed,
      };

      console.log(
        `[OllamaAdapter] Task completed: ${heartbeat.task.id} (${tokensUsed} tokens, ${modelUsed})`
      );
      res.json(response);
    } catch (err: any) {
      const isOllamaDown =
        err.code === "ECONNREFUSED" || err.message?.includes("ECONNREFUSED");

      if (isOllamaDown) {
        console.warn(
          "[OllamaAdapter] Ollama not running — escalating to Claude"
        );
        if (config.ollama.escalationApiKey) {
          try {
            const { output, tokensUsed } = await runClaude(prompt);
            res.json({
              status: "completed",
              output,
              model_used: config.ollama.escalationModel,
              tokens_used: tokensUsed,
            } satisfies HeartbeatResponse);
            return;
          } catch (claudeErr: any) {
            console.error("[OllamaAdapter] Claude escalation failed:", claudeErr.message);
          }
        }
      }

      console.error("[OllamaAdapter] Task failed:", err.message);
      res.status(500).json({
        status: "failed",
        output: `Error: ${err.message}`,
        model_used: "none",
      } satisfies HeartbeatResponse);
    }
  });

  // Model status endpoint (useful for Paperclip UI)
  app.get("/models", async (_req: Request, res: Response) => {
    try {
      const resp = await axios.get(`${config.ollama.baseUrl}/api/tags`, {
        timeout: 5000,
      });
      res.json({
        ollama_available: true,
        models: resp.data.models?.map((m: any) => m.name) ?? [],
        claude_available: !!config.ollama.escalationApiKey,
        routing: {
          code: config.ollama.defaultCodeModel,
          content: config.ollama.defaultContentModel,
          review: config.ollama.defaultReviewModel,
          escalation: config.ollama.escalationModel,
        },
      });
    } catch {
      res.json({
        ollama_available: false,
        models: [],
        claude_available: !!config.ollama.escalationApiKey,
        message: "Ollama not reachable — all tasks will use Claude",
      });
    }
  });

  return app;
}

export async function startOllamaAdapter(
  port: number = config.paperclip.webhookPort
): Promise<void> {
  const app = createOllamaAdapterServer();
  return new Promise((resolve) => {
    app.listen(port, () => {
      console.log(
        `[OllamaAdapter] Listening on http://localhost:${port}/heartbeat`
      );
      console.log(`[OllamaAdapter] Model routing:`);
      console.log(`  Code generation → ${config.ollama.defaultCodeModel}`);
      console.log(`  Content/copy    → ${config.ollama.defaultContentModel}`);
      console.log(`  Code review     → ${config.ollama.defaultReviewModel}`);
      console.log(
        `  Escalation      → ${config.ollama.escalationModel} (${
          config.ollama.escalationApiKey ? "API key set" : "NO API KEY — will use local"
        })`
      );
      resolve();
    });
  });
}
