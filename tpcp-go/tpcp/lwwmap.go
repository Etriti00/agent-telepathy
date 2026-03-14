package tpcp

import "sync"

// lwwEntry holds a value and its write timestamp.
type lwwEntry struct {
	Value       interface{}
	TimestampMs int64
}

// LWWMap is a Last-Write-Wins CRDT map, safe for concurrent use.
type LWWMap struct {
	mu      sync.RWMutex
	entries map[string]lwwEntry
}

// NewLWWMap creates an empty LWWMap.
func NewLWWMap() *LWWMap {
	return &LWWMap{entries: make(map[string]lwwEntry)}
}

// Set writes a value with the given timestamp. No-op if a newer value exists.
func (m *LWWMap) Set(key string, value interface{}, timestampMs int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if existing, ok := m.entries[key]; ok && existing.TimestampMs >= timestampMs {
		return
	}
	m.entries[key] = lwwEntry{Value: value, TimestampMs: timestampMs}
}

// Get returns the value for key, or (nil, false) if not present.
func (m *LWWMap) Get(key string) (interface{}, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	e, ok := m.entries[key]
	if !ok {
		return nil, false
	}
	return e.Value, true
}

// Merge applies all entries from other, keeping higher-timestamp values.
// The snapshot approach avoids deadlock when m == other or when both mutexes
// would otherwise be held simultaneously across the Set call.
func (m *LWWMap) Merge(other *LWWMap) {
	other.mu.RLock()
	snapshot := make([]lwwEntry, 0, len(other.entries))
	keys := make([]string, 0, len(other.entries))
	for k, v := range other.entries {
		keys = append(keys, k)
		snapshot = append(snapshot, v)
	}
	other.mu.RUnlock()

	for i, k := range keys {
		m.Set(k, snapshot[i].Value, snapshot[i].TimestampMs)
	}
}

// ToMap returns a snapshot copy as a plain map.
func (m *LWWMap) ToMap() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make(map[string]interface{}, len(m.entries))
	for k, v := range m.entries {
		out[k] = v.Value
	}
	return out
}
