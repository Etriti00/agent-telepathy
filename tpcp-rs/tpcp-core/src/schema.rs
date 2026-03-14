use alloc::{string::String, vec::Vec};
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// TPCP protocol version implemented by this crate.
pub const PROTOCOL_VERSION: &str = "0.4.0";

/// Reserved UUID for broadcast/multicast messages.
pub const BROADCAST_ID: &str = "00000000-0000-0000-0000-000000000000";

/// Intent identifies the purpose of a TPCP message.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum Intent {
    Connect,
    Disconnect,
    Handshake,
    TaskRequest,
    TaskResponse,
    StateSync,
    MemorySync,
    MediaShare,
    #[serde(rename = "ACK")]
    Ack,
    #[serde(rename = "NACK")]
    Nack,
    Broadcast,
}

/// Describes a TPCP agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentIdentity {
    pub agent_id: String,
    pub agent_type: String,
    pub public_key_b64: String,
}

/// Present on every TPCP message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeader {
    pub message_id: String,
    pub sender_id: String,
    pub receiver_id: String,
    pub intent: Intent,
    pub timestamp_ms: i64,
    pub protocol_version: String,
}

/// Top-level TPCP message container.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TPCPEnvelope {
    pub header: MessageHeader,
    pub payload: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub signature: Option<String>,
}

/// Single sensor telemetry reading.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelemetryReading {
    pub value: f64,
    pub timestamp_ms: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quality: Option<String>,
}

/// Industrial IoT sensor data payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelemetryPayload {
    pub payload_type: String,
    pub sensor_id: String,
    pub unit: String,
    pub readings: Vec<TelemetryReading>,
    pub source_protocol: String,
}

impl TelemetryPayload {
    pub fn new(sensor_id: impl Into<String>, unit: impl Into<String>,
               source_protocol: impl Into<String>, readings: Vec<TelemetryReading>) -> Self {
        Self {
            payload_type: "telemetry".into(),
            sensor_id: sensor_id.into(),
            unit: unit.into(),
            readings,
            source_protocol: source_protocol.into(),
        }
    }
}
