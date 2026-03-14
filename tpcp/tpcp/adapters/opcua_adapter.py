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
TPCP adapter for OPC-UA industrial automation protocol.

OPC-UA is the dominant OT/IT convergence standard used in manufacturing (Siemens,
ABB, Bosch). This adapter bridges OPC-UA data change subscriptions into the TPCP
agent swarm as TelemetryPayload envelopes.

Requires: pip install tpcp-core[industrial]
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import (
    AgentIdentity, BinaryPayload, Intent, TelemetryPayload, TelemetryReading,
    TPCPEnvelope,
)

# Threshold above which a bytes/bytearray OPC-UA value is returned as BinaryPayload.
# Callers that need chunked transfer should pass the result through
# tpcp.core.chunker.send_chunked().
_BINARY_THRESHOLD_BYTES = 65536

try:
    from asyncua import Client as OPCUAClient
    from asyncua import ua
    OPCUA_AVAILABLE = True
except ImportError:
    OPCUA_AVAILABLE = False

logger = logging.getLogger(__name__)


class OPCUAAdapter(BaseFrameworkAdapter):
    """
    Bridges OPC-UA data change subscriptions into TPCP TelemetryPayload envelopes.

    Usage::

        adapter = OPCUAAdapter(
            agent_identity=identity,
            server_url="opc.tcp://plc.factory.local:4840",
        )
        await adapter.start_subscription(
            node_ids=["ns=2;i=2", "ns=2;i=3"],
            on_message_callback=my_tpcp_callback,
        )
    """

    def __init__(
        self,
        server_url: str,
        agent_identity: Optional[AgentIdentity] = None,
        subscription_interval_ms: int = 500,
        identity_manager=None,
    ) -> None:
        if agent_identity is None:
            agent_identity = AgentIdentity(framework="OPCUAAdapter", public_key="")
        super().__init__(agent_identity, identity_manager)
        if not OPCUA_AVAILABLE:
            raise ImportError(
                "asyncua is required for OPCUAAdapter. "
                "Install it with: pip install tpcp-core[industrial]"
            )
        self.server_url = server_url
        self.subscription_interval_ms = subscription_interval_ms
        self._client: Optional[Any] = None

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Dict[str, Any],
        intent: Intent = Intent.STATE_SYNC,
    ) -> TPCPEnvelope:
        """
        Convert an OPC-UA DataChange notification into a TPCP payload envelope.

        For scalar numeric/bool values returns a TelemetryPayload.
        For ``bytes`` or ``bytearray`` values returns a BinaryPayload with the
        data base64-encoded and the OPC-UA node_id in the description field.

        Note: for large binary values callers should decode the BinaryPayload and
        pass the raw bytes to ``tpcp.core.chunker.send_chunked()`` for chunked delivery.

        Args:
            raw_output: Dict with keys:
                - "node_id" (str): OPC-UA NodeId string
                - "value" (float|int|bool|bytes|bytearray): The data value
                - "timestamp_ms" (int): Unix epoch milliseconds
                - "quality" (str, optional): "Good", "Bad", or "Uncertain"
                - "unit" (str, optional): Engineering unit for numeric values
        """
        self._logical_clock += 1
        node_id = str(raw_output.get("node_id", "unknown"))
        value = raw_output.get("value", 0.0)

        # --- Binary branch: bytes / bytearray values ---
        if isinstance(value, (bytes, bytearray)):
            data_b64 = base64.b64encode(bytes(value)).decode("ascii")
            payload: Union[BinaryPayload, TelemetryPayload] = BinaryPayload(
                data_base64=data_b64,
                mime_type="application/octet-stream",
                description=f"opcua:{node_id}",
            )
            header = self._create_header(receiver_id=target_id, intent=intent)
            envelope = TPCPEnvelope(header=header, payload=payload)
            if self.identity_manager:
                envelope.signature = self.identity_manager.sign_payload(payload.model_dump())
            return envelope

        # --- Numeric / scalar branch ---
        sensor_id = "opcua_" + node_id.replace(":", "_").replace(";", "_").replace("=", "_")
        reading = TelemetryReading(
            value=float(value),
            timestamp_ms=int(raw_output.get("timestamp_ms", 0)),
            quality=raw_output.get("quality"),
        )
        payload = TelemetryPayload(
            sensor_id=sensor_id,
            unit=raw_output.get("unit", ""),
            readings=[reading],
            source_protocol="opcua",
        )
        header = self._create_header(receiver_id=target_id, intent=intent)
        envelope = TPCPEnvelope(header=header, payload=payload)
        if self.identity_manager:
            envelope.signature = self.identity_manager.sign_payload(payload.model_dump())
        return envelope

    def unpack_request(self, envelope: TPCPEnvelope) -> Dict[str, Any]:
        """
        Translate a TPCP TASK_REQUEST envelope into an OPC-UA write command.

        Returns a dict with keys: "node_id", "value".  Pass the result to
        ``execute_write()`` to perform the actual OPC-UA node write::

            cmd = adapter.unpack_request(envelope)
            await adapter.execute_write(cmd)

        Expected TextPayload content: JSON string like {"node_id": "ns=2;i=2", "value": 42}
        """
        if hasattr(envelope.payload, "content"):
            try:
                return json.loads(envelope.payload.content)
            except (json.JSONDecodeError, AttributeError):
                return {"raw": envelope.payload.content}
        return {}

    async def execute_write(self, write_cmd: Dict[str, Any]) -> bool:
        """
        Write a value to an OPC-UA node.

        If ``start_subscription()`` has already been called the existing
        ``self._client`` connection is reused.  Otherwise a short-lived
        connection is opened for the write and disconnected in a ``finally``
        block, ensuring no connection leak.

        Use after ``unpack_request()``::

            cmd = adapter.unpack_request(envelope)
            await adapter.execute_write(cmd)

        Args:
            write_cmd: Dict with keys:
                - "node_id" (str): OPC-UA NodeId string, e.g. "ns=2;i=2"
                - "value": Value to write (int, float, bool, etc.)

        Returns:
            True if the write succeeded, False otherwise.
        """
        if not write_cmd.get("node_id"):
            logger.error("[OPCUAAdapter] execute_write called with missing node_id")
            return False

        # Reuse an existing subscription client if available.
        if self._client is not None:
            try:
                node = self._client.get_node(write_cmd["node_id"])
                await node.write_value(write_cmd["value"])
                logger.debug(
                    f"[OPCUAAdapter] Wrote {write_cmd['value']!r} to {write_cmd['node_id']}"
                )
                return True
            except Exception as exc:
                logger.error(f"[OPCUAAdapter] execute_write failed: {exc}")
                return False

        # No existing connection — open a transient one and always close it.
        client = OPCUAClient(self.server_url)
        try:
            await client.connect()
            logger.info(f"[OPCUAAdapter] Transient connection to {self.server_url} for write")
            node = client.get_node(write_cmd["node_id"])
            await node.write_value(write_cmd["value"])
            logger.debug(
                f"[OPCUAAdapter] Wrote {write_cmd['value']!r} to {write_cmd['node_id']}"
            )
            return True
        except Exception as exc:
            logger.error(f"[OPCUAAdapter] execute_write failed: {exc}")
            return False
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def start_subscription(
        self,
        node_ids: List[str],
        on_message_callback: Callable[[TPCPEnvelope, UUID], None],
        target_id: Optional[UUID] = None,
    ) -> None:
        """
        Connect to the OPC-UA server and subscribe to data change notifications.

        Args:
            node_ids: List of OPC-UA NodeId strings to subscribe to.
            on_message_callback: Called with (envelope, target_id) for each data change.
            target_id: UUID to use as receiver_id in envelopes (defaults to BROADCAST_UUID).
        """
        from tpcp.core.node import BROADCAST_UUID
        effective_target = target_id or BROADCAST_UUID

        # Disconnect any existing client before creating a new one to avoid
        # leaking TCP connections on repeated calls to start_subscription().
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

        self._client = OPCUAClient(self.server_url)
        await self._client.connect()
        logger.info(f"[OPCUAAdapter] Connected to {self.server_url}")

        handler = _OPCUASubscriptionHandler(
            adapter=self,
            target_id=effective_target,
            callback=on_message_callback,
        )
        subscription = await self._client.create_subscription(
            self.subscription_interval_ms, handler
        )
        nodes = [self._client.get_node(nid) for nid in node_ids]
        await subscription.subscribe_data_change(nodes)
        logger.info(f"[OPCUAAdapter] Subscribed to {len(node_ids)} nodes")


