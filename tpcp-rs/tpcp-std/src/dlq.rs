use tokio::sync::mpsc;
use tpcp_core::TPCPEnvelope;

/// Dead Letter Queue for unhandled TPCP envelopes.
pub struct DLQ {
    tx: mpsc::Sender<TPCPEnvelope>,
    rx: tokio::sync::Mutex<mpsc::Receiver<TPCPEnvelope>>,
}

impl DLQ {
    /// Creates a DLQ with capacity 100.
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel(100);
        Self { tx, rx: tokio::sync::Mutex::new(rx) }
    }

    /// Enqueues an envelope. Returns false if the queue is full.
    pub fn enqueue(&self, env: TPCPEnvelope) -> bool {
        self.tx.try_send(env).is_ok()
    }

    /// Drains all queued envelopes.
    pub async fn drain(&self) -> Vec<TPCPEnvelope> {
        let mut rx = self.rx.lock().await;
        let mut out = Vec::new();
        while let Ok(env) = rx.try_recv() {
            out.push(env);
        }
        out
    }
}

impl Default for DLQ {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tpcp_core::{Intent, MessageHeader, PROTOCOL_VERSION, TPCPEnvelope};

    fn make_envelope(id: &str) -> TPCPEnvelope {
        TPCPEnvelope {
            header: MessageHeader {
                message_id: id.to_string(),
                timestamp: "2026-01-01T00:00:00Z".to_string(),
                sender_id: "sender".to_string(),
                receiver_id: "receiver".to_string(),
                intent: Intent::TaskRequest,
                ttl: 30,
                protocol_version: PROTOCOL_VERSION.to_string(),
            },
            payload: serde_json::json!({"payload_type": "text", "content": "test"}),
            signature: None,
            ack_info: None,
            chunk_info: None,
        }
    }

    #[tokio::test]
    async fn test_enqueue_drain() {
        let dlq = DLQ::new();

        let env1 = make_envelope("msg-1");
        let env2 = make_envelope("msg-2");

        assert!(dlq.enqueue(env1), "first enqueue must succeed");
        assert!(dlq.enqueue(env2), "second enqueue must succeed");

        let drained = dlq.drain().await;
        assert_eq!(drained.len(), 2, "drain must return all enqueued envelopes");
        assert_eq!(drained[0].header.message_id, "msg-1");
        assert_eq!(drained[1].header.message_id, "msg-2");

        // After draining, queue is empty.
        let drained_again = dlq.drain().await;
        assert!(drained_again.is_empty(), "second drain must return nothing");
    }

    #[tokio::test]
    async fn test_drain_empty() {
        let dlq = DLQ::new();
        let drained = dlq.drain().await;
        assert!(drained.is_empty(), "draining an empty DLQ must return an empty vec");
    }
}
