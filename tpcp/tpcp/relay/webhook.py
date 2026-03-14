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
_local_tpcp_node = None


class WebhookIntentRequest(BaseModel):
    """Payload schema expected from an external API POST request."""
    target_id: Optional[str] = "00000000-0000-0000-0000-000000000000"
    intent: Intent = Intent.TASK_REQUEST
    text: str


def configure_gateway(identity: AgentIdentity, identity_manager: AgentIdentityManager, tpcp_node):
    """
    Initializes the Webhook Gateway globals.
    Required before running `uvicorn.run(app, ...)`
    """
    global _gateway_identity, _identity_manager, _local_tpcp_node
    _gateway_identity = identity
    _identity_manager = identity_manager
    _local_tpcp_node = tpcp_node
    logger.info("Stateless Webhook Gateway successfully configured with Identity bindings.")


@app.post("/webhook/intent")
async def trigger_swarm_intent(req: WebhookIntentRequest):
    """
    HTTP POST trigger. Wraps raw API calls securely inside a signed TPCP TextPayload Envelope.
    Ideal for Siri Shortcuts or Zapier external injection.
    """
    if not _gateway_identity or not _identity_manager or not _local_tpcp_node:
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
        if _local_tpcp_node:
            await _local_tpcp_node.send_message(t_id, req.intent, payload)
        else:
            raise HTTPException(status_code=500, detail="Local TPCP Node not attached.")
            
            
        return {"status": "success", "message_id": str(header.message_id), "dispatched_to_swarm": True}
    except Exception as e:
        logger.error(f"Failed to bridge Webhook Intent to Swarm Core: {e}")
        raise HTTPException(status_code=502, detail="Failed to route into Mesh.")


@app.get("/health")
async def get_health():
    """Simple health checking for AWS/GCP ALBs."""
    return {"status": "ok", "version": PROTOCOL_VERSION, "gateway_active": _gateway_identity is not None}


if __name__ == "__main__":
    import uvicorn
    import asyncio
    import os
    
    # Standalone execution example for the webhook gateway
    async def run_gateway():
        # Instantiate identity manager and TPCP node natively
        identity_mgr = AgentIdentityManager(auto_save=False)
        identity = AgentIdentity(
            framework="FastAPI-Webhook-Gateway",
            public_key=identity_mgr.get_public_key_string(),
            capabilities=["http-bridge"]
        )
        
        from tpcp.core.node import TPCPNode
        node = TPCPNode(identity, port=8080, identity_manager=identity_mgr)
        
        # Configure and bind the webhook globals to this local node
        configure_gateway(identity, identity_mgr, node)
        
        # Start node networking
        await node.start_listening()
        
        # Start API server in background
        config = uvicorn.Config(app, host="0.0.0.0", port=5000, log_level="info")
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        finally:
            await node.stop_listening()

    asyncio.run(run_gateway())
