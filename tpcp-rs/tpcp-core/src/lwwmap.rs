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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_set_get() {
        let mut m = LWWMap::new();
        m.set("key", Value::String("hello".into()), 100);
        assert_eq!(m.get("key"), Some(&Value::String("hello".into())));
        assert_eq!(m.get("missing"), None);
    }

    #[test]
    fn test_last_writer_wins() {
        let mut m = LWWMap::new();
        m.set("x", Value::Number(1.into()), 100);
        // Older timestamp — must NOT overwrite.
        m.set("x", Value::Number(0.into()), 50);
        assert_eq!(m.get("x"), Some(&Value::Number(1.into())), "older write must not overwrite newer value");

        // Equal timestamp — must NOT overwrite either (>= guard in set).
        m.set("x", Value::Number(99.into()), 100);
        assert_eq!(m.get("x"), Some(&Value::Number(1.into())), "equal timestamp must not overwrite");

        // Newer timestamp — must overwrite.
        m.set("x", Value::Number(2.into()), 200);
        assert_eq!(m.get("x"), Some(&Value::Number(2.into())), "newer write must overwrite");
    }

    #[test]
    fn test_merge() {
        let mut a = LWWMap::new();
        a.set("shared", Value::String("from_a".into()), 100);
        a.set("only_a", Value::Bool(true), 50);

        let mut b = LWWMap::new();
        b.set("shared", Value::String("from_b".into()), 200); // newer
        b.set("only_b", Value::Number(42.into()), 75);

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
