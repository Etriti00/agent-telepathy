import pytest
import tempfile
from pathlib import Path
from uuid import uuid4

from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
from tpcp.core.node import TPCPNode
from tpcp.core.queue import MessageQueue
from tpcp.security.crypto import AgentIdentityManager
from tpcp.memory.crdt import LWWMap
from tpcp.memory.vector import VectorBank

import threading

def make_node(port: int) -> TPCPNode:
    """Helper to create a TPCPNode with a real Ed25519 identity."""
    identity_manager = AgentIdentityManager()
    identity = AgentIdentity(
        framework="NodeTest",
        public_key=identity_manager.get_public_key_string()
    )
    return TPCPNode(identity=identity, host="127.0.0.1", port=port, identity_manager=identity_manager)


# ── NODE TESTS ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_initialization():
    node = make_node(9100)
    assert node.host == "127.0.0.1"
    assert node.port == 9100
    assert len(node.peer_registry) == 0
    assert len(node.identity.public_key) > 10  # Real Ed25519 key


@pytest.mark.asyncio
async def test_peer_registration():
    node = make_node(9101)
    peer_manager = AgentIdentityManager()
    peer_identity = AgentIdentity(
        framework="PeerTest",
        public_key=peer_manager.get_public_key_string()
    )
    
    node.register_peer(peer_identity, "ws://127.0.0.1:9102")
    assert peer_identity.agent_id in node.peer_registry
    
    node.remove_peer(peer_identity.agent_id)
    assert peer_identity.agent_id not in node.peer_registry


@pytest.mark.asyncio
async def test_message_dlq_on_unknown_peer():
    node = make_node(9103)
    target_id = uuid4()
    await node.send_message(target_id, Intent.TASK_REQUEST, TextPayload(content="test"))
    assert await node.message_queue.has_messages(target_id)


@pytest.mark.asyncio
async def test_async_context_manager():
    identity = AgentIdentity(framework="CtxTest", public_key="placeholder")
    node = TPCPNode(identity=identity, host="127.0.0.1", port=9104)
    
    async with node as n:
        assert n._running is True
    assert n._running is False


# ── CRYPTO TESTS ─────────────────────────────────────────────────────

def test_sign_verify_roundtrip():
    mgr = AgentIdentityManager()
    payload = {"key": "value", "nested": {"a": 1}}
    
    signature = mgr.sign_payload(payload)
    public_key = mgr.get_public_key_string()
    
    assert AgentIdentityManager.verify_signature(public_key, signature, payload)


def test_verify_rejects_tampered():
    mgr = AgentIdentityManager()
    payload = {"key": "value"}
    
    signature = mgr.sign_payload(payload)
    public_key = mgr.get_public_key_string()
    
    tampered = {"key": "TAMPERED"}
    assert not AgentIdentityManager.verify_signature(public_key, signature, tampered)


def test_sign_bytes_roundtrip():
    mgr = AgentIdentityManager()
    data = b"hello-nonce-12345"
    
    sig = mgr.sign_bytes(data)
    pub = mgr.get_public_key_string()
    
    assert AgentIdentityManager.verify_bytes(pub, sig, data)
    assert not AgentIdentityManager.verify_bytes(pub, sig, b"wrong-data")


def test_key_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "test.key"
        
        # Generate and save
        mgr1 = AgentIdentityManager(key_path=key_path, auto_save=True)
        pub1 = mgr1.get_public_key_string()
        
        # Load from file
        mgr2 = AgentIdentityManager(key_path=key_path)
        pub2 = mgr2.get_public_key_string()
        
        assert pub1 == pub2
        assert mgr2.was_loaded is True


# ── DLQ TESTS ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dlq_max_size_eviction():
    from tpcp.schemas.envelope import MessageHeader, TPCPEnvelope
    
    queue = MessageQueue(max_size_per_peer=3)
    target_id = uuid4()
    
    for i in range(5):
        payload = TextPayload(content=f"msg {i}")
        header = MessageHeader(sender_id=uuid4(), receiver_id=target_id, intent=Intent.TASK_REQUEST)
        envelope = TPCPEnvelope(header=header, payload=payload)
        await queue.enqueue(target_id, envelope)
    
    messages = await queue.drain(target_id)
    assert len(messages) == 3


@pytest.mark.asyncio
async def test_dlq_enqueue_front():
    from tpcp.schemas.envelope import MessageHeader, TPCPEnvelope
    
    queue = MessageQueue(max_size_per_peer=100)
    target_id = uuid4()
    
    # Enqueue msg_1 then msg_2
    for i in range(2):
        payload = TextPayload(content=f"msg_{i}")
        header = MessageHeader(sender_id=uuid4(), receiver_id=target_id, intent=Intent.TASK_REQUEST)
        envelope = TPCPEnvelope(header=header, payload=payload)
        await queue.enqueue(target_id, envelope)
    
    # Dequeue one (should be msg_0)
    msg = await queue.dequeue_one(target_id)
    assert msg is not None
    
    # Re-enqueue at front
    await queue.enqueue_front(target_id, msg)
    
    # Next dequeue should be the same message again
    msg2 = await queue.dequeue_one(target_id)
    assert msg2.header.message_id == msg.header.message_id


