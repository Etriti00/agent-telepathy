use alloc::{string::String, vec::Vec, vec};
use alloc::collections::BTreeMap;
use base64::{Engine as _, engine::general_purpose};
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
    vec!["text".into()]
}

/// Present on every TPCP message.
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

/// Acknowledgement metadata referencing the message being acknowledged.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AckInfo {
    pub acked_message_id: String,
}

/// Chunked-transfer metadata for large payloads.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkInfo {
    pub chunk_index: u32,
    pub total_chunks: u32,
    pub transfer_id: String,
}

/// Top-level TPCP message container.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TPCPEnvelope {
    pub header: MessageHeader,
    pub payload: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ack_info: Option<AckInfo>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_info: Option<ChunkInfo>,
}

// --- Payload types ---

/// Plain text content payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextPayload {
    pub payload_type: String,
    pub content: String,
    #[serde(default = "default_language")]
    pub language: String,
}

fn default_language() -> String {
    "en".into()
}

impl TextPayload {
    pub fn new(content: impl Into<String>) -> Self {
        Self {
            payload_type: "text".into(),
            content: content.into(),
            language: "en".into(),
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.content.is_empty() {
            return Err("content must not be empty".into());
        }
        Ok(())
    }
}

/// Semantic vector embedding payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorEmbeddingPayload {
    pub payload_type: String,
    pub model_id: String,
    pub dimensions: u32,
    pub vector: Vec<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_text_fallback: Option<String>,
}

impl VectorEmbeddingPayload {
    pub fn new(model_id: impl Into<String>, dimensions: u32, vector: Vec<f64>) -> Self {
        Self {
            payload_type: "vector_embedding".into(),
            model_id: model_id.into(),
            dimensions,
            vector,
            raw_text_fallback: None,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.model_id.is_empty() {
            return Err("model_id must not be empty".into());
        }
        if self.dimensions == 0 {
            return Err("dimensions must be greater than zero".into());
        }
        if self.vector.len() != self.dimensions as usize {
            return Err(alloc::format!(
                "vector length {} does not match dimensions {}",
                self.vector.len(),
                self.dimensions
            ));
        }
        Ok(())
    }
}

/// CRDT state synchronization payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CRDTSyncPayload {
    pub payload_type: String,
    pub crdt_type: String,
    pub state: Value,
    pub vector_clock: BTreeMap<String, i64>,
}

impl CRDTSyncPayload {
    pub fn new(crdt_type: impl Into<String>, state: Value, vector_clock: BTreeMap<String, i64>) -> Self {
        Self {
            payload_type: "crdt_sync".into(),
            crdt_type: crdt_type.into(),
            state,
            vector_clock,
        }
    }
}

/// Image data payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImagePayload {
    pub payload_type: String,
    pub data_base64: String,
    #[serde(default = "default_image_mime")]
    pub mime_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub caption: Option<String>,
}

fn default_image_mime() -> String { "image/png".into() }

impl ImagePayload {
    pub fn new(data_base64: impl Into<String>, mime_type: impl Into<String>) -> Self {
        Self {
            payload_type: "image".into(),
            data_base64: data_base64.into(),
            mime_type: mime_type.into(),
            width: None, height: None, source_model: None, caption: None,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if !self.mime_type.starts_with("image/") {
            return Err(alloc::format!(
                "mime_type must start with 'image/', got '{}'",
                self.mime_type
            ));
        }
        if self.data_base64.is_empty() {
            return Err("data_base64 must not be empty".into());
        }
        general_purpose::STANDARD
            .decode(&self.data_base64)
            .map_err(|e| alloc::format!("data_base64 is not valid base64: {}", e))?;
        Ok(())
    }
}

/// Audio data payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioPayload {
    pub payload_type: String,
    pub data_base64: String,
    #[serde(default = "default_audio_mime")]
    pub mime_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sample_rate: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_seconds: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transcript: Option<String>,
}

fn default_audio_mime() -> String { "audio/wav".into() }

