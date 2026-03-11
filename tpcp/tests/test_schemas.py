import pytest
from uuid import UUID
from pydantic import ValidationError

from tpcp.schemas.envelope import (
    AgentIdentity,
    Intent,
    MessageHeader,
    TextPayload,
    VectorEmbeddingPayload,
    CRDTSyncPayload,
    TPCPEnvelope
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