# ── CRDT TESTS ───────────────────────────────────────────────────────

async def test_lwwmap_basic_set_get():
    crdt = LWWMap(node_id="agent-a")
    await crdt.set("key1", "value1")
    assert crdt.get("key1") == "value1"


async def test_lwwmap_last_writer_wins():
    crdt = LWWMap(node_id="agent-a")
    await crdt.set("key1", "old", timestamp=1, writer_id="agent-a")
    await crdt.set("key1", "new", timestamp=2, writer_id="agent-b")
    assert crdt.get("key1") == "new"


async def test_lwwmap_merge():
    a = LWWMap(node_id="a")
    b = LWWMap(node_id="b")

    await a.set("x", 1, timestamp=1, writer_id="a")
    await b.set("y", 2, timestamp=2, writer_id="b")

    await a.merge(b.serialize_state())

    assert a.get("x") == 1
    assert a.get("y") == 2


async def test_lwwmap_commutativity():
    """merge(A, B) == merge(B, A)"""
    a = LWWMap(node_id="a")
    b = LWWMap(node_id="b")

    await a.set("shared", "from-a", timestamp=5, writer_id="a")
    await b.set("shared", "from-b", timestamp=5, writer_id="b")

    # A merges B
    ab = LWWMap(node_id="test")
    await ab.merge(a.serialize_state())
    await ab.merge(b.serialize_state())

    # B merges A
    ba = LWWMap(node_id="test")
    await ba.merge(b.serialize_state())
    await ba.merge(a.serialize_state())

    assert ab.to_dict() == ba.to_dict()


async def test_lwwmap_sqlite_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "memory.db"

        crdt1 = LWWMap(node_id="agent-1", db_path=db_path)
        await crdt1.connect()
        await crdt1.set("key1", "hello")
        await crdt1.set("key2", {"nested": True})
        await crdt1.close()

        # Reload from disk
        crdt2 = LWWMap(node_id="agent-1", db_path=db_path)
        await crdt2.connect()
        assert crdt2.get("key1") == "hello"
        assert crdt2.get("key2") == {"nested": True}
        await crdt2.close()


# ── VECTOR BANK TESTS ────────────────────────────────────────────────

def test_vectorbank_store_and_retrieve():
    bank = VectorBank(node_id="test")
    pid = uuid4()
    bank.store_vector(pid, [1.0, 0.0, 0.0], "test-model")
    
    result = bank.get_vector(pid)
    assert result is not None
    assert result["model_id"] == "test-model"


def test_vectorbank_cosine_search():
    bank = VectorBank(node_id="test")
    
    pid1 = uuid4()
    pid2 = uuid4()
    pid3 = uuid4()
    
    bank.store_vector(pid1, [1.0, 0.0, 0.0], "test", raw_text="east")
    bank.store_vector(pid2, [0.0, 1.0, 0.0], "test", raw_text="north")
    bank.store_vector(pid3, [0.9, 0.1, 0.0], "test", raw_text="mostly-east")
    
    # Query: pure east
    results = bank.search([1.0, 0.0, 0.0], top_k=2)
    
    assert len(results) == 2
    # First result should be the exact match (similarity ≈ 1.0)
    assert results[0][0] == pid1
    assert results[0][1] > 0.99
    # Second should be "mostly-east"
    assert results[1][0] == pid3


# ── TASK 6: ENQUEUE_FRONT EVICTION ──────────────────────────────────

@pytest.mark.asyncio
async def test_dlq_enqueue_front_evicts_newest_when_full():
    from tpcp.schemas.envelope import MessageHeader, TPCPEnvelope

    q = MessageQueue(max_size_per_peer=2)
    target = uuid4()

    def _make_env(content: str) -> TPCPEnvelope:
        return TPCPEnvelope(
            header=MessageHeader(sender_id=uuid4(), receiver_id=target, intent=Intent.TASK_REQUEST),
            payload=TextPayload(content=content),
        )

    e1 = _make_env("first")
    e2 = _make_env("second")
    e3 = _make_env("retry")
    await q.enqueue(target, e1)
    await q.enqueue(target, e2)
    # Queue is [e1, e2]. enqueue_front(e3) should evict e2 (newest/back) and insert e3 at front.
    await q.enqueue_front(target, e3)
    msgs = await q.drain(target)
    assert len(msgs) == 2
    assert msgs[0].payload.content == "retry"
    assert msgs[1].payload.content == "first"


# ── TASK 8: VECTORBANK CONCURRENCY ──────────────────────────────────

def test_vectorbank_concurrent_access():
    bank = VectorBank("test-node")
    errors = []
    def writer(n):
        try:
            for i in range(100):
                bank.store_vector(uuid4(), [float(i)] * 3, "model")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert bank.total_vectors > 0


# ── TASK 9: DEDUP CACHE ORDEREDDICT ─────────────────────────────────

@pytest.mark.asyncio
async def test_dedup_cache_bounded_cleanup():
    from collections import OrderedDict
    mgr = AgentIdentityManager(auto_save=False)
    identity = AgentIdentity(framework="test", public_key=mgr.get_public_key_string())
    node = TPCPNode(identity=identity, port=0, identity_manager=mgr)
    assert isinstance(node._seen_messages, OrderedDict)
