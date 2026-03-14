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
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import (
    AgentIdentity, Intent, TelemetryPayload, TelemetryReading, TPCPEnvelope
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
        host: str,
        port: int = 502,
        unit_id: int = 1,
        agent_identity: Optional[AgentIdentity] = None,
        identity_manager=None,
    ) -> None:
        if agent_identity is None:
            agent_identity = AgentIdentity(framework="ModbusAdapter", public_key="")
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
        self._max_retry_queue: int = 100  # prevent unbounded growth during long outages

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

        Returns the parsed command dict.  Pass the result to ``execute_write()``
        to perform the actual register write::

            cmd = adapter.unpack_request(envelope)
            await adapter.execute_write(cmd)

        Expected TextPayload content: JSON like {"address": 100, "value": 1, "type": "coil"}
        """
        if hasattr(envelope.payload, "content"):
            try:
                return json.loads(envelope.payload.content)
            except (json.JSONDecodeError, AttributeError):
                return {"raw": envelope.payload.content}
        return {}

    async def _do_write(self, write_cmd: Dict[str, Any]) -> None:
        """
        Execute a single Modbus write against the active client connection.

        Raises on any pymodbus error so callers can distinguish success from failure.

        Args:
            write_cmd: Dict with "address", "value", and optional
                "type" ("coil" or "holding", default "holding").
        """
        cmd_type = write_cmd.get("type", "holding")
        address = int(write_cmd["address"])
        value = write_cmd["value"]
        if cmd_type == "coil":
            await self._client.write_coil(address, bool(value), slave=self.unit_id)
        else:
            await self._client.write_register(address, int(value), slave=self.unit_id)

    async def execute_write(self, write_cmd: Dict[str, Any]) -> bool:
        """
        Execute a Modbus write command, retrying any previously queued failures first.

        If not connected, the command is added to the retry queue and False is returned.
        When a write succeeds, ``drain_retry_queue()`` runs first to replay any commands
        queued during earlier connection drops.

        Args:
            write_cmd: Dict with "address", "value", "type" ("coil" or "holding").

        Returns:
            True if the write succeeded, False otherwise.
        """
        if not self._client or not self._client.connected:
            logger.error("[ModbusAdapter] Not connected — cannot write; queuing command")
            if len(self._retry_queue) < self._max_retry_queue:
                self._retry_queue.append(write_cmd)
            else:
                logger.warning("[ModbusAdapter] Retry queue full — dropping write command")
            return False
        try:
            await self.drain_retry_queue()
            await self._do_write(write_cmd)
            return True
        except Exception as exc:
            logger.error(f"[ModbusAdapter] Write failed: {exc}")
            if len(self._retry_queue) < self._max_retry_queue:
                self._retry_queue.append(write_cmd)
            else:
                logger.warning("[ModbusAdapter] Retry queue full — dropping write command")
            return False

    async def drain_retry_queue(self) -> int:
        """
        Retry all previously failed write commands.

        Iterates through ``_retry_queue``, attempts each write via ``_do_write()``,
        and removes successful ones.  Commands that still fail remain in the queue.

        Called automatically at the start of each ``execute_write()`` call, and may
        also be called explicitly after re-establishing a connection.

        Returns:
            Number of commands successfully retried and removed from the queue.
        """
        if not self._retry_queue:
            return 0
        remaining = []
        retried = 0
        for cmd in list(self._retry_queue):
            try:
                await self._do_write(cmd)
                retried += 1
                logger.debug(f"[ModbusAdapter] Retried queued write: {cmd}")
            except Exception as exc:
                logger.warning(f"[ModbusAdapter] Queued write still failing: {exc}")
                remaining.append(cmd)
        self._retry_queue = remaining
        return retried

    async def connect(self) -> None:
        """Open a Modbus TCP connection to the device."""
        self._client = AsyncModbusTcpClient(self.host, port=self.port)
        await self._client.connect()
        logger.info(f"[ModbusAdapter] Connected to {self.host}:{self.port} unit={self.unit_id}")

    async def disconnect(self) -> None:
        """Close the Modbus TCP connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("[ModbusAdapter] Disconnected")

    async def poll_registers(
        self,
        register_type: str,
        start_address: int,
        count: int,
        interval_seconds: float = 1.0,
        on_message_callback: Optional[Callable[[TPCPEnvelope, UUID], None]] = None,
        callback: Optional[Callable[[TPCPEnvelope], None]] = None,
        target_id: Optional[UUID] = None,
        max_polls: Optional[int] = None,
    ) -> None:
        """
        Connect to the Modbus device and poll registers on a fixed interval.

        Args:
            register_type: "coil", "discrete", "input", or "holding"
            start_address: Starting register address.
            count: Number of registers to read.
            interval_seconds: Polling interval in seconds (default 1.0).
            on_message_callback: Called with (envelope, target_id) per poll.
            callback: Alias for on_message_callback accepting (envelope,) only.
            target_id: Receiver UUID (defaults to BROADCAST_UUID).
            max_polls: Stop after this many poll cycles (None = run forever).
        """
        import time
        from tpcp.core.node import BROADCAST_UUID
        effective_target = target_id or BROADCAST_UUID

        # Support both callback styles; on_message_callback takes priority.
        _cb = on_message_callback
        if _cb is None and callback is not None:
            def _cb(env, _tid):  # type: ignore[misc]
                callback(env)  # type: ignore[misc]

        if self._client is None:
            self._client = AsyncModbusTcpClient(self.host, port=self.port)
            await self._client.connect()
            logger.info(f"[ModbusAdapter] Connected to {self.host}:{self.port} unit={self.unit_id}")

        polls = 0
        while max_polls is None or polls < max_polls:
            try:
                timestamp_ms = int(time.time() * 1000)
                for offset in range(count):
                    address = start_address + offset
                    try:
                        read_ok = False
                        value = 0
                        if register_type in ("coil", "discrete"):
                            result = await self._client.read_coils(address, 1, slave=self.unit_id)
                            if result and not result.isError():
                                value = result.bits[0]
                                read_ok = True
                        else:
                            result = await self._client.read_holding_registers(
                                address, 1, slave=self.unit_id
                            )
                            if result and not result.isError():
                                value = result.registers[0]
                                read_ok = True

                        if not read_ok:
                            logger.warning(
                                f"[ModbusAdapter] Read error {register_type}[{address}] "
                                f"— skipping (not emitting a zero placeholder)"
                            )
                            continue

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
                        if _cb is not None:
                            result = _cb(envelope, effective_target)
                            if inspect.iscoroutine(result):
                                await result

                    except Exception as exc:
                        logger.warning(
                            f"[ModbusAdapter] Error reading {register_type}[{address}]: {exc}"
                        )

            except Exception as exc:
                logger.error(f"[ModbusAdapter] Poll cycle failed: {exc}")

            polls += 1
            if max_polls is None or polls < max_polls:
                await asyncio.sleep(interval_seconds)
