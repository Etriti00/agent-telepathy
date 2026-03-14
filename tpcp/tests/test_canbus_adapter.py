"""
Tests for CANbusAdapter using python-can's "virtual" interface.

The "virtual" interface creates an in-process loopback bus — no physical CAN
hardware or kernel modules are required.
"""
import asyncio
import pytest

pytest.importorskip("can", reason="python-can not installed; skip CANbus tests")

import can  # type: ignore
from tpcp.adapters.canbus_adapter import CANbusAdapter
from tpcp.schemas.envelope import TelemetryPayload


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pack_thought_produces_telemetry():
    """pack_thought converts a CAN frame dict to a TelemetryPayload."""
    from uuid import uuid4
    adapter = CANbusAdapter(interface="virtual", channel="test_ch1", bitrate=500000)
    envelope = adapter.pack_thought(
        target_id=uuid4(),
        raw_output={
            "arbitration_id": 0x123,
            "data": [0x01, 0x02, 0x03, 0x04],
            "dlc": 4,
            "timestamp": 0.0,
            "is_extended_id": False,
        },
    )
    assert envelope is not None
    assert isinstance(envelope.payload, TelemetryPayload)
    assert envelope.payload.payload_type == "telemetry"
    assert envelope.payload.source_protocol == "canbus"
    assert "0x123" in envelope.payload.sensor_id.lower()
    assert len(envelope.payload.readings) == 1


@pytest.mark.asyncio
async def test_start_and_stop_listening():
    """start_listening spawns a reader thread; stop_listening joins it cleanly."""
    adapter = CANbusAdapter(interface="virtual", channel="test_ch2", bitrate=500000)
    received = []

    def callback(envelope, target_id):
        received.append(envelope)

    await adapter.start_listening(can_ids=[0x100, 0x200], callback=callback)

    # Send a frame from a separate bus on the same virtual channel
    sender = can.interface.Bus(interface="virtual", channel="test_ch2")
    msg = can.Message(arbitration_id=0x100, data=[0xFF], is_extended_id=False)
    sender.send(msg)
    sender.shutdown()

    # Give the reader thread time to receive and dispatch the frame
    await asyncio.sleep(0.2)

    adapter.stop_listening()
    assert adapter._bus is None
    assert not adapter._running

    # At least one envelope should have been received
    assert len(received) >= 1
    assert isinstance(received[0].payload, TelemetryPayload)


@pytest.mark.asyncio
async def test_can_id_filter():
    """Frames whose arbitration_id is not in can_ids must be ignored."""
    adapter = CANbusAdapter(interface="virtual", channel="test_ch3", bitrate=500000)
    received = []

    def callback(envelope, target_id):
        received.append(envelope)

    await adapter.start_listening(can_ids=[0x200], callback=callback)  # only 0x200

    sender = can.interface.Bus(interface="virtual", channel="test_ch3")
    # Send a frame that should be filtered out (0x100 not in can_ids)
    sender.send(can.Message(arbitration_id=0x100, data=[0xAA], is_extended_id=False))
    sender.shutdown()

    await asyncio.sleep(0.2)
    adapter.stop_listening()

    assert len(received) == 0


@pytest.mark.asyncio
async def test_stop_listening_is_idempotent():
    """Calling stop_listening twice must not raise."""
    adapter = CANbusAdapter(interface="virtual", channel="test_ch4", bitrate=500000)
    await adapter.start_listening(can_ids=[], callback=lambda e, t: None)
    adapter.stop_listening()
    adapter.stop_listening()  # second call must be safe
