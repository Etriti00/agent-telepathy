use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::{connect_async, accept_async, tungstenite::Message};
use serde_json;
use tpcp_core::{AgentIdentity, Intent, TPCPEnvelope, MessageHeader, PROTOCOL_VERSION};
use tpcp_core::identity::{canonical_json, sign, verify};
use ed25519_dalek::SigningKey;
use uuid::Uuid;
use crate::DLQ;

type HandlerFn = Arc<dyn Fn(TPCPEnvelope) + Send + Sync + 'static>;

/// Async TPCP node backed by tokio and tokio-tungstenite.
pub struct TPCPNode {
    pub identity: AgentIdentity,
    pub memory: Arc<RwLock<tpcp_core::LWWMap>>,
    pub dlq: Arc<DLQ>,
    handlers: Arc<RwLock<HashMap<String, HandlerFn>>>,
    /// Optional Ed25519 signing key. When present, `send_message` attaches a signature.
    signing_key: Option<Arc<SigningKey>>,
    /// Known peer public keys: agent_id → base64-encoded public key.
    /// Inbound messages from registered peers are signature-verified before dispatch.
    peer_keys: Arc<RwLock<HashMap<String, String>>>,
}

impl TPCPNode {
    /// Creates a new TPCPNode with the given identity and no signing key.
    pub fn new(identity: AgentIdentity) -> Self {
        Self {
            identity,
            memory: Arc::new(RwLock::new(tpcp_core::LWWMap::new())),
            dlq: Arc::new(DLQ::new()),
            handlers: Arc::new(RwLock::new(HashMap::new())),
            signing_key: None,
            peer_keys: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Creates a TPCPNode that signs all outbound messages.
    pub fn with_signing_key(identity: AgentIdentity, key: SigningKey) -> Self {
        Self {
            identity,
            memory: Arc::new(RwLock::new(tpcp_core::LWWMap::new())),
            dlq: Arc::new(DLQ::new()),
            handlers: Arc::new(RwLock::new(HashMap::new())),
            signing_key: Some(Arc::new(key)),
            peer_keys: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Registers a peer's public key for inbound signature verification.
    pub async fn register_peer_key(&self, agent_id: &str, public_key_b64: &str) {
        self.peer_keys.write().await.insert(agent_id.to_string(), public_key_b64.to_string());
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
        let peer_keys = Arc::clone(&self.peer_keys);
        tokio::spawn(async move {
            while let Some(Ok(msg)) = read.next().await {
                if let Message::Text(text) = msg {
                    if let Ok(env) = serde_json::from_str::<TPCPEnvelope>(&text) {
                        Self::dispatch_env(env, &handlers, &dlq, &peer_keys).await;
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
        let peer_keys = Arc::clone(&self.peer_keys);
        tokio::spawn(async move {
            while let Ok((stream, _)) = listener.accept().await {
                let ws = match accept_async(stream).await {
                    Ok(ws) => ws,
                    Err(_) => continue,
                };
                let (_, mut read) = ws.split();
                let handlers = Arc::clone(&handlers);
                let dlq = Arc::clone(&dlq);
                let peer_keys = Arc::clone(&peer_keys);
                tokio::spawn(async move {
                    while let Some(Ok(msg)) = read.next().await {
                        if let Message::Text(text) = msg {
                            if let Ok(env) = serde_json::from_str::<TPCPEnvelope>(&text) {
                                Self::dispatch_env(env, &handlers, &dlq, &peer_keys).await;
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
        let signature = self.signing_key.as_ref().map(|key| {
            let canonical = canonical_json(&payload);
            sign(key, &canonical)
        });
        let envelope = TPCPEnvelope {
            header: MessageHeader {
                message_id: uuid_v4(),
                sender_id: self.identity.agent_id.clone(),
                receiver_id: url.to_string(),
                intent,
                timestamp: now_iso8601(),
                ttl: 30,
                protocol_version: PROTOCOL_VERSION.to_string(),
            },
            payload,
            signature,
            ack_info: None,
            chunk_info: None,
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
        peer_keys: &RwLock<HashMap<String, String>>,
    ) {
        // Verify signature if the sender's public key is registered.
        let sender_key = peer_keys.read().await.get(&env.header.sender_id).cloned();
        if let Some(pub_key_b64) = sender_key {
            let canonical = canonical_json(&env.payload);
            let sig_ok = env.signature.as_deref()
                .map(|sig| verify(&pub_key_b64, &canonical, sig))
                .unwrap_or(false);
            if !sig_ok {
                // Invalid or missing signature from a known peer — route to DLQ.
                if !dlq.enqueue(env) {
                    eprintln!("[TPCPNode] DLQ full — dropping invalid-signature envelope");
                }
                return;
            }
        }

        let key = serde_json::to_string(&env.header.intent).unwrap_or_default();
        let handler = handlers.read().await.get(&key).cloned();
        match handler {
            Some(h) => h(env),
            None => {
                if !dlq.enqueue(env) {
                    eprintln!("[TPCPNode] DLQ full — dropping unhandled envelope");
                }
            }
        }
    }
}

fn uuid_v4() -> String {
    Uuid::new_v4().to_string()
}

fn now_iso8601() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let dur = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    let secs = dur.as_secs();
    let millis = dur.subsec_millis();
    let sec = secs % 60;
    let min = (secs / 60) % 60;
    let hour = (secs / 3600) % 24;
    let days = secs / 86400;

    // Gregorian calendar date from days since Unix epoch (1970-01-01).
    // Algorithm: civil date from day count (Howard Hinnant).
    let z = days as i64 + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };

    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z", y, m, d, hour, min, sec, millis)
}
