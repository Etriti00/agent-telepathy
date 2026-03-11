# Copyright (c) 2026 Principal Systems Architect
# This file is part of TPCP.
# 
# TPCP is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# TPCP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with TPCP. If not, see <https://www.gnu.org/licenses/>.
# 
# For commercial licensing inquiries, see COMMERCIAL_LICENSE.md

"""
Core schemas for the TPCP protocol.
Utilises Pydantic for strict validation of messages between autonomous agents.
All payload types use a discriminated union via `payload_type` for unambiguous parsing.
"""

from enum import Enum
from typing import Any, Annotated, Dict, List, Literal, Optional, Union
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Discriminator, Field, Tag, model_validator


class Intent(str, Enum):
    """The intent or purpose of a TPCP message."""
    HANDSHAKE = "Handshake"
    TASK_REQUEST = "Task_Request"
    STATE_SYNC = "State_Sync"
    STATE_SYNC_VECTOR = "State_Sync_Vector"
    CRITIQUE = "Critique"
    TERMINATE = "Terminate"


class AgentIdentity(BaseModel):
    """Defines the cryptographic and functional identity of an agent."""
    agent_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the agent.")
    framework: str = Field(..., description="The framework powering the agent (e.g., 'CrewAI', 'LangGraph').")
    capabilities: List[str] = Field(default_factory=list, description="List of capabilities the agent possesses.")
    public_key: str = Field(..., description="Public key for verifying signatures (base64-encoded Ed25519).")


class MessageHeader(BaseModel):
    """Header information for routing and metadata."""
    message_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this message.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="Time the message was created in UTC."
    )
    sender_id: UUID = Field(..., description="Agent ID of the sender.")
    receiver_id: UUID = Field(..., description="Agent ID of the intended receiver.")
    intent: Intent = Field(..., description="The semantic intent of the message.")
    ttl: int = Field(default=30, ge=0, description="Time-to-live in hops to prevent infinite loops.")
    protocol_version: str = Field(default="0.2.0", description="TPCP protocol version for compatibility checks.")


# ── DISCRIMINATED PAYLOAD TYPES ────────────────────────────────────────

class TextPayload(BaseModel):
    """A standard text-based message payload."""
    payload_type: Literal["text"] = "text"
    content: str = Field(..., description="The text content of the message.")
    language: str = Field(default="en", description="ISO 639-1 language code.")


class VectorEmbeddingPayload(BaseModel):
    """Payload for sharing semantic state via vector embeddings."""
    payload_type: Literal["vector_embedding"] = "vector_embedding"
    model_id: str = Field(..., description="The model used to generate the embedding.")
    dimensions: int = Field(..., gt=0, description="The dimension size of the vector.")
    vector: List[float] = Field(..., description="The vector embedding.")
    raw_text_fallback: Optional[str] = Field(default=None, description="Optional original text for non-vector nodes.")

    @model_validator(mode='after')
    def validate_embedding(self) -> 'VectorEmbeddingPayload':
        """Validates that the vector matches declared dimensions and known model architectures."""
        length = len(self.vector)
        if length != self.dimensions:
            raise ValueError(f"Vector length ({length}) does not match declared dimensions ({self.dimensions}).")
        
        KNOWN_MODELS = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            "all-MiniLM-L6-v2": 384
        }
        
        if self.model_id in KNOWN_MODELS:
            expected_dim = KNOWN_MODELS[self.model_id]
            if self.dimensions != expected_dim:
                raise ValueError(
                    f"Invalid dimension {self.dimensions} for model '{self.model_id}'. "
                    f"Expected exactly {expected_dim} dimensions."
                )
        
        return self


class CRDTSyncPayload(BaseModel):
    """Payload for synchronizing distributed state using CRDTs."""
    payload_type: Literal["crdt_sync"] = "crdt_sync"
    crdt_type: str = Field(..., description="The type of CRDT (e.g., 'LWW-Map').")
    state: Dict[str, Any] = Field(..., description="The merged dictionary state of the CRDT.")
    vector_clock: Dict[str, int] = Field(..., description="Vector clock mapping agent IDs to logical timestamps.")


# Discriminated union using payload_type field — prevents silent fallthrough
def _get_payload_type(data: Any) -> str:
    if isinstance(data, dict):
        return data.get("payload_type", "text")
    return getattr(data, "payload_type", "text")


Payload = Annotated[
    Union[
        Annotated[TextPayload, Tag("text")],
        Annotated[VectorEmbeddingPayload, Tag("vector_embedding")],
        Annotated[CRDTSyncPayload, Tag("crdt_sync")],
    ],
    Discriminator(_get_payload_type)
]


class TPCPEnvelope(BaseModel):
    """The root object combining header, payload, and a cryptographic signature."""
    header: MessageHeader
    payload: Payload
    signature: Optional[str] = Field(default=None, description="Cryptographic signature of the payload.")
