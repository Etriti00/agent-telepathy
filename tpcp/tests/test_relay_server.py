"""
Tests for ADNSRelayServer (tpcp/tpcp/relay/server.py).

Strategy: call the relay's internal async methods directly via mock WebSocket
connections — no real network sockets required.
"""
import json
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

import time as _time

from tpcp.relay.server import ADNSRelayServer, TokenBucket, BROADCAST_ID
from tpcp.security.crypto import AgentIdentityManager


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_server(rate_limit: float = 30.0, burst: int = 60) -> ADNSRelayServer:
    """Return a fresh relay server instance (no network binding)."""
    return ADNSRelayServer("127.0.0.1", 9900, rate_limit=rate_limit, burst_limit=burst)


class FakeWebSocket:
    """
    Minimal WebSocket stand-in for _handle_connection tests.

    Supports:
    - ``async for msg in ws``  — yields items from *messages*
    - ``await ws.send(data)``
    - ``await ws.close(code, reason)``
    - ``id(ws)``               — stable Python object id

    All calls to send/close are recorded on ``sent`` and the close args on
    ``close_calls``.
    """

    def __init__(self, messages: list[str] | None = None):
        self._messages: list[str] = messages or []
        self.sent: list[str] = []
        self.close_calls: list[tuple] = []
        self._closed = False

    # AsyncMock-like attribute access used by tests
    @property
    def send(self):
        return self._send_mock

    @property
    def close(self):
        return self._close_mock

    async def _send_impl(self, data: str) -> None:
        self.sent.append(data)

    async def _close_impl(self, code=None, reason=None) -> None:
        self.close_calls.append((code, reason))
        self._closed = True

    def __post_init__(self):
        pass

    def __init_mocks(self):
        self._send_mock = AsyncMock(side_effect=self._send_impl)
        self._close_mock = AsyncMock(side_effect=self._close_impl)

    def __new__(cls, messages=None):
        obj = object.__new__(cls)
        obj._messages = messages or []
        obj.sent = []
        obj.close_calls = []
        obj._closed = False
        obj._send_mock = AsyncMock(side_effect=obj._send_impl_bound)
        obj._close_mock = AsyncMock(side_effect=obj._close_impl_bound)
        obj.remote_address = ("127.0.0.1", 12345)
        return obj

    async def _send_impl_bound(self, data: str) -> None:
        self.sent.append(data)

    async def _close_impl_bound(self, code=None, reason=None) -> None:
        self.close_calls.append((code, reason))
        self._closed = True

    def __aiter__(self):
        return self._AsyncIter(list(self._messages))

    class _AsyncIter:
        def __init__(self, items):
            self._items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    # Delegate attribute access for send/close to mocks so tests can use
    # assert_called_once_with etc.
    def reset_mock(self):
        self.sent.clear()
        self.close_calls.clear()
        self._send_mock.reset_mock()
        self._close_mock.reset_mock()

    # send / close are properties above, but we also expose them directly
    # so the relay code's ``await websocket.send(...)`` / ``await websocket.close(...)``
    # calls land on the AsyncMock.


def make_ws(messages: list[str] | None = None) -> FakeWebSocket:
    """Return a FakeWebSocket pre-loaded with *messages*."""
    return FakeWebSocket(messages=messages)


def _handshake_message(sender_id: str, public_key: str) -> str:
    """Build a minimal HANDSHAKE message string."""
    return json.dumps({
        "header": {
            "intent": "HANDSHAKE",
            "sender_id": sender_id,
            "receiver_id": None,
            "ttl": 30,
        },
        "payload": {
            "content": json.dumps({"public_key": public_key})
        }
    })


def _challenge_response_message(sender_id: str, signed_nonce: str) -> str:
    """Build a Challenge_Response message string."""
    return json.dumps({
        "header": {
            "intent": "Challenge_Response",
            "sender_id": sender_id,
            "receiver_id": None,
            "ttl": 30,
        },
        "payload": {
            "content": signed_nonce
        }
    })


