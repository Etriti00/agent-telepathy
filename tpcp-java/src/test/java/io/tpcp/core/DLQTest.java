package io.tpcp.core;

import io.tpcp.schema.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.util.List;

class DLQTest {

    private TPCPEnvelope makeEnvelope(String messageId) {
        MessageHeader header = new MessageHeader(
            messageId, "2026-03-16T00:00:00Z", "sender-1", "receiver-1",
            Intent.TASK_REQUEST, 30, "0.4.0"
        );
        return new TPCPEnvelope(header, null);
    }

    @Test
    void testEnqueueAndDrain() {
        DLQ dlq = new DLQ();
        TPCPEnvelope envelope = makeEnvelope("msg-dlq-001");

        boolean accepted = dlq.enqueue(envelope);
        assertTrue(accepted, "enqueue should return true when queue has capacity");
        assertEquals(1, dlq.size());

        List<TPCPEnvelope> drained = dlq.drain();
        assertNotNull(drained);
        assertEquals(1, drained.size());
        assertEquals("msg-dlq-001", drained.get(0).header.messageId);
        assertEquals(0, dlq.size(), "queue must be empty after drain");
    }

    @Test
    void testDrainEmptyReturnsEmptyList() {
        DLQ dlq = new DLQ();
        List<TPCPEnvelope> drained = dlq.drain();
        assertNotNull(drained, "drain on empty DLQ must return an empty list, not null");
        assertTrue(drained.isEmpty());
    }

    @Test
    void testCapacityEnforced() {
        DLQ dlq = new DLQ(2);
        assertTrue(dlq.enqueue(makeEnvelope("msg-1")));
        assertTrue(dlq.enqueue(makeEnvelope("msg-2")));
        assertFalse(dlq.enqueue(makeEnvelope("msg-3")),
            "enqueue must return false when DLQ is at capacity");
        assertEquals(2, dlq.size());
    }

    @Test
    void testDrainMultipleMessages() {
        DLQ dlq = new DLQ();
        dlq.enqueue(makeEnvelope("msg-a"));
        dlq.enqueue(makeEnvelope("msg-b"));
        dlq.enqueue(makeEnvelope("msg-c"));

        List<TPCPEnvelope> drained = dlq.drain();
        assertEquals(3, drained.size());
        assertEquals("msg-a", drained.get(0).header.messageId);
        assertEquals("msg-b", drained.get(1).header.messageId);
        assertEquals("msg-c", drained.get(2).header.messageId);
        assertEquals(0, dlq.size());
    }
}
