"""
Tests for HomeAssistantAdapter (tpcp/tpcp/adapters/homeassistant_adapter.py).

All network I/O is mocked; no real HTTP connections are made.
"""
import asyncio
import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from tpcp.schemas.envelope import AgentIdentity, Intent, TPCPEnvelope, CRDTSyncPayload

# Skip entire module if aiohttp is not installed
pytest.importorskip("aiohttp", reason="aiohttp not installed; skip HA adapter tests")


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_identity() -> AgentIdentity:
    return AgentIdentity(framework="HATest", public_key="placeholder")


def make_adapter(ha_token: str = "super-secret-token-abc123"):
    """Return a HomeAssistantAdapter with an injected mock session."""
    from tpcp.adapters.homeassistant_adapter import HomeAssistantAdapter

    adapter = HomeAssistantAdapter(
        identity=make_identity(),
        ha_url="http://homeassistant.local:8123",
        ha_token=ha_token,
    )
    return adapter


def _mock_post_session(raise_for_status_exc=None):
    """Build a mock aiohttp session whose .post() context manager works correctly."""
    mock_resp = AsyncMock()
    if raise_for_status_exc:
        mock_resp.raise_for_status = MagicMock(side_effect=raise_for_status_exc)
    else:
        mock_resp.raise_for_status = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.close = AsyncMock()
    return mock_session, mock_resp


def _mock_sse_session(lines: list[bytes]):
    """Build a mock aiohttp session whose .get() SSE context manager yields *lines*."""
    remaining = list(lines)

    async def readline_side_effect():
        if remaining:
            return remaining.pop(0)
        # Block forever once exhausted so the inner loop doesn't exit prematurely
        await asyncio.sleep(9999)

    mock_content = AsyncMock()
    mock_content.readline = AsyncMock(side_effect=readline_side_effect)

    mock_resp = AsyncMock()
    mock_resp.content = mock_content
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.close = AsyncMock()
    return mock_session


# ── Initialization ─────────────────────────────────────────────────────────────

def test_init_raises_when_aiohttp_unavailable():
    """Adapter must raise ImportError when aiohttp is not available."""
    with patch("tpcp.adapters.homeassistant_adapter.AIOHTTP_AVAILABLE", False):
        from tpcp.adapters.homeassistant_adapter import HomeAssistantAdapter
        with pytest.raises(ImportError, match="aiohttp"):
            HomeAssistantAdapter(
                identity=make_identity(),
                ha_url="http://ha.local",
                ha_token="tok",
            )


def test_init_strips_trailing_slash():
    from tpcp.adapters.homeassistant_adapter import HomeAssistantAdapter

    adapter = HomeAssistantAdapter(
        identity=make_identity(),
        ha_url="http://homeassistant.local:8123/",
        ha_token="tok",
    )
    assert not adapter.ha_url.endswith("/")


def test_init_stores_token_in_private_attribute():
    """Token must be stored in a private attribute, not a public one."""
    adapter = make_adapter()
    assert adapter._ha_token == "super-secret-token-abc123"
    assert not hasattr(adapter, "ha_token")


# ── SSE stream parsing ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_state_changed_produces_state_sync_envelope():
    """A state_changed SSE event must be converted to a STATE_SYNC TPCPEnvelope."""
    state_changed_event = json.dumps({
        "event_type": "state_changed",
        "data": {
            "entity_id": "light.living_room",
            "new_state": {"state": "on"},
        }
    })

    lines = [f"data: {state_changed_event}\n".encode("utf-8")]

    adapter = make_adapter()
    adapter._session = _mock_sse_session(lines)

    received: list[TPCPEnvelope] = []

    def callback(env: TPCPEnvelope) -> None:
        received.append(env)

    await adapter.start_event_stream(callback)

    # Yield control so the task runs at least one iteration
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    adapter._listening_task.cancel()
    try:
        await adapter._listening_task
    except (asyncio.CancelledError, Exception):
        pass

    assert len(received) == 1
    env = received[0]
    assert env.header.intent == Intent.STATE_SYNC
    assert isinstance(env.payload, CRDTSyncPayload)
    assert "ha_light.living_room" in env.payload.state


@pytest.mark.asyncio
async def test_sse_ping_keepalive_is_skipped():
    """Lines containing 'data: ping' must be silently ignored."""
    lines = [b"data: ping\n"]

    adapter = make_adapter()
    adapter._session = _mock_sse_session(lines)

    received: list[TPCPEnvelope] = []
    await adapter.start_event_stream(lambda env: received.append(env))

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    adapter._listening_task.cancel()
    try:
        await adapter._listening_task
    except (asyncio.CancelledError, Exception):
        pass

    assert len(received) == 0


