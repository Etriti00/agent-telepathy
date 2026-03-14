use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::{connect_async, accept_async, tungstenite::Message};
use serde_json;
use tpcp_core::{AgentIdentity, Intent, TPCPEnvelope, MessageHeader, PROTOCOL_VERSION};
use crate::DLQ;

type HandlerFn = Arc<dyn Fn(TPCPEnvelope) + Send + Sync + 'static>;

/// Async TPCP node backed by tokio and tokio-tungstenite.
pub struct TPCPNode {
    pub identity: AgentIdentity,
    pub memory: Arc<RwLock<tpcp_core::LWWMap>>,
    pub dlq: Arc<DLQ>,
    handlers: Arc<RwLock<HashMap<String, HandlerFn>>>,
}

impl TPCPNode {
    /// Creates a new TPCPNode with the given identity.
    pub fn new(identity: AgentIdentity) -> Self {
        Self {
            identity,
            memory: Arc::new(RwLock::new(tpcp_core::LWWMap::new())),
            dlq: Arc::new(DLQ::new()),
            handlers: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Registers a handler for a specific intent.
    pub async fn register_handler<F>(&self, intent: Intent, handler: F)
    where
        F: Fn(TPCPEnvelope) + Send + Sync + 'static,
    {
        let key = serde_json::to_string(&intent).unwrap_or_default();
        self.handlers.write().await.insert(key, Arc::new(handler));
    }

    /// Connects as a WebSocket client to the given URL.
    pub async fn connect(&self, url: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let (ws_stream, _) = connect_async(url).await?;
        let (_, mut read) = ws_stream.split();
        let handlers = Arc::clone(&self.handlers);
        let dlq = Arc::clone(&self.dlq);
        tokio::spawn(async move {
            while let Some(Ok(msg)) = read.next().await {
                if let Message::Text(text) = msg {
                    if let Ok(env) = serde_json::from_str::<TPCPEnvelope>(&text) {
                        Self::dispatch_env(env, &handlers, &dlq).await;
                    }
                }
            }
        });
        Ok(())
    }

    /// Starts listening on the given address (e.g. "127.0.0.1:9001").
    pub async fn listen(&self, addr: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let listener = tokio::net::TcpListener::bind(addr).await?;
        let handlers = Arc::clone(&self.handlers);
        let dlq = Arc::clone(&self.dlq);
        tokio::spawn(async move {
            while let Ok((stream, _)) = listener.accept().await {
                let ws = match accept_async(stream).await {
                    Ok(ws) => ws,
                    Err(_) => continue,
                };
                let (_, mut read) = ws.split();
                let handlers = Arc::clone(&handlers);
                let dlq = Arc::clone(&dlq);
                tokio::spawn(async move {
                    while let Some(Ok(msg)) = read.next().await {
                        if let Message::Text(text) = msg {
                            if let Ok(env) = serde_json::from_str::<TPCPEnvelope>(&text) {
                                Self::dispatch_env(env, &handlers, &dlq).await;
                            }
                        }
                    }
                });
            }
        });
        Ok(())
    }

    /// Sends a message to the given WebSocket URL.
    pub async fn send_message(
        &self,
        url: &str,
        intent: Intent,
        payload: serde_json::Value,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let (mut ws_stream, _) = connect_async(url).await?;
        let envelope = TPCPEnvelope {
            header: MessageHeader {
                message_id: uuid_v4(),
                sender_id: self.identity.agent_id.clone(),
                receiver_id: url.to_string(),
                intent,
                timestamp_ms: now_ms(),
                protocol_version: PROTOCOL_VERSION.to_string(),
            },
            payload,
            signature: None,
        };
        let text = serde_json::to_string(&envelope)?;
        ws_stream.send(Message::Text(text.into())).await?;
        ws_stream.close(None).await?;
        Ok(())
    }

    async fn dispatch_env(
        env: TPCPEnvelope,
        handlers: &RwLock<HashMap<String, HandlerFn>>,
        dlq: &DLQ,
    ) {
        let key = serde_json::to_string(&env.header.intent).unwrap_or_default();
        let handler = handlers.read().await.get(&key).cloned();
        match handler {
            Some(h) => h(env),
            None => { dlq.enqueue(env); }
        }
    }
}

fn uuid_v4() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let t = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().subsec_nanos();
    format!("{:08x}-{:04x}-4{:03x}-{:04x}-{:012x}",
        t, t >> 16, t & 0xfff, 0x8000 | (t & 0x3fff), t as u64 * 0x1_0000_0000)
}

fn now_ms() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as i64
}