impl AudioPayload {
    pub fn new(data_base64: impl Into<String>, mime_type: impl Into<String>) -> Self {
        Self {
            payload_type: "audio".into(),
            data_base64: data_base64.into(),
            mime_type: mime_type.into(),
            sample_rate: None, duration_seconds: None, source_model: None, transcript: None,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if !self.mime_type.starts_with("audio/") {
            return Err(alloc::format!(
                "mime_type must start with 'audio/', got '{}'",
                self.mime_type
            ));
        }
        if self.data_base64.is_empty() {
            return Err("data_base64 must not be empty".into());
        }
        general_purpose::STANDARD
            .decode(&self.data_base64)
            .map_err(|e| alloc::format!("data_base64 is not valid base64: {}", e))?;
        Ok(())
    }
}

/// Video data payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoPayload {
    pub payload_type: String,
    pub data_base64: String,
    #[serde(default = "default_video_mime")]
    pub mime_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_seconds: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fps: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

fn default_video_mime() -> String { "video/mp4".into() }

impl VideoPayload {
    pub fn new(data_base64: impl Into<String>, mime_type: impl Into<String>) -> Self {
        Self {
            payload_type: "video".into(),
            data_base64: data_base64.into(),
            mime_type: mime_type.into(),
            width: None, height: None, duration_seconds: None,
            fps: None, source_model: None, description: None,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if !self.mime_type.starts_with("video/") {
            return Err(alloc::format!(
                "mime_type must start with 'video/', got '{}'",
                self.mime_type
            ));
        }
        if self.data_base64.is_empty() {
            return Err("data_base64 must not be empty".into());
        }
        general_purpose::STANDARD
            .decode(&self.data_base64)
            .map_err(|e| alloc::format!("data_base64 is not valid base64: {}", e))?;
        Ok(())
    }
}

/// Generic binary data payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BinaryPayload {
    pub payload_type: String,
    pub data_base64: String,
    #[serde(default = "default_binary_mime")]
    pub mime_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filename: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

fn default_binary_mime() -> String { "application/octet-stream".into() }

impl BinaryPayload {
    pub fn new(data_base64: impl Into<String>, mime_type: impl Into<String>) -> Self {
        Self {
            payload_type: "binary".into(),
            data_base64: data_base64.into(),
            mime_type: mime_type.into(),
            filename: None, description: None,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.mime_type.is_empty() {
            return Err("mime_type must not be empty".into());
        }
        if self.data_base64.is_empty() {
            return Err("data_base64 must not be empty".into());
        }
        general_purpose::STANDARD
            .decode(&self.data_base64)
            .map_err(|e| alloc::format!("data_base64 is not valid base64: {}", e))?;
        Ok(())
    }
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

    pub fn validate(&self) -> Result<(), String> {
        if self.sensor_id.is_empty() {
            return Err("sensor_id must not be empty".into());
        }
        if self.unit.is_empty() {
            return Err("unit must not be empty".into());
        }
        if self.readings.is_empty() {
            return Err("readings must not be empty".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use alloc::string::ToString;

    #[test]
    fn intent_serialization_matches_wire_format() {
        let cases = vec![
            (Intent::Handshake, "\"Handshake\""),
            (Intent::TaskRequest, "\"Task_Request\""),
            (Intent::StateSync, "\"State_Sync\""),
            (Intent::StateSyncVector, "\"State_Sync_Vector\""),
            (Intent::MediaShare, "\"Media_Share\""),
            (Intent::Critique, "\"Critique\""),
            (Intent::Terminate, "\"Terminate\""),
            (Intent::Ack, "\"ACK\""),
            (Intent::Nack, "\"NACK\""),
            (Intent::Broadcast, "\"Broadcast\""),
        ];
        for (intent, expected) in cases {
            let json = serde_json::to_string(&intent).unwrap();
            assert_eq!(json, expected, "Intent wire format mismatch");
        }
    }

    #[test]
    fn text_payload_round_trip() {
        let payload = TextPayload::new("hello world");
        let json = serde_json::to_string(&payload).unwrap();
        let parsed: TextPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.payload_type, "text");
        assert_eq!(parsed.content, "hello world");
        assert_eq!(parsed.language, "en");
    }

    #[test]
    fn envelope_with_ack_and_chunk_info() {
        let envelope = TPCPEnvelope {
            header: MessageHeader {
                message_id: "msg-1".to_string(),
                timestamp: "2026-03-15T00:00:00Z".to_string(),
                sender_id: "sender-1".to_string(),
                receiver_id: "receiver-1".to_string(),
                intent: Intent::Ack,
                ttl: 30,
                protocol_version: PROTOCOL_VERSION.to_string(),
            },
            payload: serde_json::json!({"payload_type": "text", "content": "ack"}),
            signature: Some("sig123".to_string()),
            ack_info: Some(AckInfo {
                acked_message_id: "orig-msg-1".to_string(),
            }),
            chunk_info: Some(ChunkInfo {
                chunk_index: 0,
                total_chunks: 3,
                transfer_id: "transfer-1".to_string(),
            }),
        };

        let json = serde_json::to_string(&envelope).unwrap();
        let parsed: TPCPEnvelope = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.ack_info.as_ref().unwrap().acked_message_id, "orig-msg-1");
        assert_eq!(parsed.chunk_info.as_ref().unwrap().chunk_index, 0);
        assert_eq!(parsed.chunk_info.as_ref().unwrap().total_chunks, 3);
        assert_eq!(parsed.chunk_info.as_ref().unwrap().transfer_id, "transfer-1");
    }

    #[test]
    fn telemetry_payload_round_trip() {
        let payload = TelemetryPayload::new(
            "sensor_1", "celsius", "opcua",
            vec![TelemetryReading { value: 42.5, timestamp_ms: 1000, quality: Some("Good".to_string()) }],
        );
        let json = serde_json::to_string(&payload).unwrap();
        let parsed: TelemetryPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.sensor_id, "sensor_1");
        assert_eq!(parsed.readings.len(), 1);
        assert_eq!(parsed.readings[0].value, 42.5);
    }
}

#[cfg(test)]
mod validation_tests {
    use super::*;

