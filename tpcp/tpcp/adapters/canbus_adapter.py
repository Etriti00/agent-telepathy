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
TPCP adapter for CANbus automotive/industrial protocol.

CANbus is the dominant protocol in automotive (OBD-II), robotics drivetrains, and
industrial CAN-based sensors. This adapter bridges CAN frames into TPCP TelemetryPayload
envelopes using python-can's async interface.

IMPORTANT: CAN frames arrive at microsecond precision. This adapter uses
asyncio.get_event_loop().call_soon_threadsafe() to bridge from the CAN receive
thread to the asyncio event loop without blocking.

Requires: pip install tpcp-core[industrial]
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import (
    AgentIdentity, Intent, TelemetryPayload, TelemetryReading, TPCPEnvelope
)

try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

logger = logging.getLogger(__name__)


class CANbusAdapter(BaseFrameworkAdapter):
    """
    Bridges CAN bus frames into TPCP TelemetryPayload envelopes.

    Usage::

        adapter = CANbusAdapter(
            agent_identity=identity,
            interface="socketcan",
            channel="can0",
            bitrate=500000,
        )
        await adapter.start_listening(
            can_ids=[0x123, 0x456],  # None = listen to all IDs
            on_message_callback=my_callback,
        )
    """

    def __init__(
        self,
        interface: str,
        channel: str,
        bitrate: int = 500000,
        agent_identity: Optional[AgentIdentity] = None,
        identity_manager=None,
    ) -> None:
        if agent_identity is None:
            agent_identity = AgentIdentity(framework="CANbusAdapter", public_key="")
        super().__init__(agent_identity, identity_manager)
        if not CAN_AVAILABLE:
            raise ImportError(
                "python-can is required for CANbusAdapter. "
                "Install it with: pip install tpcp-core[industrial]"
            )
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self._bus: Optional[Any] = None
        self._running: bool = False
        self._reader_thread: Optional[threading.Thread] = None

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Dict[str, Any],
        intent: Intent = Intent.STATE_SYNC,
    ) -> TPCPEnvelope:
        """
        Convert a CAN frame into a TelemetryPayload envelope.

        Args:
            raw_output: Dict with keys:
                - "arbitration_id" (int): CAN arbitration ID (e.g. 0x123)
                - "data" (list[int]): Frame data bytes
                - "dlc" (int): Data length code
                - "timestamp" (float): CAN frame timestamp
                - "is_extended_id" (bool, optional)
        """
        self._logical_clock += 1
        arb_id = raw_output.get("arbitration_id", 0)
        sensor_id = f"can_{hex(arb_id)}"
        timestamp_ms = int(raw_output.get("timestamp", 0) * 1000)
        # Use the first byte as value if available, or the raw int representation
        data_bytes = raw_output.get("data", [])
        value = float(data_bytes[0]) if data_bytes else 0.0

        reading = TelemetryReading(
            value=value,
            timestamp_ms=timestamp_ms,
        )
        payload = TelemetryPayload(
            sensor_id=sensor_id,
            unit="raw",
            readings=[reading],
            source_protocol="canbus",
        )
        header = self._create_header(receiver_id=target_id, intent=intent)
        envelope = TPCPEnvelope(header=header, payload=payload)
        if self.identity_manager:
            envelope.signature = self.identity_manager.sign_payload(payload.model_dump())
        return envelope

    def unpack_request(self, envelope: TPCPEnvelope) -> Dict[str, Any]:
        """
        Translate a TPCP TASK_REQUEST into a CAN frame send command.

        Expected TextPayload content: JSON like {"arbitration_id": 291, "data": [1, 0, 0]}
        Note: 291 = 0x123.
        The caller is responsible for calling execute_send() with the result.
        """
        if hasattr(envelope.payload, "content"):
            try:
                return json.loads(envelope.payload.content)
            except (json.JSONDecodeError, AttributeError):
                return {"raw": envelope.payload.content}
        return {}

    async def execute_send(self, send_cmd: Dict[str, Any]) -> bool:
        """
        Send a CAN frame.

        Args:
            send_cmd: Dict with "arbitration_id" (int), "data" (list[int]).
        """
        if not self._bus:
            logger.error("[CANbusAdapter] Bus not open — cannot send")
            return False
        try:
            msg = can.Message(
                arbitration_id=int(send_cmd["arbitration_id"]),
                data=bytes(send_cmd["data"]),
                is_extended_id=bool(send_cmd.get("is_extended_id", False)),
            )
            self._bus.send(msg)
            return True
        except Exception as exc:
            logger.error(f"[CANbusAdapter] Send failed: {exc}")
            return False

    async def start_listening(
        self,
        can_ids: Optional[List[int]],
        callback: Callable[[TPCPEnvelope, UUID], None],
        target_id: Optional[UUID] = None,
    ) -> None:
        """
        Open the CAN bus and start receiving frames in a background OS thread.

        Frames are bridged from the blocking CAN receive thread to the asyncio
        event loop via ``loop.call_soon_threadsafe()``, matching the MQTTAdapter
        pattern.  Returns immediately after starting the thread; call
        ``stop_listening()`` to shut down.

        Args:
            can_ids: Allowlist of CAN arbitration IDs to forward.  Pass ``None``
                to receive all IDs (high-traffic bus warning).
            callback: Called with ``(envelope, target_id)`` for each received frame.
            target_id: Receiver UUID for outgoing envelopes (defaults to BROADCAST_UUID).
        """
        from tpcp.core.node import BROADCAST_UUID
        effective_target = target_id or BROADCAST_UUID
        loop = asyncio.get_running_loop()

        self._bus = can.Bus(
            interface=self.interface, channel=self.channel, bitrate=self.bitrate
        )
        self._running = True
        logger.info(
            f"[CANbusAdapter] Opened {self.interface}/{self.channel} at {self.bitrate} bps"
        )

        def _can_reader_thread() -> None:
            """Background thread: blocking CAN recv loop bridged to asyncio."""
            while self._running:
                try:
                    msg = self._bus.recv(timeout=1.0)
                    if msg is None:
                        continue
                    if can_ids is not None and msg.arbitration_id not in can_ids:
                        continue
                    # Bridge from OS thread to asyncio event loop
                    loop.call_soon_threadsafe(
                        lambda m=msg: asyncio.ensure_future(
                            self._dispatch_frame(m, callback, effective_target)
                        )
                    )
                except Exception as exc:
                    loop.call_soon_threadsafe(
                        lambda e=exc: logger.error("[CANbusAdapter] CAN read error: %s", e)
                    )

        self._reader_thread = threading.Thread(
            target=_can_reader_thread, daemon=True, name="canbus-reader"
        )
        self._reader_thread.start()
        logger.info("[CANbusAdapter] CAN reader thread started")

    async def _dispatch_frame(
        self,
        msg: Any,
        callback: Callable[[TPCPEnvelope, UUID], None],
        target_id: UUID,
    ) -> None:
        """
        Dispatch a single CAN frame to the callback as a TelemetryPayload envelope.

        Runs in the asyncio event loop, scheduled via call_soon_threadsafe from the
        CAN reader thread.
        """
        try:
            raw_output = {
                "arbitration_id": msg.arbitration_id,
                "data": list(msg.data),
                "dlc": msg.dlc,
                "timestamp": msg.timestamp,
                "is_extended_id": msg.is_extended_id,
            }
            envelope = self.pack_thought(target_id, raw_output, Intent.MEDIA_SHARE)
            callback(envelope, target_id)
        except Exception as exc:
            logger.error(f"[CANbusAdapter] Dispatch error: {exc}")

    def stop_listening(self) -> None:
        """
        Signal the CAN reader thread to stop and close the bus.

        Sets ``_running = False`` and calls ``bus.shutdown()`` to unblock any
        in-progress ``recv()`` call.  The bus object is kept alive until the
        reader thread observes the flag and exits (at most 1 second), avoiding
        an ``AttributeError`` from the thread accessing ``self._bus`` after it
        has been set to ``None``.
        """
        self._running = False
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception as exc:
                logger.warning(f"[CANbusAdapter] Error during bus shutdown: {exc}")
            # Join the reader thread before clearing the bus reference so the
            # thread cannot dereference self._bus after it becomes None.
            if self._reader_thread is not None and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=2.0)
            self._bus = None
        logger.info("[CANbusAdapter] Stopped listening")
