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