@pytest.mark.asyncio
async def test_sse_non_state_changed_events_are_skipped():
    """Events whose event_type != 'state_changed' must not produce envelopes."""
    other_event = json.dumps({
        "event_type": "call_service",
        "data": {"domain": "light", "service": "turn_on"}
    })

    lines = [f"data: {other_event}\n".encode()]

    adapter = make_adapter()
    adapter._session = _mock_sse_session(lines)

    received: list[TPCPEnvelope] = []
    await adapter.start_event_stream(lambda env: received.append(env))

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    adapter._listening_task.cancel()
    try:
        await adapter._listening_task
    except (asyncio.CancelledError, Exception):
        pass

    assert len(received) == 0


# ── SSE reconnection ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_client_error_triggers_reconnect():
    """aiohttp.ClientError during stream must log a warning and sleep before retrying."""
    import aiohttp

    sleep_calls: list[float] = []

    # Original asyncio.sleep so the test can yield without being intercepted
    _real_sleep = asyncio.sleep

    async def _patched_sleep(delay: float):
        sleep_calls.append(delay)
        # Stop the loop after the first reconnect sleep
        raise asyncio.CancelledError

    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("conn refused"))
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.closed = False

    adapter = make_adapter()
    adapter._session = mock_session

    with patch("tpcp.adapters.homeassistant_adapter.asyncio.sleep", side_effect=_patched_sleep):
        await adapter.start_event_stream(lambda env: None)
        try:
            await adapter._listening_task
        except (asyncio.CancelledError, Exception):
            pass

    assert len(sleep_calls) >= 1


@pytest.mark.asyncio
async def test_sse_client_error_sleep_duration_is_five_seconds():
    """The reconnect sleep duration must be exactly 5 seconds."""
    import aiohttp

    sleep_durations: list[float] = []

    async def _capture_sleep(delay: float):
        sleep_durations.append(delay)
        raise asyncio.CancelledError

    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("err"))
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.closed = False

    adapter = make_adapter()
    adapter._session = mock_session

    with patch("tpcp.adapters.homeassistant_adapter.asyncio.sleep", side_effect=_capture_sleep):
        await adapter.start_event_stream(lambda env: None)
        try:
            await adapter._listening_task
        except (asyncio.CancelledError, Exception):
            pass

    assert len(sleep_durations) >= 1
    assert sleep_durations[0] == 5


# ── execute_service_call (send_physical_command) ──────────────────────────────

@pytest.mark.asyncio
async def test_execute_service_call_posts_correct_url():
    """execute_service_call must POST to /api/services/{domain}/{service}."""
    adapter = make_adapter()
    mock_session, _ = _mock_post_session()
    adapter._session = mock_session

    result = await adapter.execute_service_call(
        domain="light",
        service="turn_on",
        entity_id="light.living_room",
    )

    assert result is True
    mock_session.post.assert_called_once()
    url = mock_session.post.call_args[0][0]
    assert url == "http://homeassistant.local:8123/api/services/light/turn_on"


@pytest.mark.asyncio
async def test_execute_service_call_includes_entity_id_in_payload():
    """POST body must contain the entity_id and any extra service_data."""
    adapter = make_adapter()
    mock_session, _ = _mock_post_session()
    adapter._session = mock_session

    await adapter.execute_service_call(
        domain="switch",
        service="turn_off",
        entity_id="switch.bedroom",
        service_data={"transition": 2},
    )

    mock_session.post.assert_called_once()
    _, kwargs = mock_session.post.call_args
    body = kwargs["json"]
    assert body["entity_id"] == "switch.bedroom"
    assert body["transition"] == 2


@pytest.mark.asyncio
async def test_execute_service_call_returns_false_on_http_error():
    """HTTP errors must be caught and return False."""
    adapter = make_adapter()
    mock_session, _ = _mock_post_session(raise_for_status_exc=Exception("404"))
    adapter._session = mock_session

    result = await adapter.execute_service_call(
        domain="light", service="turn_on", entity_id="light.x"
    )
    assert result is False