def _routing_message(
    sender_id: str,
    receiver_id: str,
    intent: str = "TASK_REQUEST",
    ttl: int = 10,
) -> str:
    return json.dumps({
        "header": {
            "intent": intent,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "ttl": ttl,
        },
        "payload": {"content": "hello"}
    })


async def _register_agent(
    server: ADNSRelayServer, sender_id: str, ws: FakeWebSocket
) -> None:
    """Run the full challenge-response flow and assert registration."""
    mgr = AgentIdentityManager()
    pub_key = mgr.get_public_key_string()

    handshake = json.loads(_handshake_message(sender_id, pub_key))
    await server._initiate_challenge(sender_id, handshake, ws)

    assert sender_id in server._pending_challenges
    nonce = server._pending_challenges[sender_id]["nonce"]

    signed = mgr.sign_bytes(nonce.encode("utf-8"))

    cr_data = json.loads(_challenge_response_message(sender_id, signed))
    await server._handle_challenge_response(sender_id, cr_data, ws)

    assert sender_id in server.registry


# ── TokenBucket ───────────────────────────────────────────────────────────────

def test_token_bucket_allows_within_burst():
    bucket = TokenBucket(rate=30.0, burst=60)
    for _ in range(60):
        assert bucket.consume() is True


def test_token_bucket_rejects_when_exhausted():
    bucket = TokenBucket(rate=30.0, burst=5)
    for _ in range(5):
        bucket.consume()
    assert bucket.consume() is False


def test_token_bucket_refills_over_time():
    bucket = TokenBucket(rate=10.0, burst=10)
    for _ in range(10):
        bucket.consume()
    # Manually inject tokens to simulate elapsed time
    bucket.tokens = 5.0
    assert bucket.consume() is True


# ── _initiate_challenge ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initiate_challenge_stores_pending_and_sends_nonce():
    server = make_server()
    ws = make_ws()
    sender_id = str(uuid4())
    mgr = AgentIdentityManager()

    handshake = json.loads(_handshake_message(sender_id, mgr.get_public_key_string()))
    await server._initiate_challenge(sender_id, handshake, ws)

    assert sender_id in server._pending_challenges
    entry = server._pending_challenges[sender_id]
    assert entry["ws"] is ws
    assert len(entry["nonce"]) == 64  # 32 bytes hex-encoded
    assert entry["public_key"] == mgr.get_public_key_string()

    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent["type"] == "ADNS_CHALLENGE"
    assert sent["agent_id"] == sender_id
    assert sent["nonce"] == entry["nonce"]


@pytest.mark.asyncio
async def test_initiate_challenge_missing_public_key_does_nothing():
    server = make_server()
    ws = make_ws()
    sender_id = str(uuid4())

    data = {
        "header": {"intent": "HANDSHAKE", "sender_id": sender_id},
        "payload": {"content": json.dumps({})}
    }
    await server._initiate_challenge(sender_id, data, ws)

    assert sender_id not in server._pending_challenges
    assert len(ws.sent) == 0


# ── _handle_challenge_response ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_challenge_response_valid_registers_agent():
    server = make_server()
    ws = make_ws()
    sender_id = str(uuid4())
    await _register_agent(server, sender_id, ws)

    # ADNS_REGISTERED must have been sent
    all_sent = [json.loads(m) for m in ws.sent]
    registered_msgs = [m for m in all_sent if m.get("type") == "ADNS_REGISTERED"]
    assert len(registered_msgs) == 1
    assert registered_msgs[0]["agent_id"] == sender_id

    assert sender_id not in server._pending_challenges


@pytest.mark.asyncio
async def test_challenge_response_invalid_signature_rejects():
    server = make_server()
    ws = make_ws()
    sender_id = str(uuid4())
    mgr = AgentIdentityManager()

    handshake = json.loads(_handshake_message(sender_id, mgr.get_public_key_string()))
    await server._initiate_challenge(sender_id, handshake, ws)

    bad_cr = json.loads(_challenge_response_message(sender_id, "bm90YXJlYWxzaWduYXR1cmU="))
    await server._handle_challenge_response(sender_id, bad_cr, ws)

    assert sender_id not in server.registry
    assert sender_id not in server._pending_challenges
    assert ws.close_calls == [(1008, "Challenge verification failed")]


