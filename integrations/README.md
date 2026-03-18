# Aura-App × Paperclip × xyops — Autonomous Agency via Agent-Telepathy

This directory contains the integration layer that connects **Aura-App** (lead gen / sales), **Paperclip** (service delivery), and **xyops** (job scheduling / monitoring) using **TPCP** as the communication backbone. Together they form a fully autonomous agency you can operate from your phone.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SAME DEVICE                               │
│                                                                     │
│  ┌─────────────────────┐           ┌─────────────────────────────┐  │
│  │      Aura-App       │           │         Paperclip           │  │
│  │  (Lead Gen / Sales) │    TPCP   │   (Service Delivery)        │  │
│  │  • Lead discovery   │◄─────────►│  • Website / app builds     │  │
│  │  • Research         │           │  • Automations              │  │
│  │  • Outreach         │           │  • Agent orchestration      │  │
│  │  [aura-bridge]      │           │  [paperclip-bridge]         │  │
│  └──────────┬──────────┘           └──────────────┬──────────────┘  │
│             │                                     │                 │
│             │         ┌────────────────┐          │                 │
│             └────────►│  TPCP A-DNS    │◄─────────┘                 │
│                       │  Relay :8765   │◄──────────────────────┐    │
│                       └────────────────┘                       │    │
│                                                                │    │
│  ┌─────────────────────────────────────────────────────────┐  │    │
│  │              xyops  (job scheduler + monitoring)         │  │    │
│  │  • Schedule lead hunts, status reports, health checks   │  │    │
│  │  • Alert on service failures → TPCP broadcast           │  │    │
│  │  • Receive TPCP job requests from Aura/Paperclip        │  │    │
│  │  [xyops-bridge]                              :5522       │──┘    │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                Ollama (Local LLMs — free inference)          │   │
│  │         codellama · llama3 · deepseek-coder                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```


This directory contains the integration layer that connects **Aura-App** (lead gen / sales) and **Paperclip** (service delivery) using the **TPCP (Telepathy Communication Protocol)** as the communication backbone.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        SAME DEVICE                            │
│                                                               │
│   ┌─────────────────────┐         ┌─────────────────────────┐ │
│   │      Aura-App       │         │       Paperclip         │ │
│   │  (Lead Gen / Sales) │         │  (Service Delivery)     │ │
│   │                     │         │                         │ │
│   │  • Lead discovery   │  TPCP   │  • Website builds       │ │
│   │  • Research         │◄───────►│  • Web apps             │ │
│   │  • Outreach         │         │  • Automations          │ │
│   │  • Deal tracking    │         │  • Agent orchestration  │ │
│   │                     │         │                         │ │
│   │  [aura-bridge]      │         │  [paperclip-bridge]     │ │
│   └─────────┬───────────┘         └───────────┬─────────────┘ │
│             │                                 │               │
│             │      ┌──────────────────┐       │               │
│             └─────►│  TPCP A-DNS      │◄──────┘               │
│                    │  Relay :8765     │                       │
│                    └──────────────────┘                       │
│                                                               │
│   ┌───────────────────────────────────────────────────────┐   │
│   │                   Ollama (Local LLMs)                 │   │
│   │    codellama · llama3 · deepseek-coder · mistral      │   │
│   │                   [ollama-adapter]                    │   │
│   └───────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

---

## How It Works

### 1. Aura qualifies a lead
Aura-App discovers a business, researches their needs, and determines they need a **website**, **web app**, or **automation**. Instead of a human handoff, Aura fires a TPCP `TASK_REQUEST` directly to Paperclip.

### 2. TPCP carries the context
The lead data (company name, contact, requirements, budget, research notes) is serialized into a TPCP envelope — cryptographically signed and delivered over WebSocket. Shared CRDT memory keeps both systems in sync throughout the project lifecycle.

### 3. Paperclip spins up a project
The Paperclip bridge receives the request, creates a Paperclip **ticket** via its REST API, and assigns it to the appropriate agent team (website builders, app devs, automation engineers). Agents pick it up on their next heartbeat.

### 4. Ollama handles the cheap work
A custom Ollama adapter runs as a Paperclip HTTP webhook agent. It routes tasks intelligently:
- `codellama` / `deepseek-coder` → code generation (free)
- `llama3` / `mistral` → copy, content, planning (free)
- `claude-sonnet` → complex reasoning, client-facing deliverables (paid, used sparingly)

### 5. Status flows back to Aura
As Paperclip progresses through the project, the bridge sends `STATE_SYNC` updates back. Aura's lead record is updated automatically — the salesperson (or Aura's autonomous closer) knows exactly when to follow up with a delivery.

---

## Directory Structure

```
integrations/
├── README.md                   ← This file
├── docker-compose.yml          ← Full-stack local setup
├── shared/
│   ├── schemas.json            ← Cross-language data schemas
│   └── service-types.json      ← Service type taxonomy
├── aura-bridge/
│   ├── README.md
│   ├── requirements.txt
│   ├── aura_tpcp_bridge.py     ← Drop-in Python class for Aura-App
│   ├── schemas.py              ← Pydantic models
│   └── example_usage.py        ← How to integrate into Aura-App
├── paperclip-bridge/
    ├── README.md
    ├── package.json
    ├── tsconfig.json
    ├── src/
    │   ├── index.ts             ← Entry point / CLI
    │   ├── PaperclipTPCPBridge.ts
    │   ├── OllamaAdapter.ts     ← Ollama webhook agent server
    │   ├── schemas.ts           ← TypeScript types
    │   └── config.ts            ← Configuration
    └── Dockerfile
