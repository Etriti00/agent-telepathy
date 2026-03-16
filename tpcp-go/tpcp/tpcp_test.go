package tpcp

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
)

// TestIntentWireValues verifies that Intent constants serialize to the canonical
// wire-format values matching the Python/TS SDK.
func TestIntentWireValues(t *testing.T) {
	cases := []struct {
		intent   Intent
		expected string
	}{
		{IntentHandshake, "Handshake"},
		{IntentTaskRequest, "Task_Request"},
		{IntentStateSync, "State_Sync"},
		{IntentStateSyncVector, "State_Sync_Vector"},
		{IntentMediaShare, "Media_Share"},
		{IntentCritique, "Critique"},
		{IntentTerminate, "Terminate"},
		{IntentACK, "ACK"},
		{IntentNACK, "NACK"},
		{IntentBroadcast, "Broadcast"},
	}
	for _, tc := range cases {
		b, err := json.Marshal(tc.intent)
		if err != nil {
			t.Fatalf("marshal Intent %q: %v", tc.intent, err)
		}
		got := strings.Trim(string(b), `"`)
		if got != tc.expected {
			t.Errorf("Intent %q: got wire value %q, want %q", tc.intent, got, tc.expected)
		}
	}
}

// TestGenerateIdentity verifies that GenerateIdentity returns a valid identity with
// the correct JSON field names.
func TestGenerateIdentity(t *testing.T) {
	identity, priv, err := GenerateIdentity("Go-Test")
	if err != nil {
		t.Fatalf("GenerateIdentity: %v", err)
	}
	if priv == nil {
		t.Fatal("expected non-nil private key")
	}
	if identity.AgentID == "" {
		t.Error("AgentID is empty")
	}
	if identity.Framework != "Go-Test" {
		t.Errorf("Framework: got %q, want %q", identity.Framework, "Go-Test")
	}
	if identity.PublicKey == "" {
		t.Error("PublicKey is empty")
	}
	if len(identity.Modality) == 0 {
		t.Error("Modality should default to [\"text\"]")
	}

	// Verify that AgentIdentity marshals with the correct JSON field names.
	b, err := json.Marshal(identity)
	if err != nil {
		t.Fatalf("marshal AgentIdentity: %v", err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatalf("unmarshal AgentIdentity: %v", err)
	}
	if _, ok := m["public_key"]; !ok {
		t.Error("JSON field \"public_key\" missing — got wrong field name (check JSON tags)")
	}
	if _, ok := m["public_key_b64"]; ok {
		t.Error("JSON field \"public_key_b64\" must not appear — should be \"public_key\"")
	}
	if _, ok := m["framework"]; !ok {
		t.Error("JSON field \"framework\" missing — got wrong field name")
	}
	if _, ok := m["agent_type"]; ok {
		t.Error("JSON field \"agent_type\" must not appear — should be \"framework\"")
	}
}

// TestSignVerify verifies that Sign produces a standard base64 signature that Verify accepts.
func TestSignVerify(t *testing.T) {
	identity, priv, err := GenerateIdentity("Go-Test")
	if err != nil {
		t.Fatalf("GenerateIdentity: %v", err)
	}
	payload := []byte(`{"content":"hello","payload_type":"text"}`)
	sig := Sign(priv, payload)

	// Signature must not contain URL-safe characters (- or _) — only standard base64 (+, /, =)
	if strings.ContainsAny(sig, "-_") {
		t.Errorf("signature %q looks URL-safe; must use standard base64", sig)
	}

	if !Verify(identity.PublicKey, payload, sig) {
		t.Error("Verify returned false for a valid signature")
	}

	// Tampered payload must not verify.
	if Verify(identity.PublicKey, []byte(`{"content":"tampered","payload_type":"text"}`), sig) {
		t.Error("Verify returned true for tampered payload")
	}
}

// TestCanonicalJSON verifies deterministic key-sorted output.
func TestCanonicalJSON(t *testing.T) {
	input := map[string]interface{}{
		"z_key":   "last",
		"a_key":   "first",
		"m_key":   42,
		"nested":  map[string]interface{}{"b": 2, "a": 1},
	}
	got, err := CanonicalJSON(input)
	if err != nil {
		t.Fatalf("CanonicalJSON: %v", err)
	}
	want := `{"a_key":"first","m_key":42,"nested":{"a":1,"b":2},"z_key":"last"}`
	if string(got) != want {
		t.Errorf("CanonicalJSON:\n got  %s\n want %s", got, want)
	}
}

// TestMessageHeaderJSONFields verifies MessageHeader uses the canonical field names.
func TestMessageHeaderJSONFields(t *testing.T) {
	hdr := MessageHeader{
		MessageID:       "msg-1",
		Timestamp:       "2026-03-14T10:00:00Z",
		SenderID:        "sender",
		ReceiverID:      "receiver",
		Intent:          IntentTaskRequest,
		TTL:             30,
		ProtocolVersion: PROTOCOL_VERSION,
	}
	b, err := json.Marshal(hdr)
	if err != nil {
		t.Fatalf("marshal MessageHeader: %v", err)
	}
	var m map[string]interface{}
	json.Unmarshal(b, &m)

	for _, required := range []string{"timestamp", "ttl", "protocol_version"} {
		if _, ok := m[required]; !ok {
			t.Errorf("MessageHeader JSON missing field %q", required)
		}
	}
	if _, ok := m["timestamp_ms"]; ok {
		t.Error("MessageHeader JSON must not have \"timestamp_ms\" — should be \"timestamp\"")
	}
}

// TestTextPayloadValidateRejectsEmpty verifies that an empty TextPayload fails validation.
func TestTextPayloadValidateRejectsEmpty(t *testing.T) {
	p := TextPayload{PayloadType: "text", Content: ""}
	if err := p.Validate(); err == nil {
		t.Fatal("expected error for empty content")
	}
}

// TestTextPayloadValidateAcceptsNonEmpty verifies that a non-empty TextPayload passes validation.
func TestTextPayloadValidateAcceptsNonEmpty(t *testing.T) {
	p := TextPayload{PayloadType: "text", Content: "hello"}
	if err := p.Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestVectorEmbeddingPayloadValidateDimensionMismatch verifies that a vector with wrong length fails.
func TestVectorEmbeddingPayloadValidateDimensionMismatch(t *testing.T) {
	p := VectorEmbeddingPayload{PayloadType: "vector_embedding", ModelID: "test", Dimensions: 3, Vector: []float64{1, 2}}
	if err := p.Validate(); err == nil {
		t.Fatal("expected dimension mismatch error")
	}
}

// TestImagePayloadValidateRejectsInvalidBase64 verifies that invalid base64 fails validation.
func TestImagePayloadValidateRejectsInvalidBase64(t *testing.T) {
	p := ImagePayload{PayloadType: "image", DataBase64: "not-base64!!!", MimeType: "image/png"}
	if err := p.Validate(); err == nil {
		t.Fatal("expected base64 validation error")
	}
}

// TestTelemetryPayloadValidateRejectsEmptyReadings verifies that empty readings slice fails.
func TestTelemetryPayloadValidateRejectsEmptyReadings(t *testing.T) {
	p := TelemetryPayload{PayloadType: "telemetry", SensorID: "s1", Unit: "rpm", Readings: []TelemetryReading{}, SourceProtocol: "opcua"}
	if err := p.Validate(); err == nil {
		t.Fatal("expected empty readings error")
	}
}

// TestSendMessageRejectsInvalidPayload verifies that SendMessage returns an error for an invalid payload
// before attempting peer lookup.
func TestSendMessageRejectsInvalidPayload(t *testing.T) {
	identity := &AgentIdentity{AgentID: "test-node", Framework: "test-fw"}
	node := NewTPCPNode(identity, nil)
	payload := &TextPayload{PayloadType: "text", Content: ""}
	err := node.SendMessage("peer-1", IntentTaskRequest, payload)
	if err == nil {
		t.Fatal("expected SendMessage to reject invalid payload")
	}
}

// TestDLQEnqueueDrain verifies that an enqueued envelope is returned by Drain.
func TestDLQEnqueueDrain(t *testing.T) {
	q := NewDLQ()
	env := &TPCPEnvelope{
		Header: MessageHeader{MessageID: "dlq-test-1"},
	}
	if !q.Enqueue(env) {
		t.Fatal("Enqueue returned false; expected true")
	}
	drained := q.Drain()
	if len(drained) != 1 {
		t.Fatalf("Drain: got %d envelopes, want 1", len(drained))
	}
	if drained[0].Header.MessageID != "dlq-test-1" {
		t.Errorf("Drain: got message ID %q, want %q", drained[0].Header.MessageID, "dlq-test-1")
	}
}

// TestDLQOverflow verifies that enqueueing more items than capacity (100) silently
// drops the excess and Drain returns at most 100 envelopes.
func TestDLQOverflow(t *testing.T) {
	q := NewDLQ()
	const overCapacity = 150
	for i := 0; i < overCapacity; i++ {
		q.Enqueue(&TPCPEnvelope{Header: MessageHeader{MessageID: fmt.Sprintf("msg-%d", i)}})
	}
	drained := q.Drain()
	if len(drained) > 100 {
		t.Errorf("Drain returned %d envelopes; DLQ capacity is 100 so must not exceed 100", len(drained))
	}
}

// TestLWWMapSetGet verifies that a value written with Set can be read back with Get.
func TestLWWMapSetGet(t *testing.T) {
	m := NewLWWMap()
	m.Set("key1", "hello", 1000)
	val, ok := m.Get("key1")
	if !ok {
		t.Fatal("Get returned false; expected key to be present")
	}
	if val != "hello" {
		t.Errorf("Get: got %v, want %q", val, "hello")
	}
}

// TestLWWMapLastWriterWins verifies that when the same key is written twice,
// the higher-timestamp value wins.
func TestLWWMapLastWriterWins(t *testing.T) {
	m := NewLWWMap()
	m.Set("counter", "first", 100)
	m.Set("counter", "second", 200)
	val, ok := m.Get("counter")
	if !ok {
		t.Fatal("Get returned false after two sets")
	}
	if val != "second" {
		t.Errorf("LWW: got %v, want %q — higher timestamp should win", val, "second")
	}

	// An older timestamp must not overwrite the current value.
	m.Set("counter", "stale", 50)
	val, _ = m.Get("counter")
	if val != "second" {
		t.Errorf("LWW: older write overwrote newer value; got %v, want %q", val, "second")
	}
}

// TestTPCPEnvelopeAckChunkJSON verifies that AckInfo and ChunkInfo survive
// a JSON marshal/unmarshal round-trip on TPCPEnvelope.
func TestTPCPEnvelopeAckChunkJSON(t *testing.T) {
	env := TPCPEnvelope{
		Header: MessageHeader{
			MessageID:       "msg-ack-1",
			Timestamp:       "2026-03-14T12:00:00Z",
			SenderID:        "agent-a",
			ReceiverID:      "agent-b",
			Intent:          IntentACK,
			TTL:             10,
			ProtocolVersion: PROTOCOL_VERSION,
		},
		Payload: json.RawMessage(`{"payload_type":"text","content":"ok"}`),
		AckInfo: &AckInfo{
			AckedMessageID: "msg-original-42",
		},
		ChunkInfo: &ChunkInfo{
			ChunkIndex:  2,
			TotalChunks: 5,
			TransferID:  "xfer-abc-123",
		},
	}

	b, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal TPCPEnvelope: %v", err)
	}

	var decoded TPCPEnvelope
	if err := json.Unmarshal(b, &decoded); err != nil {
		t.Fatalf("unmarshal TPCPEnvelope: %v", err)
	}

	// Verify AckInfo round-trip
	if decoded.AckInfo == nil {
		t.Fatal("AckInfo is nil after round-trip")
	}
	if decoded.AckInfo.AckedMessageID != "msg-original-42" {
		t.Errorf("AckInfo.AckedMessageID: got %q, want %q", decoded.AckInfo.AckedMessageID, "msg-original-42")
	}

	// Verify ChunkInfo round-trip
	if decoded.ChunkInfo == nil {
		t.Fatal("ChunkInfo is nil after round-trip")
	}
	if decoded.ChunkInfo.ChunkIndex != 2 {
		t.Errorf("ChunkInfo.ChunkIndex: got %d, want %d", decoded.ChunkInfo.ChunkIndex, 2)
	}
	if decoded.ChunkInfo.TotalChunks != 5 {
		t.Errorf("ChunkInfo.TotalChunks: got %d, want %d", decoded.ChunkInfo.TotalChunks, 5)
	}
	if decoded.ChunkInfo.TransferID != "xfer-abc-123" {
		t.Errorf("ChunkInfo.TransferID: got %q, want %q", decoded.ChunkInfo.TransferID, "xfer-abc-123")
	}
}