class _OPCUASubscriptionHandler:
    """Internal handler for OPC-UA subscription data change callbacks."""

    def __init__(self, adapter: OPCUAAdapter, target_id: UUID, callback: Callable):
        self.adapter = adapter
        self.target_id = target_id
        self.callback = callback

    async def datachange_notification(self, node, val, data):
        """Called by asyncua when a subscribed node's value changes."""
        import time
        try:
            node_id = str(node)
            raw_output = {
                "node_id": node_id,
                "value": val,
                "timestamp_ms": int(time.time() * 1000),
            }
            if hasattr(data, "monitored_item") and hasattr(data.monitored_item, "Value"):
                sv = data.monitored_item.Value
                if hasattr(sv, "StatusCode") and sv.StatusCode is not None:
                    code = sv.StatusCode.name if hasattr(sv.StatusCode, "name") else str(sv.StatusCode)
                    if "Good" in code:
                        raw_output["quality"] = "Good"
                    elif "Bad" in code:
                        raw_output["quality"] = "Bad"
                    else:
                        raw_output["quality"] = "Uncertain"
            envelope = self.adapter.pack_thought(self.target_id, raw_output, Intent.MEDIA_SHARE)
            self.callback(envelope, self.target_id)
        except Exception as exc:
            logger.error(f"[OPCUAAdapter] Error in datachange_notification: {exc}")
