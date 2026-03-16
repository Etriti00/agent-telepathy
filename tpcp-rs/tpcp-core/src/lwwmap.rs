use alloc::collections::BTreeMap;
use alloc::string::String;
use serde_json::Value;

/// Single LWW entry with value, timestamp, and writer identity.
#[derive(Debug, Clone)]
pub struct LWWEntry {
    pub value: Value,
    pub timestamp_ms: i64,
    pub writer_id: String,
}

/// Last-Write-Wins CRDT map using BTreeMap (no_std compatible).
/// Tie-breaking: timestamp > writer_id (lexicographic), matching Python's LWWMap.
#[derive(Debug, Clone, Default)]
pub struct LWWMap {
    map: BTreeMap<String, LWWEntry>,
}

impl LWWMap {
    /// Creates an empty LWWMap.
    pub fn new() -> Self {
        Self { map: BTreeMap::new() }
    }

    /// Writes a value with the given timestamp and writer ID.
    /// No-op if a newer value exists. Equal timestamps are broken by writer_id (higher wins).
    pub fn set(&mut self, key: &str, value: Value, timestamp_ms: i64, writer_id: &str) {
        if let Some(existing) = self.map.get(key) {
            if existing.timestamp_ms > timestamp_ms {
                return;
            }
            if existing.timestamp_ms == timestamp_ms && existing.writer_id.as_str() >= writer_id {
                return;
            }
        }
        self.map.insert(key.into(), LWWEntry { value, timestamp_ms, writer_id: writer_id.into() });
    }

    /// Returns the value for a key, or None if absent.
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.map.get(key).map(|e| &e.value)
    }

    /// Merges another LWWMap into this one using LWW semantics.
    pub fn merge(&mut self, other: &LWWMap) {
        for (k, entry) in &other.map {
            self.set(k, entry.value.clone(), entry.timestamp_ms, &entry.writer_id);
        }
    }

    /// Returns a plain BTreeMap snapshot of all current values.
    pub fn to_map(&self) -> BTreeMap<String, Value> {
        self.map.iter().map(|(k, v)| (k.clone(), v.value.clone())).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_set_get() {
        let mut m = LWWMap::new();
        m.set("key", Value::String("hello".into()), 100, "agent-a");
        assert_eq!(m.get("key"), Some(&Value::String("hello".into())));
        assert_eq!(m.get("missing"), None);
    }

    #[test]
    fn test_last_writer_wins() {
        let mut m = LWWMap::new();
        m.set("x", Value::Number(1.into()), 100, "agent-a");
        // Older timestamp — must NOT overwrite.
        m.set("x", Value::Number(0.into()), 50, "agent-b");
        assert_eq!(m.get("x"), Some(&Value::Number(1.into())), "older write must not overwrite newer value");

        // Equal timestamp, same writer — must NOT overwrite (>= guard).
        m.set("x", Value::Number(99.into()), 100, "agent-a");
        assert_eq!(m.get("x"), Some(&Value::Number(1.into())), "equal timestamp+writer must not overwrite");

        // Equal timestamp, higher writer_id — MUST overwrite (tie-break).
        m.set("x", Value::Number(77.into()), 100, "agent-z");
        assert_eq!(m.get("x"), Some(&Value::Number(77.into())), "equal timestamp with higher writer_id must overwrite");

        // Newer timestamp — must overwrite.
        m.set("x", Value::Number(2.into()), 200, "agent-a");
        assert_eq!(m.get("x"), Some(&Value::Number(2.into())), "newer write must overwrite");
    }

    #[test]
    fn test_merge() {
        let mut a = LWWMap::new();
        a.set("shared", Value::String("from_a".into()), 100, "agent-a");
        a.set("only_a", Value::Bool(true), 50, "agent-a");

        let mut b = LWWMap::new();
        b.set("shared", Value::String("from_b".into()), 200, "agent-b"); // newer
        b.set("only_b", Value::Number(42.into()), 75, "agent-b");

        a.merge(&b);

        // "shared" should now hold b's newer value.
        assert_eq!(
            a.get("shared"),
            Some(&Value::String("from_b".into())),
            "merge must pick the newer value for conflicting keys"
        );
        // Keys unique to each map must both be present.
        assert_eq!(a.get("only_a"), Some(&Value::Bool(true)));
        assert_eq!(a.get("only_b"), Some(&Value::Number(42.into())));
    }
}