    #[test]
    fn text_payload_rejects_empty() {
        let p = TextPayload { payload_type: "text".into(), content: "".into(), language: "en".into() };
        assert!(p.validate().is_err());
    }

    #[test]
    fn text_payload_accepts_nonempty() {
        let p = TextPayload { payload_type: "text".into(), content: "hello".into(), language: "en".into() };
        assert!(p.validate().is_ok());
    }

    #[test]
    fn vector_rejects_dimension_mismatch() {
        let p = VectorEmbeddingPayload {
            payload_type: "vector_embedding".into(),
            model_id: "test".into(),
            dimensions: 3,
            vector: vec![1.0, 2.0],
            raw_text_fallback: None,
        };
        assert!(p.validate().is_err());
    }

    #[test]
    fn vector_accepts_matching_dimensions() {
        let p = VectorEmbeddingPayload {
            payload_type: "vector_embedding".into(),
            model_id: "test".into(),
            dimensions: 3,
            vector: vec![1.0, 2.0, 3.0],
            raw_text_fallback: None,
        };
        assert!(p.validate().is_ok());
    }

    #[test]
    fn image_payload_rejects_bad_mime() {
        let p = ImagePayload::new("aGVsbG8=", "text/plain");
        assert!(p.validate().is_err());
    }

    #[test]
    fn image_payload_rejects_invalid_base64() {
        let p = ImagePayload::new("not!!valid@@base64", "image/png");
        assert!(p.validate().is_err());
    }

    #[test]
    fn image_payload_accepts_valid() {
        // "hello" base64-encoded
        let p = ImagePayload::new("aGVsbG8=", "image/png");
        assert!(p.validate().is_ok());
    }

    #[test]
    fn audio_payload_rejects_bad_mime() {
        let p = AudioPayload::new("aGVsbG8=", "image/png");
        assert!(p.validate().is_err());
    }

    #[test]
    fn audio_payload_accepts_valid() {
        let p = AudioPayload::new("aGVsbG8=", "audio/wav");
        assert!(p.validate().is_ok());
    }

    #[test]
    fn video_payload_rejects_bad_mime() {
        let p = VideoPayload::new("aGVsbG8=", "audio/wav");
        assert!(p.validate().is_err());
    }

    #[test]
    fn video_payload_accepts_valid() {
        let p = VideoPayload::new("aGVsbG8=", "video/mp4");
        assert!(p.validate().is_ok());
    }

    #[test]
    fn binary_payload_rejects_empty_data() {
        let p = BinaryPayload::new("", "application/octet-stream");
        assert!(p.validate().is_err());
    }

    #[test]
    fn binary_payload_accepts_valid() {
        let p = BinaryPayload::new("aGVsbG8=", "application/octet-stream");
        assert!(p.validate().is_ok());
    }

    #[test]
    fn telemetry_rejects_empty_sensor_id() {
        let p = TelemetryPayload {
            payload_type: "telemetry".into(),
            sensor_id: "".into(),
            unit: "celsius".into(),
            readings: vec![TelemetryReading { value: 1.0, timestamp_ms: 0, quality: None }],
            source_protocol: "opcua".into(),
        };
        assert!(p.validate().is_err());
    }

    #[test]
    fn telemetry_rejects_empty_unit() {
        let p = TelemetryPayload {
            payload_type: "telemetry".into(),
            sensor_id: "s1".into(),
            unit: "".into(),
            readings: vec![TelemetryReading { value: 1.0, timestamp_ms: 0, quality: None }],
            source_protocol: "opcua".into(),
        };
        assert!(p.validate().is_err());
    }

    #[test]
    fn telemetry_rejects_empty_readings() {
        let p = TelemetryPayload {
            payload_type: "telemetry".into(),
            sensor_id: "s1".into(),
            unit: "celsius".into(),
            readings: vec![],
            source_protocol: "opcua".into(),
        };
        assert!(p.validate().is_err());
    }

    #[test]
    fn telemetry_accepts_valid() {
        let p = TelemetryPayload::new(
            "sensor_1", "celsius", "opcua",
            vec![TelemetryReading { value: 42.5, timestamp_ms: 1000, quality: None }],
        );
        assert!(p.validate().is_ok());
    }
}
