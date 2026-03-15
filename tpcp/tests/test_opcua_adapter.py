"""
Tests for OPCUAAdapter using the asyncua built-in server.

The asyncua library ships a Server class that can run entirely in-process, so no
external OPC-UA infrastructure is required.
"""
import pytest

pytest.importorskip("asyncua", reason="asyncua not installed; skip OPC-UA tests")

from asyncua import Server as OPCUAServer, ua  # type: ignore
from tpcp.adapters.opcua_adapter import OPCUAAdapter
from tpcp.schemas.envelope import TelemetryPayload, BinaryPayload


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _build_server(url: str):
    """Spin up a minimal asyncua server, add one numeric and one bytes node."""
    from asyncua.crypto.permission_rules import PermissionRuleset  # type: ignore

    class _AllowAll(PermissionRuleset):
        """Permissive ruleset for test servers: every operation is allowed."""
        def check_validity(self, user, action_type_id, body):
            return True

    server = OPCUAServer()
    await server.init()
    server.set_endpoint(url)
    # Pass _AllowAll so SecurityPolicyNone.permissions is set to a ruleset that
    # always returns True, bypassing the default SimpleRoleRuleset RBAC check
    # that denies anonymous-client writes.  asyncua.crypto.__init__ is empty
    # so no crypto extras are required to import asyncua.crypto.permission_rules.
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity], permission_ruleset=_AllowAll())
    uri = "urn:tpcp:test"
    idx = await server.register_namespace(uri)
    objects = server.nodes.objects
    numeric_node = await objects.add_variable(idx, "Temperature", 42.0)
    await numeric_node.set_writable()
    bytes_node = await objects.add_variable(idx, "RawFrame", b"\x01\x02\x03")
    await bytes_node.set_writable()
    return server, idx


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pack_thought_telemetry():
    """pack_thought converts a numeric DataChange to a TelemetryPayload."""
    from uuid import uuid4
    url = "opc.tcp://127.0.0.1:4841/tpcp-test"
    server, idx = await _build_server(url)
    async with server:
        adapter = OPCUAAdapter(server_url=url)
        envelope = adapter.pack_thought(
            target_id=uuid4(),
            raw_output={
                "node_id": f"ns={idx};s=Temperature",
                "value": 98.6,
                "timestamp_ms": 1000,
            },
        )
        assert envelope is not None
        assert isinstance(envelope.payload, TelemetryPayload)
        assert envelope.payload.payload_type == "telemetry"
        assert envelope.payload.source_protocol == "opcua"
        assert len(envelope.payload.readings) == 1
        assert envelope.payload.readings[0].value == pytest.approx(98.6)


@pytest.mark.asyncio
async def test_pack_thought_binary():
    """pack_thought converts a bytes DataChange value to a BinaryPayload."""
    from uuid import uuid4
    url = "opc.tcp://127.0.0.1:4842/tpcp-test"
    server, idx = await _build_server(url)
    async with server:
        adapter = OPCUAAdapter(server_url=url)
        envelope = adapter.pack_thought(
            target_id=uuid4(),
            raw_output={
                "node_id": f"ns={idx};s=RawFrame",
                "value": b"\xDE\xAD\xBE\xEF",
                "timestamp_ms": 1000,
            },
        )
        assert envelope is not None
        assert isinstance(envelope.payload, BinaryPayload)
        assert envelope.payload.payload_type == "binary"
        assert envelope.payload.mime_type == "application/octet-stream"


@pytest.mark.asyncio
async def test_execute_write_connects_and_disconnects():
    """execute_write opens a transient connection, writes the value, and always disconnects."""
    url = "opc.tcp://127.0.0.1:4843/tpcp-test"
    server, idx = await _build_server(url)
    async with server:
        adapter = OPCUAAdapter(server_url=url)
        node_id = f"ns={idx};s=Temperature"
        # Retry up to 5 times to avoid startup timing races.
        import asyncio as _asyncio
        success = False
        for _ in range(5):
            success = await adapter.execute_write({"node_id": node_id, "value": 55.5})
            if success:
                break
            await _asyncio.sleep(0.1)
        assert success is True
        # Adapter should not leak an open client after a transient write
        assert adapter._client is None


@pytest.mark.asyncio
async def test_execute_write_bad_node_returns_false():
    """execute_write returns False on a nonexistent node rather than raising."""
    url = "opc.tcp://127.0.0.1:4844/tpcp-test"
    server, _ = await _build_server(url)
    async with server:
        adapter = OPCUAAdapter(server_url=url)
        result = await adapter.execute_write({"node_id": "ns=99;s=DoesNotExist", "value": 0})
        assert result is False
