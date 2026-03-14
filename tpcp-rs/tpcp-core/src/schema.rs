use alloc::{string::String, vec::Vec};
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// TPCP protocol version implemented by this crate.
pub const PROTOCOL_VERSION: &str = "0.4.0";

/// Reserved UUID for broadcast/multicast messages.
pub const BROADCAST_ID: &str = "00000000-0000-0000-0000-000000000000";

/// Intent identifies the purpose of a TPCP message.
/// Wire-format values must match the canonical Python/TS SDK exactly.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Intent {
    #[serde(rename = "Handshake")]
    Handshake,
    #[serde(rename = "Task_Request")]
    TaskRequest,
    #[serde(rename = "State_Sync")]
    StateSync,
    #[serde(rename = "State_Sync_Vector")]
    StateSyncVector,
    #[serde(rename = "Media_Share")]
    MediaShare,
    #[serde(rename = "Critique")]
    Critique,
    #[serde(rename = "Terminate")]
    Terminate,
    #[serde(rename = "ACK")]
    Ack,
    #[serde(rename = "NACK")]
    Nack,
    #[serde(rename = "Broadcast")]
    Broadcast,
}

/// Describes a TPCP agent.
/// Field names match the canonical Python SDK (public_key, framework, capabilities, modality).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentIdentity {
    pub agent_id: String,
    pub framework: String,
    #[serde(default)]
    pub capabilities: Vec<String>,
    pub public_key: String,
    #[serde(default = "default_modality")]
    pub modality: Vec<String>,
}

fn default_modality() -> Vec<String> {
    alloc::vec!["text".into()]
}

/// Present on every TPCP message.
/// Timestamp is an ISO 8601 UTC string to match Python's datetime serialization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeader {
    pub message_id: String,
    pub timestamp: String,
    pub sender_id: String,
    pub receiver_id: String,
    pub intent: Intent,
    #[serde(default = "default_ttl")]
    pub ttl: u32,
    pub protocol_version: String,
}

fn default_ttl() -> u32 {
    30
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
