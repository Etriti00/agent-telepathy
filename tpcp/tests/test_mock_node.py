"""Tests for MockTPCPNode."""
import pytest
from tpcp.testing import MockTPCPNode
from tpcp.schemas.envelope import Intent, TextPayload


def test_connect_pair_creates_linked_nodes():
    alice, bob = MockTPCPNode.connect_pair()
    assert bob.agent_id in alice._peers
    assert alice.agent_id in bob._peers


@pytest.mark.asyncio
async def test_send_and_receive():
    alice, bob = MockTPCPNode.connect_pair()

    received = []
    bob.register_handler(Intent.TASK_REQUEST, lambda env: received.append(env))

    await alice.send_message(bob.agent_id, Intent.TASK_REQUEST, TextPayload(content="hello"))

    assert len(received) == 1
    assert received[0].payload.content == "hello"
    alice.assert_sent(Intent.TASK_REQUEST, count=1)
    bob.assert_received(Intent.TASK_REQUEST, count=1)


@pytest.mark.asyncio
async def test_unhandled_goes_to_dlq():
    alice, bob = MockTPCPNode.connect_pair()
    # No handler registered for STATE_SYNC
    await alice.send_message(bob.agent_id, Intent.STATE_SYNC, TextPayload(content="state"))
    assert len(bob.dlq) == 1


@pytest.mark.asyncio
async def test_clear_resets_state():
    alice, bob = MockTPCPNode.connect_pair()
    await alice.send_message(bob.agent_id, Intent.HANDSHAKE, TextPayload(content="hi"))
    alice.clear()
    bob.clear()
    assert len(alice.sent) == 0
    assert len(bob.received) == 0
