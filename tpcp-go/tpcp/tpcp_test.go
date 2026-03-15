package tpcp

import (
	"encoding/json"
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
