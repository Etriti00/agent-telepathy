# Aura-App TPCP Bridge

Drop-in Python module for Aura-App that enables it to send qualified leads to Paperclip and receive project status updates.

## Setup

### 1. Install the TPCP Python package
```bash
# From the agent-telepathy repo root:
pip install -e ../../tpcp
# Then install this bridge's deps:
pip install -r requirements.txt
```

### 2. Add the bridge to your Aura-App code
```python
import asyncio
from aura_tpcp_bridge import AuraBridge
from schemas import ProjectRequest, ProjectStatus, ProjectStatusUpdate, ServiceType

bridge = AuraBridge(
    relay_url="ws://localhost:8765",   # TPCP relay address
    port=8100,                          # This node's port
)

@bridge.on_status_update
async def handle_update(update: ProjectStatusUpdate):
    """Called whenever Paperclip reports progress on a project."""
    if update.status == ProjectStatus.DELIVERED:
        # Trigger your delivery email / CRM update here
        pass

await bridge.start()
```

### 3. Send a project request when a lead qualifies
```python
from uuid import uuid4
from schemas import ProjectRequest, ServiceType, Priority

request = ProjectRequest(
    lead_id="lead_123",                           # Your internal lead ID
    company_name="Acme Corp",
    contact_email="owner@acme.com",
    service_type=ServiceType.WEBSITE_ECOMMERCE,
    requirements="E-commerce for 500 products, Stripe checkout",
    budget_usd=2500,
    priority=Priority.HIGH,
    research_notes="Moving off Etsy, frustrated by fees...",
)

request_id = await bridge.request_project(request)
```

## Integration Points in Aura-App

The bridge should be called from these places in Aura-App:

| Aura Engine | When to call | Action |
|------------|-------------|--------|
| `deal_closing_engine.py` | Lead score > 80, reply shows interest in services | `bridge.request_project()` |
| `needs_assessment_engine.py` | Research reveals tech needs | `bridge.request_project()` |
| `objection_handler.py` | Client asks for a sample/demo | `bridge.request_project()` with `priority=HIGH` |
| `follow_up_engine.py` | Project delivered notification | Send delivery follow-up email |

## Environment Variables

| Variable | Default | Description |
|---------|---------|-------------|
| `TPCP_RELAY_URL` | `ws://localhost:8765` | TPCP relay WebSocket URL |
| `AURA_TPCP_PORT` | `8100` | Port this node listens on |
| `PAPERCLIP_AGENT_ID` | Auto-discovered | Paperclip node's UUID (set after first handshake) |
| `TPCP_PRIVATE_KEY` | Auto-generated | Base64 Ed25519 seed |

## Service Types

| Value | Use for |
|-------|---------|
| `website_landing` | Marketing landing pages |
| `website_ecommerce` | Online stores |
| `website_portfolio` | Portfolio / brochure sites |
| `webapp_saas` | Multi-user SaaS apps |
| `webapp_internal_tool` | Internal dashboards / tools |
| `webapp_dashboard` | Analytics dashboards |
| `automation_email` | Email drip sequences |
| `automation_crm` | CRM workflow automation |
| `automation_data_pipeline` | ETL / data pipelines |
| `automation_scraper` | Web scrapers |
| `automation_reporting` | Scheduled reports |
