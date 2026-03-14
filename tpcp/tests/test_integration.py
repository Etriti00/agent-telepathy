"""
Integration tests: full 2-node TPCP handshake and message round-trip over real WebSocket.
"""
import asyncio
import pytest

from tpcp.core.node import TPCPNode
from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


def make_agent(port: int, name: str):
    """Create a TPCPNode with a real Ed25519 identity."""
    im = AgentIdentityManager()
    identity = AgentIdentity(
        framework=name,
        public_key=im.get_public_key_string()
    )
    return TPCPNode(identity=identity, host="127.0.0.1", port=port, identity_manager=im)


@pytest.mark.asyncio
async def test_two_node_handshake_and_message():
    """
    Two nodes start listening, exchange handshakes, then node_a sends a
    TASK_REQUEST to node_b, which receives and routes it correctly.
    """
    node_a = make_agent(19200, "AgentA")
    node_b = make_agent(19201, "AgentB")

    received = []

    async def on_task(envelope, ws):
        received.append(envelope)

    node_b.register_handler(Intent.TASK_REQUEST, on_task)

    async with node_a:
        async with node_b:
            # Handshake: A announces itself to B
            await node_a.broadcast_discovery(seed_nodes=["ws://127.0.0.1:19201"])
            await asyncio.sleep(0.3)  # Let handshake propagate

            # Register B in A's registry (normally done via A-DNS; we do it manually here)
            node_a.register_peer(node_b.identity, "ws://127.0.0.1:19201")

            # Send TASK_REQUEST from A to B
            await node_a.send_message(
                target_id=node_b.identity.agent_id,
                intent=Intent.TASK_REQUEST,
                payload=TextPayload(content="Hello from A")
            )
            await asyncio.sleep(0.3)  # Let message arrive

    assert len(received) == 1, f"Expected 1 message, got {len(received)}"
    assert received[0].header.intent == Intent.TASK_REQUEST
    assert isinstance(received[0].payload, TextPayload)
    assert received[0].payload.content == "Hello from A"


@pytest.mark.asyncio
async def test_two_node_crdt_sync():
    """
    Node A sets a CRDT key, broadcasts it as CRDTSyncPayload to B.
    B receives and merges it into its own shared memory.
    """
    from tpcp.schemas.envelope import CRDTSyncPayload

    node_a = make_agent(19202, "SyncA")
    node_b = make_agent(19203, "SyncB")

    async with node_a:
        async with node_b:
            # A sets a value
            await node_a.shared_memory.set("project", "TPCP")

            # Register B in A's peer registry
            node_a.register_peer(node_b.identity, "ws://127.0.0.1:19203")
            # Register A in B's peer registry (needed so B accepts the signed message)
            node_b.register_peer(node_a.identity, "ws://127.0.0.1:19202")

            # A sends CRDT state sync to B
            state = node_a.shared_memory.serialize_state()
            payload = CRDTSyncPayload(
                crdt_type="LWW-Map",
                state=state,
                vector_clock={str(node_a.identity.agent_id): node_a.shared_memory.logical_clock}
            )
            await node_a.send_message(
                target_id=node_b.identity.agent_id,
                intent=Intent.STATE_SYNC,
                payload=payload
            )
            await asyncio.sleep(0.3)

    assert node_b.shared_memory.get("project") == "TPCP"
