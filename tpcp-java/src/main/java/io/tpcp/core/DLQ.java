package io.tpcp.core;

import io.tpcp.schema.TPCPEnvelope;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.LinkedBlockingQueue;

/**
 * Dead Letter Queue for unhandled TPCP envelopes.
 * Capacity capped at 100 to prevent unbounded growth.
 */
public class DLQ {
    private final LinkedBlockingQueue<TPCPEnvelope> queue = new LinkedBlockingQueue<>(100);

    /** Adds an envelope to the queue. Returns false if the queue is full. */
    public boolean enqueue(TPCPEnvelope envelope) {
        return queue.offer(envelope);
    }

    /** Removes and returns all envelopes currently in the queue. */
    public List<TPCPEnvelope> drain() {
        List<TPCPEnvelope> result = new ArrayList<>();
        queue.drainTo(result);
        return result;
    }

    /** Returns the number of envelopes in the queue. */
    public int size() {
        return queue.size();
    }
}
