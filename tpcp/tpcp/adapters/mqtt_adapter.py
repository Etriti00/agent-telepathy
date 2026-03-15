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
MQTT Broker Adapter for TPCP.
Targets Industrial IoT networks and embedded edge hardware (ESP32).

Translates bi-directional MQTT topics into TPCP semantic payloads 
and natively injects sensor data streams into the swarm's CRDT state.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

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


class MQTTAdapter(BaseFrameworkAdapter):
    """
    Adapter bridging Industrial IoT infrastructure (via standard MQTT Broker)
    into a TPCP swarm natively.
    """

    def __init__(self, identity: AgentIdentity, broker_host: str, broker_port: int = 1883,
                 client_id: str = "tpcp_edge_bridge", identity_manager=None):
        if not MQTT_AVAILABLE:
            raise ImportError(
                "paho-mqtt is required for MQTTAdapter. "
                "Install it with: pip install tpcp-core[edge]"
            )
        super().__init__(identity, identity_manager)
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id, protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self._on_tpcp_message_callback: Optional[Callable[[TPCPEnvelope], None]] = None
        self._subscribed_topics: List[str] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def pack_thought(self, target_id: UUID, raw_output: Dict[str, Any], intent: Intent = Intent.STATE_SYNC) -> TPCPEnvelope:
        """
        Translates raw MQTT sensor dictionaries into structured CRDT operations.
        """
        topic = raw_output.get("topic", "unknown/sensor")
        payload_data = raw_output.get("payload", "")
        
        # We try to parse the payload as JSON for rich CRDT ingestion, fallback to basic text
        try:
            value = json.loads(payload_data)
        except json.JSONDecodeError:
            value = payload_data
            
        memory_state = {
            f"mqtt_{topic.replace('/', '_')}": {
                "value": value,
                "timestamp": int(time.time() * 1000),
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
        if self.identity_manager:
            envelope.signature = self.identity_manager.sign_payload(payload.model_dump())
        return envelope

    def unpack_request(self, envelope: TPCPEnvelope) -> Any:
        """
        Intercepts TaskRequests from the Swarm destined for MQTT devices.
        Agent payload instructions: { "topic": "cmnd/relay", "payload": "ON" }
        """
        if isinstance(envelope.payload, TextPayload):
            try:
                cmd = json.loads(envelope.payload.content)
                if "topic" in cmd and "payload" in cmd:
                    publish_payload = json.dumps(cmd["payload"]) if isinstance(cmd["payload"], dict) else str(cmd["payload"])
                    self.client.publish(cmd["topic"], publish_payload, qos=1)
                    logger.info(f"Bridged TPCP Intent -> MQTT Message on '{cmd['topic']}'")
                    return {"status": "published"}
            except json.JSONDecodeError:
                pass
            
        return {"status": "error", "message": "Invalid TPCP-to-MQTT command."}

    def start_broker_connection(self, topics: List[str], on_message_callback: Callable[[TPCPEnvelope], None]) -> None:
        """
        Initiates background loop for MQTT tracking over the provided topics.
        """
        self._subscribed_topics = topics
        self._on_tpcp_message_callback = on_message_callback
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            logger.info(f"MQTT Adapter connecting to broker at {self.broker_host}:{self.broker_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✓ Connected to MQTT Broker.")
            for topic in self._subscribed_topics:
                self.client.subscribe(topic)
                logger.debug(f"Subscribed to MQTT Topic: {topic}")
        else:
            logger.error(f"MQTT Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        """Standard MQTT Paho Callback. Safely bridges execution cleanly to TPCP."""
        if not self._on_tpcp_message_callback:
            return
            
        try:
            decoded_payload = msg.payload.decode('utf-8')
            raw_output = {
                "topic": msg.topic,
                "payload": decoded_payload
            }
            
            # Broadcast by default
            envelope = self.pack_thought(UUID(int=0), raw_output, Intent.STATE_SYNC)
            
            # Bridge to TPCP network event loop seamlessly
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._on_tpcp_message_callback, envelope)
        except Exception as e:
            logger.warning(f"Error packing MQTT message for TPCP bridge: {e}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker (code: {rc}). Broker connection loop handles reconnect automatically.")

    def stop(self):
        """Teardown background Paho-MQTT Thread and cleanly disconnect."""
        self.client.loop_stop()
        self.client.disconnect()
