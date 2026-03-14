package tpcp

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"sort"
)

// GenerateIdentity creates a new Ed25519 keypair and AgentIdentity.
// framework should describe the agent's framework (e.g. "Go", "CrewAI").
func GenerateIdentity(framework string) (*AgentIdentity, ed25519.PrivateKey, error) {
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, nil, fmt.Errorf("generate ed25519 key: %w", err)
	}
	agentID := randomUUID()
	pubB64 := base64.StdEncoding.EncodeToString(pub)
	identity := &AgentIdentity{
		AgentID:      agentID,
		Framework:    framework,
		Capabilities: []string{},
		PublicKey:    pubB64,
		Modality:     []string{"text"},
	}
	return identity, priv, nil
}

// Sign signs payload bytes with the private key and returns a standard base64-encoded signature.
// Uses standard (not URL-safe) base64 to match Python's base64.b64encode().
func Sign(privKey ed25519.PrivateKey, payload []byte) string {
	sig := ed25519.Sign(privKey, payload)
	return base64.StdEncoding.EncodeToString(sig)
}

// Verify checks a standard base64-encoded signature against the payload.
func Verify(pubKeyB64 string, payload []byte, sigB64 string) bool {
	pubBytes, err := base64.StdEncoding.DecodeString(pubKeyB64)
	if err != nil {
		return false
	}
	sigBytes, err := base64.StdEncoding.DecodeString(sigB64)
	if err != nil {
		return false
	}
	pub := ed25519.PublicKey(pubBytes)
	return ed25519.Verify(pub, payload, sigBytes)
}

// CanonicalJSON serializes v to canonical JSON with sorted keys and compact separators,
// matching Python's json.dumps(sort_keys=True, separators=(',',':')).
func CanonicalJSON(v interface{}) ([]byte, error) {
	// Marshal to generic map first so we can sort keys
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var generic interface{}
	if err := json.Unmarshal(raw, &generic); err != nil {
		return nil, err
	}
	return marshalSorted(generic)
}

func marshalSorted(v interface{}) ([]byte, error) {
	switch val := v.(type) {
	case map[string]interface{}:
		keys := make([]string, 0, len(val))
		for k := range val {
			keys = append(keys, k)
		}
		sort.Strings(keys)

		result := []byte("{")
		for i, k := range keys {
			keyBytes, _ := json.Marshal(k)
			valBytes, err := marshalSorted(val[k])
			if err != nil {
				return nil, err
			}
			result = append(result, keyBytes...)
			result = append(result, ':')
			result = append(result, valBytes...)
			if i < len(keys)-1 {
				result = append(result, ',')
			}
		}
		result = append(result, '}')
		return result, nil

	case []interface{}:
		result := []byte("[")
		for i, item := range val {
			itemBytes, err := marshalSorted(item)
			if err != nil {
				return nil, err
			}
			result = append(result, itemBytes...)
			if i < len(val)-1 {
				result = append(result, ',')
			}
		}
		result = append(result, ']')
		return result, nil

	default:
		return json.Marshal(v)
	}
}
