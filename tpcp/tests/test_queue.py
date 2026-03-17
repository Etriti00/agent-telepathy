import pytest
from uuid import uuid4

from tpcp.core.queue import MessageQueue
from tpcp.schemas.envelope import (
    TPCPEnvelope,
    MessageHeader,
    TextPayload,
    Intent,
    PROTOCOL_VERSION,
)


def _make_envelope(msg_id: str = None) -> TPCPEnvelope:
    header = MessageHeader(
        message_id=msg_id or str(uuid4()),
        sender_id=str(uuid4()),
        receiver_id=str(uuid4()),
        intent=Intent.TASK_REQUEST,
        ttl=30,
        protocol_version=PROTOCOL_VERSION,
    )
    payload = TextPayload(content="test")
    return TPCPEnvelope(header=header, payload=payload)


@pytest.mark.asyncio
async def test_enqueue_and_dequeue():
    q = MessageQueue(max_size_per_peer=10)
    target = uuid4()
    env = _make_envelope()
    await q.enqueue(target, env)
    assert await q.has_messages(target)
    result = await q.dequeue_one(target)
    assert result is not None
    assert result.header.message_id == env.header.message_id
    assert not await q.has_messages(target)


@pytest.mark.asyncio
async def test_queue_stats():
    q = MessageQueue(max_size_per_peer=100)
    t1 = str(uuid4())
    t2 = str(uuid4())
    await q.enqueue(t1, _make_envelope())
    await q.enqueue(t1, _make_envelope())
    await q.enqueue(t2, _make_envelope())

    stats = q.queue_stats
    assert stats[t1] == 2
    assert stats[t2] == 1


@pytest.mark.asyncio
async def test_enqueue_front():
    q = MessageQueue(max_size_per_peer=10)
    target = str(uuid4())
    env1 = _make_envelope()
    env2 = _make_envelope()
    await q.enqueue(target, env1)
    await q.enqueue_front(target, env2)
    result = await q.dequeue_one(target)
    assert result.header.message_id == env2.header.message_id


@pytest.mark.asyncio
async def test_drain():
    q = MessageQueue(max_size_per_peer=10)
    target = str(uuid4())
    for _ in range(5):
        await q.enqueue(target, _make_envelope())
    drained = await q.drain(target)
    assert len(drained) == 5
    assert not await q.has_messages(target)


@pytest.mark.asyncio
async def test_max_size_eviction():
    q = MessageQueue(max_size_per_peer=3)
    target = str(uuid4())
    for _ in range(5):
        await q.enqueue(target, _make_envelope())
    stats = q.queue_stats
    assert stats[target] == 3