@pytest.mark.asyncio
async def test_unpack_request_dispatches_valid_command():
    """unpack_request with a valid JSON TextPayload must call execute_service_call."""
    from tpcp.schemas.envelope import TextPayload, MessageHeader, TPCPEnvelope

    adapter = make_adapter()
    adapter.execute_service_call = AsyncMock(return_value=True)

    cmd = json.dumps({
        "domain": "light",
        "service": "turn_on",
        "entity_id": "light.kitchen",
        "service_data": {"brightness": 200},
    })

    header = MessageHeader(
        sender_id=uuid4(),
        receiver_id=adapter.identity.agent_id,
        intent=Intent.TASK_REQUEST,
    )
    envelope = TPCPEnvelope(header=header, payload=TextPayload(content=cmd))

    result = await adapter.unpack_request(envelope)
    assert result["status"] == "success"
    adapter.execute_service_call.assert_called_once_with(
        domain="light",
        service="turn_on",
        entity_id="light.kitchen",
        service_data={"brightness": 200},
    )


@pytest.mark.asyncio
async def test_unpack_request_returns_error_for_invalid_payload():
    """unpack_request with a non-command payload must return error status."""
    from tpcp.schemas.envelope import TextPayload, MessageHeader, TPCPEnvelope

    adapter = make_adapter()

    header = MessageHeader(
        sender_id=uuid4(),
        receiver_id=adapter.identity.agent_id,
        intent=Intent.TASK_REQUEST,
    )
    envelope = TPCPEnvelope(header=header, payload=TextPayload(content="not json"))

    result = await adapter.unpack_request(envelope)
    assert result["status"] == "error"


# ── Token not logged ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ha_token_not_present_in_log_output(caplog):
    """The HA bearer token must never appear in any log records during normal operation."""
    adapter = make_adapter(ha_token="super-secret-token-abc123")
    mock_session, _ = _mock_post_session()
    adapter._session = mock_session

    with caplog.at_level(logging.DEBUG):
        await adapter.execute_service_call(
            domain="light", service="turn_on", entity_id="light.hall"
        )

    secret = "super-secret-token-abc123"
    for record in caplog.records:
        assert secret not in record.getMessage(), (
            f"Token leaked in log record: {record.getMessage()}"
        )


@pytest.mark.asyncio
async def test_ha_token_not_in_error_log_on_failure(caplog):
    """Token must not leak in error log messages when a service call fails."""
    adapter = make_adapter(ha_token="super-secret-token-abc123")
    mock_session, _ = _mock_post_session(raise_for_status_exc=Exception("Server Error"))
    adapter._session = mock_session

    with caplog.at_level(logging.DEBUG):
        await adapter.execute_service_call(
            domain="light", service="turn_on", entity_id="light.hall"
        )

    secret = "super-secret-token-abc123"
    for record in caplog.records:
        assert secret not in record.getMessage()


# ── pack_thought ──────────────────────────────────────────────────────────────

def test_pack_thought_produces_crdt_sync_envelope():
    """pack_thought must produce a CRDTSyncPayload with the entity state."""
    adapter = make_adapter()

    raw_output = {
        "entity_id": "sensor.temperature",
        "new_state": {"state": "21.5"},
    }

    envelope = adapter.pack_thought(UUID(int=0), raw_output, Intent.STATE_SYNC)

    assert envelope.header.intent == Intent.STATE_SYNC
    assert isinstance(envelope.payload, CRDTSyncPayload)
    assert "ha_sensor.temperature" in envelope.payload.state
    assert envelope.payload.state["ha_sensor.temperature"]["value"] == "21.5"


def test_pack_thought_increments_logical_clock():
    """Each call to pack_thought must increment the logical clock."""
    adapter = make_adapter()

    raw = {"entity_id": "light.x", "new_state": {"state": "off"}}
    adapter.pack_thought(UUID(int=0), raw, Intent.STATE_SYNC)
    clock_after_first = adapter._logical_clock

    adapter.pack_thought(UUID(int=0), raw, Intent.STATE_SYNC)
    clock_after_second = adapter._logical_clock

    assert clock_after_second == clock_after_first + 1


# ── stop / cleanup ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stop_cancels_listening_task_and_closes_session():
    """stop() must cancel the background task and close the session."""
    from tpcp.adapters.homeassistant_adapter import HomeAssistantAdapter

    adapter = HomeAssistantAdapter(
        identity=make_identity(),
        ha_url="http://ha.local",
        ha_token="tok",
    )

    async def _noop():
        await asyncio.sleep(9999)

    adapter._listening_task = asyncio.create_task(_noop())

    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.close = AsyncMock()
    adapter._session = mock_session

    await adapter.stop()
    # Give event loop one tick to process the cancellation
    await asyncio.sleep(0)

    assert adapter._listening_task.cancelled() or adapter._listening_task.done()
    mock_session.close.assert_called_once()
