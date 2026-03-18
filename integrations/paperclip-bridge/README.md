# Paperclip TPCP Bridge

Connects Paperclip (service delivery orchestrator) to the TPCP network so it can receive project requests from Aura-App and report status back.

## What it does

1. **Bridge** — Registers as a TPCP node, receives `TASK_REQUEST` messages from Aura, creates Paperclip tickets via REST API, polls for status changes, and sends `STATE_SYNC` updates back to Aura.

2. **Ollama Adapter** — Runs an HTTP server (`POST /heartbeat`) that Paperclip treats as a webhook agent. Routes tasks to the right local model (codellama, llama3, deepseek-coder) or escalates to Claude for complex/client-facing work.

## Setup

### 1. Install dependencies
```bash
npm install
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — fill in PAPERCLIP_API_KEY and PAPERCLIP_COMPANY_ID
```

### 3. Pull Ollama models (one-time)
```bash
ollama pull codellama:13b       # For code generation
ollama pull llama3:8b           # For content and planning
ollama pull deepseek-coder:6.7b # For code review
```

### 4. Start the bridge
```bash
npm run dev   # Development mode (hot reload)
npm start     # Production mode
```

This starts both the TPCP bridge (port 8101) and the Ollama webhook adapter (port 3001).

## Register the Ollama agent in Paperclip

1. Open Paperclip UI at `http://localhost:3000`
2. Go to **Employees** → **Add Agent**
3. Configure:
   - **Name**: Ollama Developer Agent
   - **Adapter**: HTTP Webhook
   - **Webhook URL**: `http://localhost:3001/heartbeat`
   - **Role**: Developer (or create a custom role)
   - **Monthly budget**: $0 (it's free — Ollama is local)
4. Assign this agent to the same company/goal as your service delivery projects

## Model Routing

| Task keyword | Model | Cost |
|-------------|-------|------|
| implement, create, build, generate, write code | codellama:13b | Free |
| copy, content, text, landing page, email | llama3:8b | Free |
| review, check, validate, debug, audit | deepseek-coder:6.7b | Free |
| proposal, client email, final review, complex architecture | claude-sonnet-4-6 | ~$0.003 |

If Ollama is not running, all tasks automatically fall back to Claude.

## API

### `POST /heartbeat`
Receives a Paperclip agent heartbeat and runs the task via Ollama/Claude.

**Request:**
```json
{
  "agent_id": "uuid",
  "task": {
    "id": "ticket-123",
    "title": "Create landing page for Acme Corp",
    "description": "...",
    "goal_ancestry": ["Service Delivery", "Website Projects"],
    "metadata": {
      "service_type": "website_landing",
      "company_name": "Acme Corp",
      "requirements": "..."
    }
  }
}
```

**Response:**
```json
{
  "status": "completed",
  "output": "Here's the Next.js landing page component...",
  "model_used": "codellama:13b",
  "tokens_used": 1247
}
```

### `GET /models`
Returns available Ollama models and current routing configuration.

### `GET /health`
Health check endpoint.
