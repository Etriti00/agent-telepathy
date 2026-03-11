import pytest
import asyncio
from uuid import uuid4

from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
from tpcp.core.node import TPCPNode

@pytest.mark.asyncio
async def test_node_initialization():
    identity = AgentIdentity(framework="NodeTest", public_key="test_key")
    node = TPCPNode(identity=identity, host="127.0.0.1", port=9000)
    
    assert node.host == "127.0.0.1"
    assert node.port == 9000
    assert node.identity == identity
    assert len(node.peer_registry) == 0

@pytest.mark.asyncio
async def test_peer_registration():
    identity = AgentIdentity(framework="NodeTest", public_key="test_key")
    node = TPCPNode(identity=identity, host="127.0.0.1", port=9000)
    
    peer_identity = AgentIdentity(framework="PeerTest", public_key="peer_key")
    peer_address = "ws://127.0.0.1:9001"
    
    node.register_peer(peer_identity, peer_address)
    assert peer_identity.agent_id in node.peer_registry
    
    node.remove_peer(peer_identity.agent_id)
    assert peer_identity.agent_id not in node.peer_registry

@pytest.mark.asyncio
async def test_message_sending_unknown_peer():
    identity = AgentIdentity(framework="NodeTest", public_key="test_key")
    node = TPCPNode(identity=identity, host="127.0.0.1", port=9000)
    
    target_id = uuid4()
    await node.send_message(
        target_id=target_id,
        intent=Intent.TASK_REQUEST,
        payload=TextPayload(content="test")
    )
    
    assert await node.message_queue.has_messages(target_id)