└── xyops-bridge/
    ├── README.md
    ├── package.json
    ├── tsconfig.json
    ├── plugin/
    │   └── tpcp-notify.js      ← xyops plugin: sends TPCP from inside jobs
    ├── src/
    │   ├── index.ts             ← Entry point
    │   ├── XyopsTPCPBridge.ts   ← Core bridge (TPCP <-> xyops API)
    │   ├── schemas.ts           ← TypeScript types
    │   └── config.ts            ← Configuration
    └── Dockerfile
```

---

## Quick Start

### Prerequisites
- Aura-App running locally
- Paperclip running locally (`npx paperclipai onboard --yes`)
- Ollama installed (`ollama serve`)
- Docker (optional, for relay)

### 1. Start the TPCP relay
```bash
docker compose up adns-relay
# or: cd ../tpcp && python -m tpcp.relay
```

### 2. Start the Paperclip bridge
```bash
cd paperclip-bridge
npm install
cp .env.example .env   # fill in PAPERCLIP_API_KEY + PAPERCLIP_URL
npm run dev
```

### 3. Add Aura bridge to Aura-App
```python
# In your Aura-App code:
from aura_bridge import AuraBridge, ProjectRequest, ServiceType

bridge = AuraBridge()
await bridge.start()

# When a lead qualifies for services:
await bridge.request_project(ProjectRequest(
    lead_id="lead_123",
    company_name="Acme Corp",
    service_type=ServiceType.WEBSITE,
    requirements="E-commerce site for 500 products, Stripe integration",
    budget_usd=2500,
    contact_email="owner@acmecorp.com",
    research_notes="Uses Shopify now, wants to move off it. Pain: fees."
))
```

### 4. Register an Ollama agent in Paperclip
In the Paperclip UI, add an agent with:
- **Adapter**: HTTP Webhook
- **URL**: `http://localhost:3001/heartbeat`
- **Role**: "Ollama Developer Agent"

---

## Cost Optimization Strategy

| Task Type | Model | Cost |
|-----------|-------|------|
| Code scaffolding | codellama:13b | Free |
| UI component generation | deepseek-coder:6.7b | Free |
| Landing page copy | llama3:8b | Free |
| Automation scripts | codellama:7b | Free |
| Client proposals | claude-sonnet-4-5 | ~$0.003/req |
| Complex architecture decisions | claude-sonnet-4-5 | ~$0.003/req |
| Final code review | claude-sonnet-4-5 | ~$0.003/req |

Estimated cost per project: **$0.02 - $0.50** vs **$5-20** with cloud-only models.

---

## TPCP Message Flow

```
Aura-App                    TPCP Relay              Paperclip
    │                           │                       │
    │── HANDSHAKE ──────────────►│                       │
    │                           │◄──── HANDSHAKE ────────│
    │                           │                       │
    │── TASK_REQUEST ───────────►│──── TASK_REQUEST ─────►│
    │   (lead + requirements)   │                       │
    │                           │   [creates ticket]    │
    │                           │   [agents work]       │
    │                           │                       │
    │◄── STATE_SYNC ────────────│◄─── STATE_SYNC ────────│
    │   (project_started)       │                       │
    │                           │   [Ollama generates]  │
    │                           │   [review + refine]   │
    │                           │                       │
    │◄── STATE_SYNC ────────────│◄─── STATE_SYNC ────────│
    │   (deliverable_ready)     │                       │
```