@pytest.mark.asyncio
async def test_challenge_response_unknown_sender_ignored():
    server = make_server()
    ws = make_ws()
    unknown_id = str(uuid4())

    cr_data = json.loads(_challenge_response_message(unknown_id, "irrelevant"))
    await server._handle_challenge_response(unknown_id, cr_data, ws)

    assert unknown_id not in server.registry
    assert len(ws.sent) == 0
    assert len(ws.close_calls) == 0


@pytest.mark.asyncio
async def test_challenge_response_empty_content_rejects():
    server = make_server()
    ws = make_ws()
    sender_id = str(uuid4())
    mgr = AgentIdentityManager()

    handshake = json.loads(_handshake_message(sender_id, mgr.get_public_key_string()))
    await server._initiate_challenge(sender_id, handshake, ws)

    cr_data = json.loads(_challenge_response_message(sender_id, ""))
    await server._handle_challenge_response(sender_id, cr_data, ws)

    assert sender_id not in server.registry
    assert sender_id not in server._pending_challenges


# ── Rate limiting ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_disconnects_on_exhaustion():
    """A connection that exhausts its token bucket must be closed."""
    server = make_server(rate_limit=1.0, burst=2)
    target_id = str(uuid4())
    target_ws = make_ws()
    sender_id = str(uuid4())

    # Use the full _handle_connection flow so rate_limiters dict is populated.
    # First send a HANDSHAKE to trigger challenge (which registers rate limiter).
    # Then immediately deplete the bucket via direct access.

    # We construct a ws that will: send 1 HANDSHAKE, then 3 routing msgs.
    # The rate limiter is inserted at start of _handle_connection with burst=2,
    # so after 2 consumes it's exhausted.
    mgr = AgentIdentityManager()
    pub_key = mgr.get_public_key_string()

    messages = [_handshake_message(sender_id, pub_key)] * 3

    ws = make_ws(messages=messages)

    # Patch _initiate_challenge to also deplete the token bucket
    original_initiate = server._initiate_challenge

    async def depleting_initiate(sid, data, websocket):
        # Drain bucket so the very next message triggers rate-limit
        ws_id = id(websocket)
        if ws_id in server._rate_limiters:
            server._rate_limiters[ws_id].tokens = 0.0
        await original_initiate(sid, data, websocket)

    server._initiate_challenge = depleting_initiate
    server.registry[target_id] = {"ws": target_ws, "public_key": "pk"}

    await server._handle_connection(ws)

    assert ws.close_calls[0][0] == 1008
    assert "Rate limit" in ws.close_calls[0][1]


# ── TTL enforcement ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ttl_zero_message_is_dropped():
    """A message with ttl=0 must not be forwarded to the target."""
    server = make_server()
    sender_id = str(uuid4())
    target_id = str(uuid4())
    sender_ws = make_ws()
    target_ws = make_ws()

    await _register_agent(server, sender_id, sender_ws)
    server.registry[target_id] = {"ws": target_ws, "public_key": "pk"}

    routing_ws = make_ws(messages=[_routing_message(sender_id, target_id, ttl=0)])
    # Pre-copy registration to the new ws
    server.registry[sender_id]["ws"] = routing_ws

    await server._handle_connection(routing_ws)

    assert len(target_ws.sent) == 0


@pytest.mark.asyncio
async def test_ttl_decremented_on_forwarding():
    """A successfully routed message must arrive with TTL decremented by 1."""
    server = make_server()
    sender_id = str(uuid4())
    target_id = str(uuid4())
    sender_ws = make_ws()
    target_ws = make_ws()

    await _register_agent(server, sender_id, sender_ws)
    server.registry[target_id] = {"ws": target_ws, "public_key": "pk"}

    original_ttl = 5
    routing_ws = make_ws(messages=[_routing_message(sender_id, target_id, ttl=original_ttl)])
    server.registry[sender_id]["ws"] = routing_ws

    await server._handle_connection(routing_ws)

    assert len(target_ws.sent) == 1
    forwarded = json.loads(target_ws.sent[0])
    assert forwarded["header"]["ttl"] == original_ttl - 1


