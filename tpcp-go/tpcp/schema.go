// Package tpcp implements the Telepathy Communication Protocol Go SDK.
package tpcp

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
)

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
	IntentStateSync       Intent = "State_Sync"
	IntentStateSyncVector Intent = "State_Sync_Vector"
	IntentMediaShare      Intent = "Media_Share"
	IntentCritique        Intent = "Critique"
	IntentTerminate       Intent = "Terminate"
	IntentACK             Intent = "ACK"
	IntentNACK            Intent = "NACK"
	IntentBroadcast       Intent = "Broadcast"
)

// AgentIdentity describes a TPCP agent.
type AgentIdentity struct {
	AgentID      string   `json:"agent_id"`
	Framework    string   `json:"framework"`
	Capabilities []string `json:"capabilities"`
	PublicKey    string   `json:"public_key"`
	Modality     []string `json:"modality"`
}

// MessageHeader is the envelope header present on every TPCP message.
type MessageHeader struct {
	MessageID       string `json:"message_id"`
	Timestamp       string `json:"timestamp"`
	SenderID        string `json:"sender_id"`
	ReceiverID      string `json:"receiver_id"`
	Intent          Intent `json:"intent"`
	TTL             int    `json:"ttl"`
	ProtocolVersion string `json:"protocol_version"`
}

// AckInfo references the message being acknowledged.
type AckInfo struct {
	AckedMessageID string `json:"acked_message_id"`
}

// ChunkInfo contains chunked-transfer metadata.
type ChunkInfo struct {
	ChunkIndex  int    `json:"chunk_index"`
	TotalChunks int    `json:"total_chunks"`
	TransferID  string `json:"transfer_id"`
}

// TPCPEnvelope is the top-level message container.
type TPCPEnvelope struct {
	Header    MessageHeader   `json:"header"`
	Payload   json.RawMessage `json:"payload"`
	Signature string          `json:"signature,omitempty"`
	AckInfo   *AckInfo        `json:"ack_info,omitempty"`
	ChunkInfo *ChunkInfo      `json:"chunk_info,omitempty"`
}

// --- Payload types ---

// TextPayload carries plain text content.
type TextPayload struct {
	PayloadType string `json:"payload_type"`
	Content     string `json:"content"`
	Language    string `json:"language,omitempty"`
}

// VectorEmbeddingPayload carries semantic state via vector embeddings.
type VectorEmbeddingPayload struct {
	PayloadType     string    `json:"payload_type"`
	ModelID         string    `json:"model_id"`
	Dimensions      int       `json:"dimensions"`
	Vector          []float64 `json:"vector"`
	RawTextFallback string    `json:"raw_text_fallback,omitempty"`
}

// CRDTSyncPayload carries conflict-free replicated data type state.
type CRDTSyncPayload struct {
	PayloadType string                 `json:"payload_type"`
	CRDTType    string                 `json:"crdt_type"`
	State       map[string]interface{} `json:"state"`
	VectorClock map[string]int         `json:"vector_clock"`
}

// ImagePayload carries base64-encoded image data.
type ImagePayload struct {
	PayloadType string `json:"payload_type"`
	DataBase64  string `json:"data_base64"`
	MimeType    string `json:"mime_type"`
	Width       *int   `json:"width,omitempty"`
	Height      *int   `json:"height,omitempty"`
	SourceModel string `json:"source_model,omitempty"`
	Caption     string `json:"caption,omitempty"`
}

// AudioPayload carries base64-encoded audio data.
type AudioPayload struct {
	PayloadType     string   `json:"payload_type"`
	DataBase64      string   `json:"data_base64"`
	MimeType        string   `json:"mime_type"`
	SampleRate      *int     `json:"sample_rate,omitempty"`
	DurationSeconds *float64 `json:"duration_seconds,omitempty"`
	SourceModel     string   `json:"source_model,omitempty"`
	Transcript      string   `json:"transcript,omitempty"`
}

// VideoPayload carries base64-encoded video data.
type VideoPayload struct {
	PayloadType     string   `json:"payload_type"`
	DataBase64      string   `json:"data_base64"`
	MimeType        string   `json:"mime_type"`
	Width           *int     `json:"width,omitempty"`
	Height          *int     `json:"height,omitempty"`
	DurationSeconds *float64 `json:"duration_seconds,omitempty"`
	FPS             *float64 `json:"fps,omitempty"`
	SourceModel     string   `json:"source_model,omitempty"`
	Description     string   `json:"description,omitempty"`
}

