"""
Tests for ModbusAdapter using the pymodbus ModbusSimulatorServer.

The pymodbus library ships a simulator that runs entirely in-process over a
loopback TCP socket, so no external PLC hardware is required.
"""
import asyncio
import pytest

pytest.importorskip("pymodbus", reason="pymodbus not installed; skip Modbus tests")

from pymodbus.server import ModbusSimulatorServer  # type: ignore
from tpcp.adapters.modbus_adapter import ModbusAdapter
from tpcp.schemas.envelope import TelemetryPayload


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def modbus_server():
    """Start a pymodbus simulator on a random port and yield (host, port)."""
    server = ModbusSimulatorServer(
        modbus_server="127.0.0.1",
        modbus_port=50200,
        http_host="127.0.0.1",
        http_port=50201,
    )
    task = asyncio.create_task(server.run_forever(only_start=True))
    await asyncio.sleep(0.3)   # give server time to bind
    yield ("127.0.0.1", 50200)
    server.stop()
    task.cancel()
    await asyncio.sleep(0.1)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_poll_holding_registers_produces_telemetry(modbus_server):
    """Polling holding registers must yield TelemetryPayload envelopes."""
    host, port = modbus_server
    adapter = ModbusAdapter(host=host, port=port, unit_id=1)
    received = []

    async def callback(envelope):
        received.append(envelope)

    await adapter.connect()
    try:
        await adapter.poll_registers(
            register_type="holding",
            start_address=0,
            count=4,
            callback=callback,
        )
    finally:
        await adapter.disconnect()

    assert len(received) >= 1
    env = received[0]
    assert isinstance(env.payload, TelemetryPayload)
    assert env.payload.payload_type == "telemetry"
    assert env.payload.source_protocol == "modbus"
    assert len(env.payload.readings) == 4


@pytest.mark.asyncio
async def test_retry_queue_bounded():
    """Writes queued when disconnected are capped at max_retry_queue entries."""
    adapter = ModbusAdapter(host="127.0.0.1", port=50299, unit_id=1)
    # Don't connect — all writes should be queued.
    for i in range(adapter._max_retry_queue + 20):
        await adapter.execute_write({"address": 0, "value": i, "type": "holding"})

    # Queue must not exceed the declared maximum.
    assert len(adapter._retry_queue) == adapter._max_retry_queue


@pytest.mark.asyncio
async def test_drain_retry_queue(modbus_server):
    """drain_retry_queue flushes queued write commands once connected."""
    host, port = modbus_server
    adapter = ModbusAdapter(host=host, port=port, unit_id=1)

    # Queue two writes while disconnected.
    adapter._retry_queue.append({"address": 0, "value": 1, "type": "coil"})
    adapter._retry_queue.append({"address": 1, "value": 0, "type": "coil"})
    assert len(adapter._retry_queue) == 2

    await adapter.connect()
    try:
        drained = await adapter.drain_retry_queue()
        assert drained == 2
        assert len(adapter._retry_queue) == 0
    finally:
        await adapter.disconnect()