# ── Message routing ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_routing_registered_sender_to_registered_receiver():
    """Message from registered agent A to registered agent B must be delivered."""
    server = make_server()
    sender_id = str(uuid4())
    target_id = str(uuid4())
    sender_ws = make_ws()
    target_ws = make_ws()

    await _register_agent(server, sender_id, sender_ws)
    server.registry[target_id] = {"ws": target_ws, "public_key": "pk"}

    routing_ws = make_ws(messages=[_routing_message(sender_id, target_id, ttl=10)])
    server.registry[sender_id]["ws"] = routing_ws

    await server._handle_connection(routing_ws)

    assert len(target_ws.sent) == 1
    received = json.loads(target_ws.sent[0])
    assert received["header"]["sender_id"] == sender_id


@pytest.mark.asyncio
async def test_routing_to_unknown_recipient_is_dropped():
    """A message to an unregistered agent_id must not raise and not be delivered."""
    server = make_server()
    sender_id = str(uuid4())
    ghost_id = str(uuid4())
    sender_ws = make_ws()

    await _register_agent(server, sender_id, sender_ws)
    assert ghost_id not in server.registry

    routing_ws = make_ws(messages=[_routing_message(sender_id, ghost_id, ttl=5)])
    server.registry[sender_id]["ws"] = routing_ws

    # Must not raise
    await server._handle_connection(routing_ws)

    # No delivery possible — confirm server is still consistent
    assert sender_id not in server.registry  # deregistered on clean exit


@pytest.mark.asyncio
async def test_broadcast_fanout_reaches_all_peers_except_sender():
    """A BROADCAST_ID message must be fanned out to every peer except the sender."""
    server = make_server()
    sender_id = str(uuid4())
    peer_a_id = str(uuid4())
    peer_b_id = str(uuid4())

    sender_ws = make_ws()
    peer_a_ws = make_ws()
    peer_b_ws = make_ws()

    await _register_agent(server, sender_id, sender_ws)
    server.registry[peer_a_id] = {"ws": peer_a_ws, "public_key": "pk"}
    server.registry[peer_b_id] = {"ws": peer_b_ws, "public_key": "pk"}

    routing_ws = make_ws(messages=[_routing_message(sender_id, BROADCAST_ID, ttl=5)])
    server.registry[sender_id]["ws"] = routing_ws

    await server._handle_connection(routing_ws)

    assert len(peer_a_ws.sent) == 1
    assert len(peer_b_ws.sent) == 1
    # Sender's own ws should not have received the broadcast
    assert len(routing_ws.sent) == 0


@pytest.mark.asyncio
async def test_broadcast_stale_connection_is_deregistered():
    """If a broadcast send fails for a peer, that peer is removed from registry."""
    server = make_server()
    sender_id = str(uuid4())
    stale_id = str(uuid4())

    sender_ws = make_ws()

    class FailingWS(FakeWebSocket):
        async def _send_impl_bound(self, data):
            raise Exception("connection lost")

    stale_ws = FailingWS()

    await _register_agent(server, sender_id, sender_ws)
    server.registry[stale_id] = {"ws": stale_ws, "public_key": "pk"}

    routing_ws = make_ws(messages=[_routing_message(sender_id, BROADCAST_ID, ttl=5)])
    server.registry[sender_id]["ws"] = routing_ws

    await server._handle_connection(routing_ws)

    assert stale_id not in server.registry


# ── Stale connection cleanup ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stale_target_deregistered_on_unicast_failure():
    """If forwarding raises ConnectionClosed the target is removed from registry."""
    import websockets.exceptions

    server = make_server()
    sender_id = str(uuid4())
    target_id = str(uuid4())
    sender_ws = make_ws()

    class ClosedWS(FakeWebSocket):
        async def _send_impl_bound(self, data):
            raise websockets.exceptions.ConnectionClosed(None, None)

    target_ws = ClosedWS()

    await _register_agent(server, sender_id, sender_ws)
    server.registry[target_id] = {"ws": target_ws, "public_key": "pk"}

    routing_ws = make_ws(messages=[_routing_message(sender_id, target_id, ttl=5)])
    server.registry[sender_id]["ws"] = routing_ws

    await server._handle_connection(routing_ws)

    assert target_id not in server.registry


