// Package tpcp implements the Telepathy Communication Protocol Go SDK.
package tpcp

import "encoding/json"

// PROTOCOL_VERSION is the TPCP version implemented by this SDK.
const PROTOCOL_VERSION = "0.4.0"

// BROADCAST_ID is the reserved UUID for broadcast/multicast messages.
const BROADCAST_ID = "00000000-0000-0000-0000-000000000000"

// Intent identifies the purpose of a TPCP message.
// Wire-format values must match the canonical Python/TS SDK exactly.
type Intent string

const (
	IntentHandshake       Intent = "Handshake"
	IntentTaskRequest     Intent = "Task_Request"
	IntentTaskResponse    Intent = "Task_Response"
	IntentStateSync       Intent = "State_Sync"
	IntentStateSyncVector Intent = "State_Sync_Vector"
	IntentMemorySync      Intent = "Memory_Sync"
	IntentMediaShare      Intent = "Media_Share"
	IntentCritique        Intent = "Critique"
	IntentTerminate       Intent = "Terminate"
	IntentACK             Intent = "ACK"
	IntentNACK            Intent = "NACK"
	IntentBroadcast       Intent = "Broadcast"
)

// AgentIdentity describes a TPCP agent.
// Field names match the canonical Python SDK (public_key, framework, capabilities, modality).
type AgentIdentity struct {
	AgentID      string   `json:"agent_id"`
	Framework    string   `json:"framework"`
	Capabilities []string `json:"capabilities"`
	PublicKey    string   `json:"public_key"`
	Modality     []string `json:"modality"`
}

// MessageHeader is the envelope header present on every TPCP message.
// Timestamp is an ISO 8601 UTC string to match Python's datetime serialization.
type MessageHeader struct {
	MessageID       string `json:"message_id"`
	Timestamp       string `json:"timestamp"`
	SenderID        string `json:"sender_id"`
	ReceiverID      string `json:"receiver_id"`
	Intent          Intent `json:"intent"`
	TTL             int    `json:"ttl"`
	ProtocolVersion string `json:"protocol_version"`
}

// TPCPEnvelope is the top-level message container.
type TPCPEnvelope struct {
	Header    MessageHeader   `json:"header"`
	Payload   json.RawMessage `json:"payload"`
	Signature string          `json:"signature,omitempty"`
}

// --- Payload types ---

// TextPayload carries plain text content.
type TextPayload struct {
	PayloadType string `json:"payload_type"`
	Content     string `json:"content"`
	Language    string `json:"language,omitempty"`
}

// BinaryPayload carries base64-encoded binary data.
type BinaryPayload struct {
	PayloadType string `json:"payload_type"`
	DataBase64  string `json:"data_base64"`
	MimeType    string `json:"mime_type"`
	Description string `json:"description,omitempty"`
}

// TaskPayload describes an agent task.
type TaskPayload struct {
	PayloadType string                 `json:"payload_type"`
	TaskName    string                 `json:"task_name"`
	Parameters  map[string]interface{} `json:"parameters,omitempty"`
	Result      interface{}            `json:"result,omitempty"`
}

// StatePayload carries key-value state for CRDT sync.
type StatePayload struct {
	PayloadType string                 `json:"payload_type"`
	State       map[string]interface{} `json:"state"`
	TimestampMs int64                  `json:"timestamp_ms"`
}

// MemoryPayload carries CRDT memory updates.
type MemoryPayload struct {
	PayloadType string                 `json:"payload_type"`
	Updates     map[string]interface{} `json:"updates"`
	TimestampMs int64                  `json:"timestamp_ms"`
}

// ThoughtPayload carries an agent's internal reasoning step.
type ThoughtPayload struct {
	PayloadType string  `json:"payload_type"`
	Thought     string  `json:"thought"`
	Confidence  float64 `json:"confidence,omitempty"`
}

// TelemetryReading is a single sensor reading.
type TelemetryReading struct {
	Value       float64 `json:"value"`
	TimestampMs int64   `json:"timestamp_ms"`
	Quality     string  `json:"quality,omitempty"`
}

// TelemetryPayload carries industrial IoT sensor data.
type TelemetryPayload struct {
	PayloadType    string             `json:"payload_type"`
	SensorID       string             `json:"sensor_id"`
	Unit           string             `json:"unit"`
	Readings       []TelemetryReading `json:"readings"`
	SourceProtocol string             `json:"source_protocol"`
}

// NewTextPayload creates a TextPayload with the correct payload_type tag.
func NewTextPayload(content string) *TextPayload {
	return &TextPayload{PayloadType: "text", Content: content, Language: "en"}
}

// NewTelemetryPayload creates a TelemetryPayload.
func NewTelemetryPayload(sensorID, unit, sourceProtocol string, readings []TelemetryReading) *TelemetryPayload {
	return &TelemetryPayload{
		PayloadType:    "telemetry",
		SensorID:       sensorID,
		Unit:           unit,
		Readings:       readings,
		SourceProtocol: sourceProtocol,
	}
}
