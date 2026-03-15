use alloc::collections::BTreeMap;
use alloc::string::String;
use serde_json::Value;

/// Single LWW entry with value and timestamp.
#[derive(Debug, Clone)]
pub struct LWWEntry {
    pub value: Value,
    pub timestamp_ms: i64,
}

/// Last-Write-Wins CRDT map using BTreeMap (no_std compatible).
#[derive(Debug, Clone, Default)]
pub struct LWWMap {
    map: BTreeMap<String, LWWEntry>,
}

impl LWWMap {
    /// Creates an empty LWWMap.
    pub fn new() -> Self {
        Self { map: BTreeMap::new() }
    }

    /// Writes a value with the given timestamp. No-op if a newer value exists.
    pub fn set(&mut self, key: &str, value: Value, timestamp_ms: i64) {
        if let Some(existing) = self.map.get(key) {
            if existing.timestamp_ms >= timestamp_ms {
                return;
            }
        }
        self.map.insert(key.into(), LWWEntry { value, timestamp_ms });
    }

    /// Returns the value for a key, or None if absent.
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.map.get(key).map(|e| &e.value)
    }

    /// Merges another LWWMap into this one using LWW semantics.
    pub fn merge(&mut self, other: &LWWMap) {
        for (k, entry) in &other.map {
            self.set(k, entry.value.clone(), entry.timestamp_ms);
        }
    }

    /// Returns a plain BTreeMap snapshot of all current values.
    pub fn to_map(&self) -> BTreeMap<String, Value> {
        self.map.iter().map(|(k, v)| (k.clone(), v.value.clone())).collect()
    }
}
