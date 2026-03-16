import base64
import logging
import pytest
from uuid import UUID
from pydantic import ValidationError

from tpcp.schemas.envelope import (
    AgentIdentity,
    AckInfo,
    ChunkInfo,
    Intent,
    MessageHeader,
    TextPayload,
    VectorEmbeddingPayload,
    TPCPEnvelope,
    ImagePayload,
    AudioPayload,
    VideoPayload,
    BinaryPayload,
    TelemetryPayload,
    TelemetryReading,
)

def test_agent_identity_creation():
    identity = AgentIdentity(
        framework="TestFramework",
        capabilities=["test_skill"],
        public_key="test_key"
    )
    assert isinstance(identity.agent_id, UUID)
    assert identity.framework == "TestFramework"
    assert identity.public_key == "test_key"
    assert "test_skill" in identity.capabilities

def test_vector_payload_validation():
    # Valid
    payload = VectorEmbeddingPayload(
        model_id="test",
        dimensions=3,
        vector=[0.1, 0.2, 0.3]
    )
    assert len(payload.vector) == payload.dimensions

    # Invalid: dimension mismatch
    with pytest.raises(ValidationError):
        VectorEmbeddingPayload(
            model_id="test",
            dimensions=3,
            vector=[0.1, 0.2]
        )

def test_envelope_serialization():
    identity1 = AgentIdentity(framework="A", public_key="A")
    identity2 = AgentIdentity(framework="B", public_key="B")

    header = MessageHeader(
        sender_id=identity1.agent_id,
        receiver_id=identity2.agent_id,
        intent=Intent.TASK_REQUEST
    )
    
    payload = TextPayload(content="Hello", language="en")
    
    envelope = TPCPEnvelope(header=header, payload=payload)
    
    # Serialize to JSON
    json_str = envelope.model_dump_json()
    assert "Task_Request" in json_str
    
    # Deserialize
    loaded = TPCPEnvelope.model_validate_json(json_str)
    assert loaded.header.intent == Intent.TASK_REQUEST
    assert loaded.header.sender_id == identity1.agent_id


# ── Task 1: base64 field validators ──────────────────────────────────────────

def test_base64_validation_rejects_invalid():
    with pytest.raises(Exception):
        ImagePayload(data_base64="not-valid-base64!!!", mime_type="image/png")

def test_base64_validation_accepts_valid():
    valid_b64 = base64.b64encode(b"test image data").decode()
    img = ImagePayload(data_base64=valid_b64, mime_type="image/png")
    assert img.data_base64 == valid_b64

def test_audio_base64_rejects_invalid():
    with pytest.raises(Exception):
        AudioPayload(data_base64="!!!not-base64!!!", mime_type="audio/wav")

def test_audio_base64_accepts_valid():
    valid_b64 = base64.b64encode(b"audio data").decode()
    a = AudioPayload(data_base64=valid_b64, mime_type="audio/wav")
    assert a.data_base64 == valid_b64

def test_video_base64_rejects_invalid():
    with pytest.raises(Exception):
        VideoPayload(data_base64="!!!not-base64!!!", mime_type="video/mp4")

def test_video_base64_accepts_valid():
    valid_b64 = base64.b64encode(b"video data").decode()
    v = VideoPayload(data_base64=valid_b64, mime_type="video/mp4")
    assert v.data_base64 == valid_b64

def test_binary_base64_rejects_invalid():
    with pytest.raises(Exception):
        BinaryPayload(data_base64="!!!not-base64!!!")

def test_binary_base64_accepts_valid():
    valid_b64 = base64.b64encode(b"binary data").decode()
    b = BinaryPayload(data_base64=valid_b64)
    assert b.data_base64 == valid_b64


# ── Task 2: TelemetryPayload soft validators ──────────────────────────────────

def test_telemetry_source_protocol_known_accepted():
    tp = TelemetryPayload(
        sensor_id="s1", unit="rpm",
        readings=[TelemetryReading(value=1.0, timestamp_ms=1000)],
        source_protocol="opcua"
    )
    assert tp.source_protocol == "opcua"

def test_telemetry_source_protocol_unknown_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="tpcp.schemas.envelope"):
        tp = TelemetryPayload(
            sensor_id="s1", unit="rpm",
            readings=[TelemetryReading(value=1.0, timestamp_ms=1000)],
            source_protocol="zigbee"
        )
    assert tp.source_protocol == "zigbee"

def test_telemetry_quality_unknown_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="tpcp.schemas.envelope"):
        tr = TelemetryReading(value=1.0, timestamp_ms=1000, quality="Unknown")
    assert tr.quality == "Unknown"


# ── AckInfo & ChunkInfo TESTS ──────────────────────────────────────

def test_ack_info_serialization():
    from uuid import uuid4
    mid = uuid4()
    ack = AckInfo(acked_message_id=mid)
    d = ack.model_dump()
    assert d["acked_message_id"] == mid


def test_chunk_info_serialization():
    from uuid import uuid4
    tid = uuid4()
    ci = ChunkInfo(chunk_index=0, total_chunks=5, transfer_id=tid)
    d = ci.model_dump()
    assert d["chunk_index"] == 0
    assert d["total_chunks"] == 5
