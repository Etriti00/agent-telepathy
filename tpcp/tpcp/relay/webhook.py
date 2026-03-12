# Copyright (c) 2026 Principal Systems Architect
# This file is part of TPCP.
# 
# TPCP is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# TPCP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with TPCP. If not, see <https://www.gnu.org/licenses/>.
# 
# For commercial licensing inquiries, see COMMERCIAL_LICENSE.md

"""
Stateless TPCP Webhook Gateway.
Targets Siri Shortcuts, Zapier, Retool, and custom iOS/Android HTTP triggers.

Runs a fast HTTP API exposing the Swarm via POST requests securely bridging outside JSON logic
to the cryptographically enforced TPCP Agent WebSocket Mesh.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from tpcp.schemas.envelope import (
    AgentIdentity,
    Intent,
    TPCPEnvelope,
    TextPayload,
    MessageHeader,
    PROTOCOL_VERSION
)
from tpcp.security.crypto import AgentIdentityManager

logger = logging.getLogger(__name__)

# FastAPI Setup
app = FastAPI(title="TPCP Stateless Webhook Gateway", version=PROTOCOL_VERSION)

# Global runtime variables allowing instantiation integration natively
_gateway_identity: Optional[AgentIdentity] = None
_identity_manager: Optional[AgentIdentityManager] = None
_on_webhook_inbound_callback = None


class WebhookIntentRequest(BaseModel):
    """Payload schema expected from an external API POST request."""
    target_id: Optional[str] = "00000000-0000-0000-0000-000000000000"
    intent: Intent = Intent.TASK_REQUEST
    text: str


def configure_gateway(identity: AgentIdentity, identity_manager: AgentIdentityManager, bridge_callback):
    """
    Initializes the Webhook Gateway globals.
    Required before running `uvicorn.run(app, ...)`
    """
    global _gateway_identity, _identity_manager, _on_webhook_inbound_callback
    _gateway_identity = identity
    _identity_manager = identity_manager
    _on_webhook_inbound_callback = bridge_callback
    logger.info("Stateless Webhook Gateway successfully configured with Identity bindings.")


@app.post("/webhook/intent")
async def trigger_swarm_intent(req: WebhookIntentRequest):
    """
    HTTP POST trigger. Wraps raw API calls securely inside a signed TPCP TextPayload Envelope.
    Ideal for Siri Shortcuts or Zapier external injection.
    """
    if not _gateway_identity or not _identity_manager or not _on_webhook_inbound_callback:
        raise HTTPException(status_code=500, detail="Stateless Webhook Gateway has not been configured securely.")

    try:
        t_id = UUID(req.target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target_id UUID format.")

    payload = TextPayload(content=req.text)
    
    header = MessageHeader(
        sender_id=_gateway_identity.agent_id,
        receiver_id=t_id,
        intent=req.intent,
        protocol_version=PROTOCOL_VERSION
    )

    payload_dict = payload.model_dump()
    signature = _identity_manager.sign_payload(payload_dict)

    envelope = TPCPEnvelope(
        header=header,
        payload=payload,
        signature=signature
    )

    try:
        # Route the securely validated Envelope to the main TPCP swarm logic node.
        if asyncio.iscoroutinefunction(_on_webhook_inbound_callback):
            await _on_webhook_inbound_callback(envelope)
        else:
            _on_webhook_inbound_callback(envelope)
            
        return {"status": "success", "message_id": str(header.message_id), "dispatched_to_swarm": True}
    except Exception as e:
        logger.error(f"Failed to bridge Webhook Intent to Swarm Core: {e}")
        raise HTTPException(status_code=502, detail="Failed to route into Mesh.")


@app.get("/health")
async def get_health():
    """Simple health checking for AWS/GCP ALBs."""
    return {"status": "ok", "version": PROTOCOL_VERSION, "gateway_active": _gateway_identity is not None}
