# xyops TPCP Bridge

Connects **xyops** (job scheduling, workflow automation, server monitoring) to the TPCP agent network. This bridge is the **autonomous operations layer** of the Aura × Paperclip agency — it keeps everything running on its own while you work from your phone.

## What xyops Does in the Agency

| Feature | Role |
|---------|------|
| Job scheduling | Runs Aura lead hunts, Paperclip status sweeps on a schedule |
| Service monitoring | Watches the TPCP relay, Paperclip, and Aura for downtime |
| Webhook triggers | On job completion, notifies the right agent via TPCP |
| Plugin system | `tpcp-notify.js` sends TPCP messages from inside any xyops job |

## Architecture

```
Aura-App / Paperclip
      │
      │  TPCP TASK_REQUEST (type: "schedule_job")
      ▼
 xyops-agent (this bridge)
      │
      │  REST API  GET /api/app/create_job/v1
      ▼
    xyops
      │
      │  Webhook POST /xyops/webhook (on job complete)
      ▼
 xyops-agent (this bridge)
      │
      │  TPCP STATE_SYNC (JobStatusUpdate)
      ▼
Aura-App / Paperclip
```

## Quick Start

```bash
cd xyops-bridge
npm install
cp .env.example .env    # fill in XYOPS_API_KEY and XYOPS_URL
npm run dev
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TPCP_RELAY_URL` | `ws://localhost:8765` | TPCP A-DNS relay URL |
| `XYOPS_URL` | `http://localhost:5522` | xyops API base URL |
| `XYOPS_API_KEY` | *(required)* | xyops API key (24-char alphanumeric) |
| `XYOPS_WEBHOOK_PORT` | `3002` | Port this bridge listens on for xyops callbacks |
| `XYOPS_BRIDGE_PUBLIC_URL` | `http://localhost:3002` | Public URL xyops uses to call the webhook |

## TPCP Message Protocol

Send these from Aura or Paperclip to `xyops-agent` via TPCP TASK_REQUEST:

### Schedule a job

```json
{
  "type": "schedule_job",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "lead_hunt",
  "params": { "industry": "plumbing", "city": "Berlin" },
  "description": "Daily lead hunt for plumbers in Berlin",
  "notify_sender": true
}
```

The bridge creates the job in xyops and, when it completes, sends back:

```json
{
  "type": "job_status_update",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "xyops_job_id": "abc123",
  "status": "success",
  "progress_pct": 100,
  "description": "Found 47 leads",
  "updated_at": "2026-03-18T09:00:01Z"
}
```

### Create a monitoring alert

```json
{
  "type": "create_alert",
  "alert_id": "550e8400-e29b-41d4-a716-446655440001",
  "title": "Paperclip API Down",
  "expression": "[job.total_errors] > 5",
  "message": "Paperclip API is failing. Check http://localhost:3000"
}
```

### Get job status

```json
{
  "type": "get_job_status",
  "xyops_job_id": "abc123"
}
```

## xyops Plugin: tpcp-notify.js

Drop this script into xyops as a plugin to send TPCP messages from inside any xyops job:

```bash
# Copy to xyops plugins directory
cp plugin/tpcp-notify.js /path/to/xyops/plugins/

# In xyops, create an event using this plugin
# Plugin params:
#   tpcp_relay_url  - WebSocket URL of the TPCP relay
#   tpcp_target_id  - Target agent to notify (or broadcast UUID)
#   message         - Optional message body
```

## Docker (full stack)

```bash
cd integrations
docker compose up
```

This starts the complete agency stack:
- `adns-relay` — TPCP message router (:8765)
- `paperclip` — Service delivery orchestrator (:3000)
- `paperclip-bridge` — Paperclip ↔ TPCP link (:8101, :3001)
- `ollama` — Local LLMs for cost-free task execution (:11434)
- `xyops` — Job scheduler + monitoring (:5522)
- `xyops-bridge` — xyops ↔ TPCP link (:8102, :3002)
