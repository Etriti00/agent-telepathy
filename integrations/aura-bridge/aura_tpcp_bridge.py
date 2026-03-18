"""
Aura-App TPCP Bridge
====================
Drop-in module for Aura-App that enables it to communicate with Paperclip
via the TPCP (Telepathy Communication Protocol).

Usage:
    from aura_bridge import AuraBridge, ProjectRequest, ServiceType

    bridge = AuraBridge()
    await bridge.start()

    # When Aura qualifies a lead for service delivery:
    await bridge.request_project(ProjectRequest(
        lead_id="lead_123",
        company_name="Acme Corp",
        contact_email="owner@acme.com",
        service_type=ServiceType.WEBSITE_ECOMMERCE,
        requirements="E-commerce site for 500 products, Stripe integration",
        budget_usd=2500,
        research_notes="Uses Shopify, frustrated by 2% fees. Pain: customization."
    ))

    # Register a callback for project status updates:
    @bridge.on_status_update
    async def handle_update(update: ProjectStatusUpdate):
        print(f"Project {update.request_id}: {update.status} ({update.progress_pct}%)")
        if update.status == ProjectStatus.DELIVERED:
            # Tell Aura's email agent to follow up with the client
            ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID, uuid4

from schemas import ProjectRequest, ProjectStatus, ProjectStatusUpdate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional TPCP import — gracefully degrade if not installed yet
# ---------------------------------------------------------------------------
try:
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tpcp"))
    from tpcp.core.node import TPCPNode
    from tpcp.schemas.envelope import (
        CRDTSyncPayload,
        Intent,
        TextPayload,
    )
    from tpcp.schemas.identity import AgentIdentity

    TPCP_AVAILABLE = True
except ImportError:
    TPCP_AVAILABLE = False
    logger.warning(
        "tpcp package not found — bridge will run in simulation mode. "
        "Install it: cd ../../tpcp && pip install -e ."
    )


StatusCallback = Callable[[ProjectStatusUpdate], Coroutine[Any, Any, None]]


class AuraBridge:
    """
    TPCP bridge for Aura-App.

    Registers Aura as a TPCP node and provides a clean interface for:
    - Sending project requests to Paperclip
    - Receiving project status updates from Paperclip
    - Syncing shared state via CRDT

    Configuration via environment variables:
        TPCP_RELAY_URL       WebSocket URL of the A-DNS relay (default: ws://localhost:8765)
        AURA_TPCP_PORT       Port this node listens on (default: 8100)
        PAPERCLIP_AGENT_ID   UUID of the Paperclip TPCP node (set after first handshake)
        TPCP_PRIVATE_KEY     Base64 Ed25519 seed (auto-generated if not set)
    """

    def __init__(
        self,
        relay_url: str | None = None,
        port: int | None = None,
        paperclip_agent_id: str | UUID | None = None,
    ) -> None:
        self._relay_url = relay_url or os.getenv("TPCP_RELAY_URL", "ws://localhost:8765")
        self._port = port or int(os.getenv("AURA_TPCP_PORT", "8100"))
        self._paperclip_agent_id: UUID | None = (
            UUID(str(paperclip_agent_id)) if paperclip_agent_id else None
        )
        self._node: TPCPNode | None = None
        self._status_callbacks: list[StatusCallback] = []
        self._pending_requests: dict[UUID, ProjectRequest] = {}
        self._simulation_mode = not TPCP_AVAILABLE

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the TPCP node and connect to the relay."""
        if self._simulation_mode:
            logger.warning("[AuraBridge] Running in simulation mode (no TPCP)")
            return

        identity = AgentIdentity(
            agent_id=uuid4(),
            framework="AuraApp",
            capabilities=[
                "lead_generation",
                "sales_outreach",
                "project_request",
                "crm_management",
            ],
        )

        self._node = TPCPNode(
            identity=identity,
            host="127.0.0.1",
            port=self._port,
            adns_url=self._relay_url,
            auto_ack=True,
        )

        # Register handlers for incoming messages from Paperclip
        self._node.register_handler(Intent.STATE_SYNC, self._handle_state_sync)
        self._node.register_handler(Intent.TASK_REQUEST, self._handle_task_request)
        self._node.register_handler(Intent.HANDSHAKE, self._handle_handshake)

        await self._node.start_listening()
        logger.info(
            f"[AuraBridge] Started on port {self._port}, "
            f"relay={self._relay_url}, "
            f"agent_id={self._node.identity.agent_id}"
        )

        # Broadcast discovery so Paperclip finds us
        if self._paperclip_agent_id:
            paperclip_ws = f"ws://localhost:{int(os.getenv('PAPERCLIP_TPCP_PORT', '8101'))}"
            await self._node.broadcast_discovery([paperclip_ws])

    async def stop(self) -> None:
        """Gracefully shut down the TPCP node."""
        if self._node:
            await self._node.stop()
            logger.info("[AuraBridge] Stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def request_project(self, request: ProjectRequest) -> UUID:
        """
        Send a project request to Paperclip.

        This is the main integration point: call this from Aura-App whenever
        a lead has been qualified and needs a deliverable from Paperclip.

        Returns the request_id (UUID) for tracking.
        """
        self._pending_requests[request.request_id] = request
        payload_data = request.model_dump(mode="json")

        if self._simulation_mode or not self._node:
            logger.info(
                f"[AuraBridge] [SIM] Would send project request: "
                f"{request.company_name} → {request.service_type.value} "
                f"(${request.budget_usd})"
            )
            return request.request_id

        if not self._paperclip_agent_id:
            raise RuntimeError(
                "Paperclip agent ID not set. "
                "Wait for handshake or set PAPERCLIP_AGENT_ID env var."
            )

        payload = TextPayload(
            content=json.dumps(payload_data),
            language="json",
        )
        await self._node.send_message(
            target_id=self._paperclip_agent_id,
            intent=Intent.TASK_REQUEST,
            payload=payload,
        )

        # Also write to shared CRDT memory so both sides have the context
        self._node.shared_memory.set(
            f"project:{request.request_id}:request",
            payload_data,
        )

        logger.info(
            f"[AuraBridge] Sent project request {request.request_id} "
            f"to Paperclip ({request.company_name} / {request.service_type.value})"
        )
        return request.request_id

    async def send_revision_request(
        self, request_id: UUID, feedback: str
    ) -> None:
        """Ask Paperclip to revise a delivered project."""
        if self._simulation_mode or not self._node or not self._paperclip_agent_id:
            logger.info(f"[AuraBridge] [SIM] Revision request for {request_id}: {feedback}")
            return

        payload = TextPayload(
            content=json.dumps(
                {
                    "type": "revision_request",
                    "request_id": str(request_id),
                    "feedback": feedback,
                }
            ),
            language="json",
        )
        await self._node.send_message(
            target_id=self._paperclip_agent_id,
            intent=Intent.CRITIQUE,
            payload=payload,
        )

    def on_status_update(self, fn: StatusCallback) -> StatusCallback:
        """
        Decorator to register a callback for project status updates.

        Example:
            @bridge.on_status_update
            async def handle_update(update: ProjectStatusUpdate):
                print(f"Project {update.request_id}: {update.status}")
        """
        self._status_callbacks.append(fn)
        return fn

    def get_project_status(self, request_id: UUID) -> dict[str, Any] | None:
        """Read the latest project status from shared CRDT memory."""
        if not self._node:
            return None
        key = f"project:{request_id}:status"
        return self._node.shared_memory.get(key)

    # ------------------------------------------------------------------
    # TPCP handlers (incoming messages from Paperclip)
    # ------------------------------------------------------------------

    async def _handle_state_sync(self, envelope: Any) -> None:
        """Paperclip sends STATE_SYNC to update project status."""
        try:
            # Merge the CRDT state
            if hasattr(envelope.payload, "state"):
                await self._node.shared_memory.merge(envelope.payload.state)

            # Extract project status updates from merged state
            state = envelope.payload.state if hasattr(envelope.payload, "state") else {}
            for key, entry in state.items():
                if key.startswith("project:") and key.endswith(":status"):
                    raw = entry.get("value") if isinstance(entry, dict) else entry
                    if raw:
                        update = ProjectStatusUpdate.model_validate(
                            raw if isinstance(raw, dict) else json.loads(raw)
                        )
                        await self._dispatch_status_update(update)

        except Exception as exc:
            logger.error(f"[AuraBridge] Error handling STATE_SYNC: {exc}")

    async def _handle_task_request(self, envelope: Any) -> None:
        """Handle any task requests Paperclip sends back (e.g., clarification)."""
        try:
            content = envelope.payload.content
            data = json.loads(content) if isinstance(content, str) else content
            msg_type = data.get("type", "")

            if msg_type == "clarification_needed":
                request_id = UUID(data["request_id"])
                question = data.get("question", "")
                logger.info(
                    f"[AuraBridge] Paperclip needs clarification for {request_id}: {question}"
                )
                # Surface this through the status update system
                if request_id in self._pending_requests:
                    update = ProjectStatusUpdate(
                        request_id=request_id,
                        lead_id=self._pending_requests[request_id].lead_id,
                        status=ProjectStatus.SCOPING,
                        message=f"Paperclip needs clarification: {question}",
                    )
                    await self._dispatch_status_update(update)

        except Exception as exc:
            logger.error(f"[AuraBridge] Error handling TASK_REQUEST: {exc}")

    async def _handle_handshake(self, envelope: Any) -> None:
        """Auto-register Paperclip's agent ID on first handshake."""
        try:
            sender_id = envelope.header.sender_id
            if self._paperclip_agent_id is None:
                self._paperclip_agent_id = UUID(str(sender_id))
                logger.info(
                    f"[AuraBridge] Registered Paperclip agent: {self._paperclip_agent_id}"
                )
        except Exception as exc:
            logger.error(f"[AuraBridge] Error handling HANDSHAKE: {exc}")

    async def _dispatch_status_update(self, update: ProjectStatusUpdate) -> None:
        """Fire all registered status callbacks."""
        for callback in self._status_callbacks:
            try:
                await callback(update)
            except Exception as exc:
                logger.error(f"[AuraBridge] Status callback error: {exc}")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AuraBridge:
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()
