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
import os
import time
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from tpcp.schemas.envelope import (
    AgentIdentity,
    Intent,
    TextPayload,
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


_rate_limits: dict = {}  # ip -> (count, window_start)


def _verify_auth(request: Request):
    """Bearer token auth — only enforced when TPCP_WEBHOOK_SECRET is set."""
    secret = os.environ.get("TPCP_WEBHOOK_SECRET")
    if not secret:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")


def _check_rate_limit(request: Request):
    """Per-IP rate limit: max 60 requests per minute."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if ip in _rate_limits:
        count, window_start = _rate_limits[ip]
        if now - window_start > 60:
            _rate_limits[ip] = (1, now)
        elif count >= 60:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        else:
            _rate_limits[ip] = (count + 1, window_start)
    else:
        _rate_limits[ip] = (1, now)


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
async def trigger_swarm_intent(req: WebhookIntentRequest, _auth=Depends(_verify_auth), _rate=Depends(_check_rate_limit)):
    """
    HTTP POST trigger. Wraps the incoming JSON body into a signed TPCP TextPayload envelope
    and routes it to the local TPCP node for dispatch to the target agent.
    """
    if not _gateway_identity or not _identity_manager or not _local_tpcp_node:
        raise HTTPException(status_code=500, detail="Stateless Webhook Gateway has not been configured securely.")

    try:
        t_id = UUID(req.target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target_id UUID format.")

    payload = TextPayload(content=req.text)

    try:
        # Route the securely validated Envelope to the main TPCP swarm logic node.
        if _local_tpcp_node:
            message_id = await _local_tpcp_node.send_message(t_id, req.intent, payload)
        else:
            raise HTTPException(status_code=500, detail="Local TPCP Node not attached.")

        return {"status": "success", "message_id": str(message_id), "dispatched_to_swarm": True}
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
