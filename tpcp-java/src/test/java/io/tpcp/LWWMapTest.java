package io.tpcp;

import io.tpcp.core.LWWMap;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class LWWMapTest {

    @Test
    void lastWriteWins() {
        LWWMap map = new LWWMap();
        map.set("key", "first", 100L);
        map.set("key", "second", 200L);
        assertEquals("second", map.get("key").orElseThrow());
    }

    @Test
    void olderWriteDoesNotOverwrite() {
        LWWMap map = new LWWMap();
        map.set("key", "newer", 200L);
        map.set("key", "older", 100L);
        assertEquals("newer", map.get("key").orElseThrow());
    }

    @Test
    void mergeKeepsHigherTimestamp() {
        LWWMap a = new LWWMap();
        LWWMap b = new LWWMap();
        a.set("x", "from-a", 100L);
        b.set("x", "from-b", 200L);
        a.merge(b);
        assertEquals("from-b", a.get("x").orElseThrow());
    }

    @Test
    void mergePreservesLocalIfNewer() {
        LWWMap a = new LWWMap();
        LWWMap b = new LWWMap();
        a.set("x", "from-a", 300L);
        b.set("x", "from-b", 200L);
        a.merge(b);
        assertEquals("from-a", a.get("x").orElseThrow());
    }
}
