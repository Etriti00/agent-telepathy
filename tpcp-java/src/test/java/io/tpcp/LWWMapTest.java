package io.tpcp;

import io.tpcp.core.LWWMap;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class LWWMapTest {

    @Test
    void lastWriteWins() {
        LWWMap map = new LWWMap();
        map.set("key", "first", 100L, "agent-a");
        map.set("key", "second", 200L, "agent-a");
        assertEquals("second", map.get("key").orElseThrow());
    }

    @Test
    void olderWriteDoesNotOverwrite() {
        LWWMap map = new LWWMap();
        map.set("key", "newer", 200L, "agent-a");
        map.set("key", "older", 100L, "agent-b");
        assertEquals("newer", map.get("key").orElseThrow());
    }

    @Test
    void mergeKeepsHigherTimestamp() {
        LWWMap a = new LWWMap();
        LWWMap b = new LWWMap();
        a.set("x", "from-a", 100L, "agent-a");
        b.set("x", "from-b", 200L, "agent-b");
        a.merge(b);
        assertEquals("from-b", a.get("x").orElseThrow());
    }

    @Test
    void mergePreservesLocalIfNewer() {
        LWWMap a = new LWWMap();
        LWWMap b = new LWWMap();
        a.set("x", "from-a", 300L, "agent-a");
        b.set("x", "from-b", 200L, "agent-b");
        a.merge(b);
        assertEquals("from-a", a.get("x").orElseThrow());
    }

    @Test
    void writerIdTieBreaking() {
        LWWMap map = new LWWMap();
        map.set("key", "agent-a-val", 100L, "agent-a");
        map.set("key", "agent-z-val", 100L, "agent-z");
        assertEquals("agent-z-val", map.get("key").orElseThrow(),
                "equal timestamp must be broken by higher writer_id");
    }
}
