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
Home Assistant & Matter Adapter for TPCP.
Targets Smart Home bridging (Apple, Samsung, LG, Philips).

Translates TPCP TaskRequests into HA REST service-calls, and
streams HA SSE state changes back to the swarm CRDT memory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
from uuid import UUID

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

if TYPE_CHECKING:
    import aiohttp

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import (
    AgentIdentity,
    Intent,
    TPCPEnvelope,
    TextPayload,
    CRDTSyncPayload,
    MessageHeader,
    PROTOCOL_VERSION
)

logger = logging.getLogger(__name__)


class HomeAssistantAdapter(BaseFrameworkAdapter):
    """
    Adapter mapping HomeAssistant Rest API and WebSocket/SSE streams
    into TPCP Envelopes. Acts as a proxy for smart home devices.
    """

    def __init__(self, identity: AgentIdentity, ha_url: str, ha_token: str, identity_manager=None):
        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp is required for HomeAssistantAdapter. "
                "Install it with: pip install tpcp-core[edge]"
            )
        super().__init__(identity, identity_manager)
        self.ha_url = ha_url.rstrip("/")
        self._ha_token = ha_token
        self._session: Optional[aiohttp.ClientSession] = None
        self._listening_task: Optional[asyncio.Task] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(headers={
                "Authorization": f"Bearer {self._ha_token}",
                "Content-Type": "application/json",
            })
        return self._session

    def pack_thought(self, target_id: UUID, raw_output: Dict[str, Any], intent: Intent = Intent.STATE_SYNC) -> TPCPEnvelope:
        """
        Packs HomeAssistant state events into TPCP CRDT memory chunks.
        """
        entity_id = raw_output.get("entity_id", "unknown_entity")
        state_data = raw_output.get("new_state", {})
        
        # Package entity physical state into swarm memory
        memory_state = {
            f"ha_{entity_id}": {
                "value": state_data.get("state"),
                "timestamp": int(time.monotonic() * 1000),
                "writer_id": str(self.identity.agent_id)
            }
        }
        
        self._tick()
        
        payload = CRDTSyncPayload(
            crdt_type="LWW-Map",
            state=memory_state,
            vector_clock={str(self.identity.agent_id): self._logical_clock}
        )

        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=intent,
            protocol_version=PROTOCOL_VERSION
        )

        envelope = TPCPEnvelope(header=header, payload=payload)
        im = self._require_identity_manager()
        envelope.signature = im.sign_payload(payload.model_dump())
        return envelope

    async def execute_service_call(self, domain: str, service: str, entity_id: str, service_data: Optional[dict] = None) -> bool:
        """
        Translates a TPCP agent's physical request into HA REST POST.
        e.g., domain="light", service="turn_on", entity_id="light.living_room".
        """
        data = {"entity_id": entity_id}
        if service_data:
            data.update(service_data)
            
        url = f"{self.ha_url}/api/services/{domain}/{service}"
        
        try:
            session = await self._get_session()
            async with session.post(url, json=data) as resp:
                resp.raise_for_status()
                logger.info(f"Executed HA service: {domain}.{service} on {entity_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to execute HA service call: {e}")
            return False

    async def unpack_request(self, envelope: TPCPEnvelope) -> Any:
        """
        Intercepts inbound TaskRequests to the Smart Home bridging node.
        If structured correctly, runs the execute_service_call.
        """
        if isinstance(envelope.payload, TextPayload):
            try:
                cmd = json.loads(envelope.payload.content)
                if "domain" in cmd and "service" in cmd and "entity_id" in cmd:
                    success = await self.execute_service_call(
                        domain=cmd["domain"],
                        service=cmd["service"],
                        entity_id=cmd["entity_id"],
                        service_data=cmd.get("service_data", {})
                    )
                    return {"status": "success" if success else "failed", "hardware_called": True}
            except json.JSONDecodeError:
                pass
            
        return {"status": "error", "message": "Invalid HomeAssistant physical command payload."}

    async def start_event_stream(self, on_message_callback: Callable[[TPCPEnvelope], None]) -> None:
        """
        Connects to HA REST API Server-Sent Events (SSE) stream to mirror physical state to swarm CRDT.
        """
        session = await self._get_session()
        url = f"{self.ha_url}/api/stream"
        
        async def listen():
            while True:
                try:
                    async with session.get(url) as resp:
                        while True:
                            raw_line = await resp.content.readline()
                            if not raw_line:
                                break
                            decoded = raw_line.decode('utf-8').strip()
                            if decoded.startswith('data: '):
                                raw_json = decoded[6:]
                                if raw_json == "ping":
                                    continue
                                
                                event = json.loads(raw_json)
                                if event.get("event_type") == "state_changed":
                                    data = event.get("data", {})
                                    envelope = self.pack_thought(UUID(int=0), data, Intent.STATE_SYNC)
                                    on_message_callback(envelope)
                                    
                except aiohttp.ClientError as e:
                    logger.warning(f"HA Stream disconnected: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"HA Stream processing error: {e}")
                    await asyncio.sleep(5)

        self._listening_task = asyncio.create_task(listen())
        logger.info(f"HomeAssistant Adapter connected to {self.ha_url} SSE stream.")

    async def stop(self):
        """Cleanup network connections."""
        if self._listening_task:
            self._listening_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
