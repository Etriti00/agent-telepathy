import pytest
import asyncio
from uuid import uuid4

from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
from tpcp.core.node import TPCPNode
from tpcp.security.crypto import AgentIdentityManager


def make_node(port: int) -> TPCPNode:
    """Helper to create a TPCPNode with a real Ed25519 identity."""
    identity_manager = AgentIdentityManager()
    identity = AgentIdentity(
        framework="NodeTest",
        public_key=identity_manager.get_public_key_string()
    )
    node = TPCPNode(identity=identity, host="127.0.0.1", port=port)
    return node


@pytest.mark.asyncio
async def test_node_initialization():
    node = make_node(9000)
    
    assert node.host == "127.0.0.1"
    assert node.port == 9000
    assert len(node.peer_registry) == 0
    # Node should have auto-generated a real Ed25519 public key
    assert len(node.identity.public_key) > 0
    assert node.identity.public_key != "test_key"


@pytest.mark.asyncio
async def test_peer_registration():
    node = make_node(9000)
    
    peer_manager = AgentIdentityManager()
    peer_identity = AgentIdentity(
        framework="PeerTest",
        public_key=peer_manager.get_public_key_string()
    )
    peer_address = "ws://127.0.0.1:9001"
    
    node.register_peer(peer_identity, peer_address)
    assert peer_identity.agent_id in node.peer_registry
    
    node.remove_peer(peer_identity.agent_id)
    assert peer_identity.agent_id not in node.peer_registry


@pytest.mark.asyncio
async def test_message_sending_unknown_peer():
    """Messages to unknown peers must be enqueued to the DLQ, not dropped silently."""
    node = make_node(9000)
    
    target_id = uuid4()
    await node.send_message(
        target_id=target_id,
        intent=Intent.TASK_REQUEST,
        payload=TextPayload(content="test")
    )
    
    assert await node.message_queue.has_messages(target_id)


@pytest.mark.asyncio
async def test_dlq_max_size_eviction():
    """DLQ should not grow indefinitely — oldest messages are evicted when full."""
    from tpcp.core.queue import MessageQueue
    from tpcp.schemas.envelope import MessageHeader, TPCPEnvelope, TextPayload
    
    queue = MessageQueue(max_size_per_peer=3)
    target_id = uuid4()
    
    node = make_node(9000)
    
    for i in range(5):
        payload = TextPayload(content=f"msg {i}")
        header = MessageHeader(
            sender_id=node.identity.agent_id,
            receiver_id=target_id,
            intent=Intent.TASK_REQUEST
        )
        envelope = TPCPEnvelope(header=header, payload=payload)
        await queue.enqueue(target_id, envelope)
    
    # After 5 enqueues with max_size=3, only 3 most recent should remain
    messages = await queue.drain(target_id)
    assert len(messages) == 3