// BinaryPayload carries base64-encoded binary data.
type BinaryPayload struct {
	PayloadType string `json:"payload_type"`
	DataBase64  string `json:"data_base64"`
	MimeType    string `json:"mime_type"`
	Filename    string `json:"filename,omitempty"`
	Description string `json:"description,omitempty"`
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

// --- Constructors ---

// NewTextPayload creates a TextPayload with the correct payload_type tag.
func NewTextPayload(content string) *TextPayload {
	return &TextPayload{PayloadType: "text", Content: content, Language: "en"}
}

// NewVectorEmbeddingPayload creates a VectorEmbeddingPayload.
func NewVectorEmbeddingPayload(modelID string, dimensions int, vector []float64) *VectorEmbeddingPayload {
	return &VectorEmbeddingPayload{
		PayloadType: "vector_embedding",
		ModelID:     modelID,
		Dimensions:  dimensions,
		Vector:      vector,
	}
}

// NewCRDTSyncPayload creates a CRDTSyncPayload.
func NewCRDTSyncPayload(crdtType string, state map[string]interface{}, vectorClock map[string]int) *CRDTSyncPayload {
	return &CRDTSyncPayload{
		PayloadType: "crdt_sync",
		CRDTType:    crdtType,
		State:       state,
		VectorClock: vectorClock,
	}
}

// NewImagePayload creates an ImagePayload.
func NewImagePayload(dataBase64, mimeType string) *ImagePayload {
	return &ImagePayload{
		PayloadType: "image",
		DataBase64:  dataBase64,
		MimeType:    mimeType,
	}
}

// NewAudioPayload creates an AudioPayload.
func NewAudioPayload(dataBase64, mimeType string) *AudioPayload {
	return &AudioPayload{
		PayloadType: "audio",
		DataBase64:  dataBase64,
		MimeType:    mimeType,
	}
}

// NewVideoPayload creates a VideoPayload.
func NewVideoPayload(dataBase64, mimeType string) *VideoPayload {
	return &VideoPayload{
		PayloadType: "video",
		DataBase64:  dataBase64,
		MimeType:    mimeType,
	}
}

// NewBinaryPayload creates a BinaryPayload.
func NewBinaryPayload(dataBase64, mimeType string) *BinaryPayload {
	return &BinaryPayload{
		PayloadType: "binary",
		DataBase64:  dataBase64,
		MimeType:    mimeType,
	}
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

// --- Validate() methods ---

// Validate checks that TextPayload has non-empty content.
func (p *TextPayload) Validate() error {
	if p.Content == "" {
		return fmt.Errorf("TextPayload: content must not be empty")
	}
	return nil
}

// Validate checks that VectorEmbeddingPayload has consistent dimensions and vector length.
func (p *VectorEmbeddingPayload) Validate() error {
	if p.Dimensions <= 0 {
		return fmt.Errorf("VectorEmbeddingPayload: dimensions must be > 0")
	}
	if len(p.Vector) != p.Dimensions {
		return fmt.Errorf("VectorEmbeddingPayload: vector length %d != dimensions %d", len(p.Vector), p.Dimensions)
	}
	return nil
}

// Validate checks that ImagePayload has valid base64 data and an image/ mime type.
func (p *ImagePayload) Validate() error {
	if _, err := base64.StdEncoding.DecodeString(p.DataBase64); err != nil {
		return fmt.Errorf("ImagePayload: invalid base64: %w", err)
	}
	if len(p.MimeType) < 6 || p.MimeType[:6] != "image/" {
		return fmt.Errorf("ImagePayload: mime_type must start with image/")
	}
	return nil
}

// Validate checks that AudioPayload has valid base64 data and an audio/ mime type.
func (p *AudioPayload) Validate() error {
	if _, err := base64.StdEncoding.DecodeString(p.DataBase64); err != nil {
		return fmt.Errorf("AudioPayload: invalid base64: %w", err)
	}
	if len(p.MimeType) < 6 || p.MimeType[:6] != "audio/" {
		return fmt.Errorf("AudioPayload: mime_type must start with audio/")
	}
	return nil
}

// Validate checks that VideoPayload has valid base64 data and a video/ mime type.
func (p *VideoPayload) Validate() error {
	if _, err := base64.StdEncoding.DecodeString(p.DataBase64); err != nil {
		return fmt.Errorf("VideoPayload: invalid base64: %w", err)
	}
	if len(p.MimeType) < 6 || p.MimeType[:6] != "video/" {
		return fmt.Errorf("VideoPayload: mime_type must start with video/")
	}
	return nil
}

// Validate checks that BinaryPayload has valid base64 data.
func (p *BinaryPayload) Validate() error {
	if _, err := base64.StdEncoding.DecodeString(p.DataBase64); err != nil {
		return fmt.Errorf("BinaryPayload: invalid base64: %w", err)
	}
	return nil
}

// Validate checks that TelemetryPayload has required fields and non-empty readings.
func (p *TelemetryPayload) Validate() error {
	if p.SensorID == "" {
		return fmt.Errorf("TelemetryPayload: sensor_id must not be empty")
	}
	if p.Unit == "" {
		return fmt.Errorf("TelemetryPayload: unit must not be empty")
	}
	if len(p.Readings) == 0 {
		return fmt.Errorf("TelemetryPayload: readings must not be empty")
	}
	return nil
}
