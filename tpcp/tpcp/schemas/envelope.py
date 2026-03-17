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
Defines all payload types for multimodal AI agent communication:
- Text, Vector Embeddings, CRDT State, Images, Audio, Video, and raw Binary.
All payload types use a discriminated union via `payload_type` for unambiguous parsing.
"""

import base64 as _base64
from enum import Enum
from typing import Any, Annotated, Dict, List, Literal, Optional, Union
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Discriminator, Field, Tag, field_validator, model_validator


PROTOCOL_VERSION = "0.4.0"


class Intent(str, Enum):
    """The intent or purpose of a TPCP message."""
    HANDSHAKE = "Handshake"
    TASK_REQUEST = "Task_Request"
    STATE_SYNC = "State_Sync"
    STATE_SYNC_VECTOR = "State_Sync_Vector"
    MEDIA_SHARE = "Media_Share"
    CRITIQUE = "Critique"
    TERMINATE = "Terminate"
    ACK = "ACK"
    NACK = "NACK"
    BROADCAST = "Broadcast"


class AgentIdentity(BaseModel):
    """Defines the cryptographic and functional identity of an agent."""
    agent_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the agent.")
    framework: str = Field(..., description="The framework powering the agent (e.g., 'CrewAI', 'LangGraph').")
    capabilities: List[str] = Field(default_factory=list, description="List of capabilities the agent possesses.")
    public_key: str = Field(..., description="Public key for verifying signatures (base64-encoded Ed25519).")
    modality: List[str] = Field(
        default_factory=lambda: ["text"],
        description="List of modalities this agent supports (e.g., ['text', 'image', 'audio', 'video'])."
    )


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
    protocol_version: str = Field(default=PROTOCOL_VERSION, description="TPCP protocol version for compatibility checks.")


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


# ── MULTIMODAL PAYLOAD TYPES ──────────────────────────────────────────

class ImagePayload(BaseModel):
    """
    Payload for sharing images between agents.
    Supports vision models (GPT-4V, Gemini Vision, LLaVA) and image generators (DALL-E, Midjourney).
    """
    payload_type: Literal["image"] = "image"
    data_base64: str = Field(..., description="The image data encoded as a base64 string.")
    mime_type: str = Field(
        default="image/png", 
        description="MIME type of the image (e.g., 'image/png', 'image/jpeg', 'image/webp')."
    )
    width: Optional[int] = Field(default=None, description="Image width in pixels.")
    height: Optional[int] = Field(default=None, description="Image height in pixels.")
    source_model: Optional[str] = Field(
        default=None, 
        description="The model that generated or analyzed this image (e.g., 'dall-e-3', 'stable-diffusion-xl')."
    )
    caption: Optional[str] = Field(
        default=None,
        description="Optional text description of the image for agents that cannot process visual data."
    )

    @field_validator('data_base64')
    @classmethod
    def validate_base64(cls, v: str) -> str:
        try:
            _base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("data_base64 must be valid base64-encoded data")
        return v


class AudioPayload(BaseModel):
    """
    Payload for sharing audio between agents.
    Supports TTS models (ElevenLabs, OpenAI TTS), STT models (Whisper), and voice agents.
    """
    payload_type: Literal["audio"] = "audio"
    data_base64: str = Field(..., description="The audio data encoded as a base64 string.")
    mime_type: str = Field(
        default="audio/wav",
        description="MIME type of the audio (e.g., 'audio/wav', 'audio/mp3', 'audio/ogg')."
    )
    sample_rate: Optional[int] = Field(default=None, description="Audio sample rate in Hz (e.g., 16000, 44100).")
    duration_seconds: Optional[float] = Field(default=None, description="Duration of the audio in seconds.")
    source_model: Optional[str] = Field(
        default=None,
        description="The model that generated or transcribed this audio (e.g., 'whisper-1', 'elevenlabs-v2')."
    )
    transcript: Optional[str] = Field(
        default=None,
        description="Optional text transcript for agents that cannot process audio."
    )

    @field_validator('data_base64')
    @classmethod
    def validate_base64(cls, v: str) -> str:
        try:
            _base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("data_base64 must be valid base64-encoded data")
        return v


class VideoPayload(BaseModel):
    """
    Payload for sharing video between agents.
    Supports video generation models (Sora, Runway), video analysis, and screen recordings.
    """
    payload_type: Literal["video"] = "video"
    data_base64: str = Field(..., description="The video data encoded as a base64 string.")
    mime_type: str = Field(
        default="video/mp4",
        description="MIME type of the video (e.g., 'video/mp4', 'video/webm')."
    )
    width: Optional[int] = Field(default=None, description="Video width in pixels.")
    height: Optional[int] = Field(default=None, description="Video height in pixels.")
    duration_seconds: Optional[float] = Field(default=None, description="Duration in seconds.")
    fps: Optional[float] = Field(default=None, description="Frames per second.")
    source_model: Optional[str] = Field(
        default=None,
        description="The model that generated this video (e.g., 'sora-1', 'runway-gen3')."
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional text description for agents that cannot process video."
    )

    @field_validator('data_base64')
    @classmethod
    def validate_base64(cls, v: str) -> str:
        try:
            _base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("data_base64 must be valid base64-encoded data")
        return v


class BinaryPayload(BaseModel):
    """
    Generic binary payload for any data type not covered by the specific payload types.
    Use this for documents (PDFs), 3D models, datasets, or any custom binary format.
    """
    payload_type: Literal["binary"] = "binary"
    data_base64: str = Field(..., description="The raw binary data encoded as a base64 string.")
    mime_type: str = Field(
        default="application/octet-stream",
        description="MIME type of the data (e.g., 'application/pdf', 'model/gltf+json')."
    )
    filename: Optional[str] = Field(
        default=None,
        description="Optional original filename for context."
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional text description of the binary content."
    )

    @field_validator('data_base64')
    @classmethod
    def validate_base64(cls, v: str) -> str:
        try:
            _base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("data_base64 must be valid base64-encoded data")
        return v


# ── TELEMETRY PAYLOAD TYPE ────────────────────────────────────────────

class TelemetryReading(BaseModel):
    """A single sensor reading with timestamp and optional quality indicator."""
    value: float = Field(..., description="Sensor reading value.")
    timestamp_ms: int = Field(..., description="Unix epoch timestamp in milliseconds.")
    quality: Optional[str] = Field(default=None, description="OPC-UA quality code: 'Good', 'Bad', or 'Uncertain'.")

    @field_validator('quality')
    @classmethod
    def warn_unknown_quality(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("Good", "Bad", "Uncertain"):
            import logging
            logging.getLogger(__name__).warning(f"Unknown quality value: {v!r}. Expected 'Good', 'Bad', or 'Uncertain'.")
        return v


class TelemetryPayload(BaseModel):
    """
    Payload for industrial/IoT telemetry data from hardware protocols.
    Supports OPC-UA, Modbus, CANbus, and MQTT sensor streams.
    """
    payload_type: Literal["telemetry"] = "telemetry"
    sensor_id: str = Field(..., description="Unique sensor identifier, e.g. 'opcua_ns2_i_2' or 'can_0x123'.")
    unit: str = Field(..., description="Engineering unit, e.g. 'rpm', 'celsius', 'bar'.")
    readings: List[TelemetryReading] = Field(..., description="Batch of timestamped readings from this sensor.")
    source_protocol: str = Field(..., description="Origin protocol: 'opcua', 'modbus', 'canbus', or 'mqtt'.")

    @field_validator('source_protocol')
    @classmethod
    def warn_unknown_protocol(cls, v: str) -> str:
        known = {"opcua", "modbus", "canbus", "mqtt"}
        if v not in known:
            import logging
            logging.getLogger(__name__).warning(f"Unknown source_protocol: {v!r}. Known: {known}")
        return v


# ── ACK / CHUNK METADATA MODELS ───────────────────────────────────────

class AckInfo(BaseModel):
    """Acknowledgement metadata referencing the message being acknowledged."""
    acked_message_id: UUID = Field(..., description="UUID of the message being acknowledged.")


class ChunkInfo(BaseModel):
    """Chunked-transfer metadata for large payloads split across multiple messages."""
    chunk_index: int = Field(..., ge=0, description="Zero-based index of this chunk.")
    total_chunks: int = Field(..., ge=1, description="Total number of chunks in the transfer.")
    transfer_id: UUID = Field(..., description="Unique identifier for this chunked transfer.")


# ── DISCRIMINATED UNION ───────────────────────────────────────────────

def _get_payload_type(data: Any) -> str:
    if isinstance(data, dict):
        pt = data.get("payload_type")
    else:
        pt = getattr(data, "payload_type", None)
    if pt is None:
        raise ValueError("Missing 'payload_type' field in payload")
    return pt


Payload = Annotated[
    Union[
        Annotated[TextPayload, Tag("text")],
        Annotated[VectorEmbeddingPayload, Tag("vector_embedding")],
        Annotated[CRDTSyncPayload, Tag("crdt_sync")],
        Annotated[ImagePayload, Tag("image")],
        Annotated[AudioPayload, Tag("audio")],
        Annotated[VideoPayload, Tag("video")],
        Annotated[BinaryPayload, Tag("binary")],
        Annotated[TelemetryPayload, Tag("telemetry")],
    ],
    Discriminator(_get_payload_type)
]


class TPCPEnvelope(BaseModel):
    """The root object combining header, payload, and a cryptographic signature."""
    header: MessageHeader
    payload: Payload
    signature: Optional[str] = Field(default=None, description="Cryptographic signature of the payload.")
    ack_info: Optional[AckInfo] = Field(default=None, description="Acknowledgement metadata; present when intent is ACK or NACK.")
    chunk_info: Optional[ChunkInfo] = Field(default=None, description="Chunked transfer metadata; present when this envelope is a chunk of a larger payload.")
