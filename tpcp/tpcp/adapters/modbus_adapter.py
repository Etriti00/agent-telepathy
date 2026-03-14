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
TPCP adapter for Modbus TCP industrial protocol.

Modbus TCP is the dominant legacy protocol for industrial PLCs and controllers.
This adapter polls Modbus registers and publishes readings as TelemetryPayload envelopes.

Requires: pip install tpcp-core[industrial]
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import (
    AgentIdentity, Intent, TelemetryPayload, TelemetryReading, TextPayload, TPCPEnvelope
)

try:
    from pymodbus.client import AsyncModbusTcpClient
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModbusAdapter(BaseFrameworkAdapter):
    """
    Polls Modbus TCP registers and publishes readings as TPCP TelemetryPayload envelopes.

    Modbus has no push model — this adapter polls on a configurable interval.

    Usage::

        adapter = ModbusAdapter(
            agent_identity=identity,
            host="192.168.1.100",
            port=502,
            unit_id=1,
        )
        await adapter.poll_registers(
            register_type="holding",
            start_address=0,
            count=10,
            interval_seconds=1.0,
            on_message_callback=my_callback,
        )
    """

    def __init__(
        self,
        agent_identity: AgentIdentity,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        identity_manager=None,
    ) -> None:
        super().__init__(agent_identity, identity_manager)
        if not MODBUS_AVAILABLE:
            raise ImportError(
                "pymodbus is required for ModbusAdapter. "
                "Install it with: pip install tpcp-core[industrial]"
            )
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._client: Optional[Any] = None
        self._retry_queue: list = []

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Dict[str, Any],
        intent: Intent = Intent.STATE_SYNC,
    ) -> TPCPEnvelope:
        """
        Convert a Modbus register read result into a TelemetryPayload envelope.

        Args:
            raw_output: Dict with keys:
                - "register_type" (str): "coil", "discrete", "input", or "holding"
                - "address" (int): Register address
                - "value" (float|int): Register value
                - "unit_id" (int, optional): Modbus unit ID
                - "timestamp_ms" (int): Unix epoch milliseconds
        """
        self._logical_clock += 1
        reg_type = raw_output.get("register_type", "holding")
        address = raw_output.get("address", 0)
        uid = raw_output.get("unit_id", self.unit_id)
        sensor_id = f"modbus_{uid}_{reg_type}_{address}"

        reading = TelemetryReading(
            value=float(raw_output.get("value", 0.0)),
            timestamp_ms=int(raw_output.get("timestamp_ms", 0)),
        )
        payload = TelemetryPayload(
            sensor_id=sensor_id,
            unit=raw_output.get("unit", ""),
            readings=[reading],
            source_protocol="modbus",
        )
        header = self._create_header(receiver_id=target_id, intent=intent)
        envelope = TPCPEnvelope(header=header, payload=payload)
        if self.identity_manager:
            envelope.signature = self.identity_manager.sign_payload(payload.model_dump())
        return envelope

    def unpack_request(self, envelope: TPCPEnvelope) -> Dict[str, Any]:
        """
        Translate a TPCP TASK_REQUEST into a Modbus write command dict.

        Expected TextPayload content: JSON like {"address": 100, "value": 1, "type": "coil"}
        The caller is responsible for executing the write via execute_write().
        """
        if hasattr(envelope.payload, "content"):
            try:
                return json.loads(envelope.payload.content)
            except (json.JSONDecodeError, AttributeError):
                return {"raw": envelope.payload.content}
        return {}

    async def execute_write(self, write_cmd: Dict[str, Any]) -> bool:
        """
        Execute a Modbus write command.

        Args:
            write_cmd: Dict with "address", "value", "type" ("coil" or "holding").

        Returns:
            True if successful, False otherwise.
        """
        if not self._client or not self._client.connected:
            logger.error("[ModbusAdapter] Not connected — cannot write")
            return False
        try:
            cmd_type = write_cmd.get("type", "holding")
            address = int(write_cmd["address"])
            value = write_cmd["value"]
            if cmd_type == "coil":
                await self._client.write_coil(address, bool(value), unit=self.unit_id)
            else:
                await self._client.write_register(address, int(value), unit=self.unit_id)
            return True
        except Exception as exc:
            logger.error(f"[ModbusAdapter] Write failed: {exc}")
            self._retry_queue.append(write_cmd)
            return False

    async def poll_registers(
        self,
        register_type: str,
        start_address: int,
        count: int,
        interval_seconds: float,
        on_message_callback: Callable[[TPCPEnvelope, UUID], None],
        target_id: Optional[UUID] = None,
    ) -> None:
        """
        Connect to the Modbus device and poll registers on a fixed interval.

        Args:
            register_type: "coil", "discrete", "input", or "holding"
            start_address: Starting register address.
            count: Number of registers to read.
            interval_seconds: Polling interval.
            on_message_callback: Called with (envelope, target_id) per poll.
            target_id: Receiver UUID (defaults to BROADCAST_UUID).
        """
        import time
        from tpcp.core.node import BROADCAST_UUID
        effective_target = target_id or BROADCAST_UUID

        self._client = AsyncModbusTcpClient(self.host, port=self.port)
        await self._client.connect()
        logger.info(f"[ModbusAdapter] Connected to {self.host}:{self.port} unit={self.unit_id}")

        while True:
            try:
                timestamp_ms = int(time.time() * 1000)
                for offset in range(count):
                    address = start_address + offset
                    try:
                        if register_type in ("coil", "discrete"):
                            result = await self._client.read_coils(address, 1, unit=self.unit_id)
                            value = result.bits[0] if result and not result.isError() else 0
                        else:
                            result = await self._client.read_holding_registers(
                                address, 1, unit=self.unit_id
                            )
                            value = result.registers[0] if result and not result.isError() else 0

                        raw_output = {
                            "register_type": register_type,
                            "address": address,
                            "value": value,
                            "unit_id": self.unit_id,
                            "timestamp_ms": timestamp_ms,
                        }
                        envelope = self.pack_thought(
                            effective_target, raw_output, Intent.MEDIA_SHARE
                        )
                        on_message_callback(envelope, effective_target)

                    except Exception as exc:
                        logger.warning(
                            f"[ModbusAdapter] Error reading {register_type}[{address}]: {exc}"
                        )

            except Exception as exc:
                logger.error(f"[ModbusAdapter] Poll cycle failed: {exc}")

            await asyncio.sleep(interval_seconds)
