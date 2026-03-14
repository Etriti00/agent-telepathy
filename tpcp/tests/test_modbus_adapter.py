"""
Tests for ModbusAdapter using a pymodbus TCP server with in-memory datastore.

Uses StartAsyncTcpServer + ModbusDeviceContext so no external PLC hardware
or aiohttp (ModbusSimulatorServer dependency) is required.

Two server fixtures run on different ports (50200, 50201) so sequential
function-scoped teardown/setup never races over the same port.
"""
import asyncio
import pytest

pytest.importorskip("pymodbus", reason="pymodbus not installed; skip Modbus tests")

from pymodbus.server import StartAsyncTcpServer  # type: ignore
from pymodbus.datastore import (  # type: ignore
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
from tpcp.adapters.modbus_adapter import ModbusAdapter
from tpcp.schemas.envelope import TelemetryPayload

_MODBUS_HOST = "127.0.0.1"


async def _start_server(host: str, port: int):
    """Start a pymodbus TCP server; return (context, task)."""
    store = ModbusDeviceContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),
        co=ModbusSequentialDataBlock(0, [0] * 100),
        hr=ModbusSequentialDataBlock(0, [17] * 100),
        ir=ModbusSequentialDataBlock(0, [0] * 100),
    )
    context = ModbusServerContext(devices=store, single=True)
    task = asyncio.get_event_loop().create_task(
        StartAsyncTcpServer(context=context, address=(host, port))
    )
    await asyncio.sleep(0.3)
    return task


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
async def modbus_server_50200():
    """In-process pymodbus server on port 50200 for poll tests."""
    task = await _start_server(_MODBUS_HOST, 50200)
    yield (_MODBUS_HOST, 50200)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


@pytest.fixture()
async def modbus_server_50201():
    """In-process pymodbus server on port 50201 for drain-queue tests."""
    task = await _start_server(_MODBUS_HOST, 50201)
    yield (_MODBUS_HOST, 50201)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_poll_holding_registers_produces_telemetry(modbus_server_50200):
    """Polling holding registers must yield TelemetryPayload envelopes."""
    host, port = modbus_server_50200
    adapter = ModbusAdapter(host=host, port=port, unit_id=1)
    received = []

    def callback(envelope, target_id):
        received.append(envelope)

    await adapter.connect()
    try:
        await adapter.poll_registers(
            register_type="holding",
            start_address=0,
            count=4,
            on_message_callback=callback,
            max_polls=1,
        )
    finally:
        await adapter.disconnect()

    assert len(received) >= 1
    env = received[0]
    assert isinstance(env.payload, TelemetryPayload)
    assert env.payload.payload_type == "telemetry"
    assert env.payload.source_protocol == "modbus"


async def test_retry_queue_bounded():
    """Writes queued when disconnected are capped at max_retry_queue entries."""
    adapter = ModbusAdapter(host=_MODBUS_HOST, port=50299, unit_id=1)
    # Don't connect — all writes should be queued.
    for i in range(adapter._max_retry_queue + 20):
        await adapter.execute_write({"address": 0, "value": i, "type": "holding"})

    # Queue must not exceed the declared maximum.
    assert len(adapter._retry_queue) == adapter._max_retry_queue


async def test_drain_retry_queue(modbus_server_50201):
    """drain_retry_queue flushes queued write commands once connected."""
    host, port = modbus_server_50201
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
