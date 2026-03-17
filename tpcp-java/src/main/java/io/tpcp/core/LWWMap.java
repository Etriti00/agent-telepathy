package io.tpcp.core;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * Last-Write-Wins CRDT map, thread-safe via ConcurrentHashMap.
 *
 * <p>Tie-breaking: timestamp > writer_id (lexicographic), matching Python's LWWMap.
 */
public class LWWMap {
    private final ConcurrentHashMap<String, LWWEntry> map = new ConcurrentHashMap<>();

    /** Writes a value with the given timestamp and writer ID. No-op if a newer value exists. */
    public void set(String key, Object value, long timestampMs, String writerId) {
        map.merge(key, new LWWEntry(value, timestampMs, writerId), (existing, incoming) -> {
            if (incoming.timestampMs > existing.timestampMs) return incoming;
            if (incoming.timestampMs == existing.timestampMs
                    && incoming.writerId.compareTo(existing.writerId) > 0) return incoming;
            return existing;
        });
    }

    /** Returns the value for a key, or empty if absent. */
    public Optional<Object> get(String key) {
        LWWEntry entry = map.get(key);
        return entry == null ? Optional.empty() : Optional.ofNullable(entry.value);
    }

    /** Merges all entries from {@code other} using LWW semantics. */
    public void merge(LWWMap other) {
        other.map.forEach((k, v) -> set(k, v.value, v.timestampMs, v.writerId));
    }

    /** Returns a plain map snapshot of current values. */
    public Map<String, Object> toMap() {
        return map.entrySet().stream()
                .collect(Collectors.toMap(Map.Entry::getKey, e -> e.getValue().value));
    }

    private record LWWEntry(Object value, long timestampMs, String writerId) {}
}
