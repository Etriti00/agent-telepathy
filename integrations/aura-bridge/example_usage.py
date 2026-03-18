"""
Example: How to integrate AuraBridge into Aura-App
===================================================
This shows how to wire AuraBridge into Aura-App's existing agent pipeline.

In practice, you'd call `bridge.request_project()` from inside Aura's
"deal closing" or "needs assessment" engine when a lead is qualified
and ready for a deliverable from Paperclip.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from aura_tpcp_bridge import AuraBridge
from schemas import (
    CompanySize,
    Priority,
    ProjectRequest,
    ProjectStatus,
    ProjectStatusUpdate,
    ServiceType,
)

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    # --- 1. Create and start the bridge ---
    bridge = AuraBridge(
        relay_url="ws://localhost:8765",
        port=8100,
    )

    # --- 2. Register a callback for project status updates ---
    @bridge.on_status_update
    async def handle_project_update(update: ProjectStatusUpdate) -> None:
        print(f"\n[Aura] Project update received!")
        print(f"  Lead:     {update.lead_id}")
        print(f"  Status:   {update.status.value}")
        print(f"  Progress: {update.progress_pct}%")
        if update.message:
            print(f"  Message:  {update.message}")
        if update.deliverable_url:
            print(f"  Delivery: {update.deliverable_url}")

        # -- Hook this into Aura's CRM / sequencing engine --
        if update.status == ProjectStatus.DELIVERED:
            print(f"\n  [Aura] Triggering follow-up email sequence for lead {update.lead_id}")
            # aura.email_agent.send_delivery_notification(update.lead_id, update.deliverable_url)

        elif update.status == ProjectStatus.COMPLETED:
            print(f"\n  [Aura] Marking lead {update.lead_id} as WON in CRM")
            # aura.crm.update_lead_status(update.lead_id, "won")

        elif update.status == ProjectStatus.REVISION_REQUESTED:
            print(f"\n  [Aura] Notifying client about revision for lead {update.lead_id}")

    async with bridge:
        # --- 3. Scenario: Aura qualified a lead for an e-commerce site ---
        request = ProjectRequest(
            lead_id="lead_789_acme",
            company_name="Acme Hardware Co.",
            contact_email="mike@acmehardware.com",
            contact_name="Mike Torres",
            contact_phone="+1-555-0123",
            service_type=ServiceType.WEBSITE_ECOMMERCE,
            requirements=(
                "E-commerce site for 500 SKUs of hardware products. "
                "Needs Stripe checkout, inventory tracking, and mobile-friendly design. "
                "Client wants to move off Etsy where they're paying high fees."
            ),
            budget_usd=2800,
            priority=Priority.HIGH,
            deadline_iso=datetime.utcnow() + timedelta(days=14),
            research_notes=(
                "Currently on Etsy (600+ sales, 4.8 stars). "
                "Pain point: Etsy fees eating 10-15% of revenue. "
                "Tech savvy owner (runs own email via Gmail). "
                "Competitor BuildRight moved off Etsy last year — Mike noticed their traffic went up. "
                "Open to ongoing maintenance contract at $150/month."
            ),
            existing_website=None,
            industry="Hardware & Tools",
            company_size=CompanySize.SOLO,
            metadata={
                "aura_score": 87,
                "outreach_stage": "deal_closing",
                "last_email_opened": "2026-03-17T14:30:00Z",
                "source": "google_maps_scrape",
            },
        )

        print(f"\n[Aura] Sending project request to Paperclip...")
        request_id = await bridge.request_project(request)
        print(f"[Aura] Request sent: {request_id}")

        # --- 4. Check status via shared CRDT ---
        await asyncio.sleep(2)  # Let CRDT sync
        status = bridge.get_project_status(request_id)
        if status:
            print(f"[Aura] Current status from CRDT: {status}")

        # --- 5. Simulate receiving updates (in real use, these come async) ---
        print("\n[Aura] Listening for project updates... (Ctrl+C to stop)")
        await asyncio.sleep(60)  # In production, run indefinitely


if __name__ == "__main__":
    asyncio.run(main())