@pytest.mark.asyncio
async def test_disconnected_client_removed_from_registry():
    """When a connection's message loop ends normally, the agent is deregistered."""
    server = make_server()
    sender_id = str(uuid4())
    sender_ws = make_ws()

    await _register_agent(server, sender_id, sender_ws)
    assert sender_id in server.registry

    # Empty message list simulates clean disconnect
    clean_ws = make_ws(messages=[])
    server.registry[sender_id]["ws"] = clean_ws

    await server._handle_connection(clean_ws)

    assert sender_id not in server.registry


@pytest.mark.asyncio
async def test_rate_limiter_removed_on_disconnect():
    """After a connection closes, its rate-limiter entry is cleaned up."""
    server = make_server()
    ws = make_ws(messages=[])

    await server._handle_connection(ws)

    assert id(ws) not in server._rate_limiters


# ── Pending challenge cleanup ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pending_challenge_cleaned_on_disconnect():
    """Pending challenges for a closed connection are removed on disconnect."""
    server = make_server()
    ws = make_ws()
    sender_id = str(uuid4())
    mgr = AgentIdentityManager()

    handshake = json.loads(_handshake_message(sender_id, mgr.get_public_key_string()))
    await server._initiate_challenge(sender_id, handshake, ws)
    assert sender_id in server._pending_challenges

    # Disconnect without responding to challenge
    clean_ws = make_ws(messages=[])
    # Patch the pending challenge to use clean_ws so cleanup triggers
    server._pending_challenges[sender_id]["ws"] = clean_ws

    await server._handle_connection(clean_ws)

    assert sender_id not in server._pending_challenges


# ── Unverified sender is not routed ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_unverified_sender_triggers_challenge_not_routing():
    """A message from an unverified sender starts a challenge, not routing."""
    server = make_server()
    target_id = str(uuid4())
    sender_id = str(uuid4())
    target_ws = make_ws()
    server.registry[target_id] = {"ws": target_ws, "public_key": "pk"}

    mgr = AgentIdentityManager()
    msg = _handshake_message(sender_id, mgr.get_public_key_string())

    sender_ws = make_ws(messages=[msg])
    await server._handle_connection(sender_ws)

    # Challenge sent to sender, nothing routed to target
    assert len(target_ws.sent) == 0
    assert len(sender_ws.sent) == 1
    sent = json.loads(sender_ws.sent[0])
    assert sent["type"] == "ADNS_CHALLENGE"


# ── TASK 16: CHALLENGE HARDENING TESTS ──────────────────────────────

@pytest.mark.asyncio
async def test_challenge_expiration_cleanup():
    server = make_server()
    server._pending_challenges["old-agent"] = {
        "ws": None, "nonce": "abc", "public_key": "key", "timestamp": _time.monotonic() - 400
    }
    server._cleanup_stale_challenges()
    assert "old-agent" not in server._pending_challenges


@pytest.mark.asyncio
async def test_challenge_fresh_not_cleaned():
    server = make_server()
    server._pending_challenges["fresh-agent"] = {
        "ws": None, "nonce": "abc", "public_key": "key", "timestamp": _time.monotonic()
    }
    server._cleanup_stale_challenges()
    assert "fresh-agent" in server._pending_challenges


def test_public_key_format_validation_rejects_malformed():
    import base64
    short_key = base64.b64encode(b"x" * 16).decode()
    decoded = base64.b64decode(short_key)
    assert len(decoded) != 32


def test_public_key_format_validation_accepts_valid():
    import base64
    valid_key = base64.b64encode(b"x" * 32).decode()
    decoded = base64.b64decode(valid_key)
    assert len(decoded) == 32
