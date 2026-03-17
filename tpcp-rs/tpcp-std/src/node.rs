use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
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
    handlers: Arc<RwLock<HashMap<Intent, HandlerFn>>>,
    /// Optional Ed25519 signing key. When present, `send_message` attaches a signature.
    signing_key: Option<Arc<SigningKey>>,
    /// Known peer public keys: agent_id → base64-encoded public key.
    /// Inbound messages from registered peers are signature-verified before dispatch.
    peer_keys: Arc<RwLock<HashMap<String, String>>>,
    /// Replay-protection window: message_id → unix timestamp (seconds) of first receipt.
    seen_messages: Arc<RwLock<HashMap<String, i64>>>,
    /// Maximum number of concurrent inbound WebSocket connections.
    max_connections: usize,
    /// Current count of active inbound connections.
    active_connections: Arc<AtomicUsize>,
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
            seen_messages: Arc::new(RwLock::new(HashMap::new())),
            max_connections: 100,
            active_connections: Arc::new(AtomicUsize::new(0)),
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
            seen_messages: Arc::new(RwLock::new(HashMap::new())),
            max_connections: 100,
            active_connections: Arc::new(AtomicUsize::new(0)),
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
        self.handlers.write().await.insert(intent, Arc::new(handler));
    }

    /// Connects as a WebSocket client to the given URL.
    pub async fn connect(&self, url: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let (ws_stream, _) = connect_async(url).await?;
        let (_, mut read) = ws_stream.split();
        let handlers = Arc::clone(&self.handlers);
        let dlq = Arc::clone(&self.dlq);
        let peer_keys = Arc::clone(&self.peer_keys);
        let seen_messages = Arc::clone(&self.seen_messages);
        tokio::spawn(async move {
            while let Some(Ok(msg)) = read.next().await {
                if let Message::Text(text) = msg {
                    if let Ok(env) = serde_json::from_str::<TPCPEnvelope>(&text) {
                        Self::dispatch_env(env, &handlers, &dlq, &peer_keys, &seen_messages).await;
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
        let seen_messages = Arc::clone(&self.seen_messages);
        let max_connections = self.max_connections;
        let active_connections = Arc::clone(&self.active_connections);
        tokio::spawn(async move {
            while let Ok((stream, _)) = listener.accept().await {
                // Enforce connection limit before upgrading to WebSocket.
                if active_connections.load(Ordering::Acquire) >= max_connections {
                    eprintln!("[TPCPNode] max_connections ({}) reached — rejecting new connection", max_connections);
                    // Drop the raw TcpStream; this closes the TCP connection.
                    drop(stream);
                    continue;
                }

                let ws = match accept_async(stream).await {
                    Ok(ws) => ws,
                    Err(_) => continue,
                };
                let (_, mut read) = ws.split();
                let handlers = Arc::clone(&handlers);
                let dlq = Arc::clone(&dlq);
                let peer_keys = Arc::clone(&peer_keys);
                let seen_messages = Arc::clone(&seen_messages);
                let active_connections_inner = Arc::clone(&active_connections);
                active_connections_inner.fetch_add(1, Ordering::AcqRel);
                tokio::spawn(async move {
                    while let Some(Ok(msg)) = read.next().await {
                        if let Message::Text(text) = msg {
                            if let Ok(env) = serde_json::from_str::<TPCPEnvelope>(&text) {
                                Self::dispatch_env(env, &handlers, &dlq, &peer_keys, &seen_messages).await;
                            }
                        }
                    }
                    active_connections_inner.fetch_sub(1, Ordering::AcqRel);
                });
            }
        });
        Ok(())
    }

    /// Sends a message to the given WebSocket URL.
    /// `receiver_id` is the target agent's agent_id (not the URL).
    pub async fn send_message(
        &self,
        url: &str,
        receiver_id: &str,
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
                receiver_id: receiver_id.to_string(),
                intent,
                timestamp: chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
                ttl: 30,
                protocol_version: PROTOCOL_VERSION.to_string(),
            },
            payload,
            signature,
            ack_info: None,
            chunk_info: None,
        };
        let text = serde_json::to_string(&envelope)?;
        ws_stream.send(Message::Text(text)).await?;
        ws_stream.close(None).await?;
        Ok(())
    }

    async fn dispatch_env(
        env: TPCPEnvelope,
        handlers: &RwLock<HashMap<Intent, HandlerFn>>,
        dlq: &DLQ,
        peer_keys: &RwLock<HashMap<String, String>>,
        seen_messages: &RwLock<HashMap<String, i64>>,
    ) {
        // --- Signature enforcement ---
        // If the envelope carries a non-empty signature, the sender's public key
        // MUST be registered. Fail closed: unknown-peer signed messages go to DLQ.
        let has_signature = env.signature.as_deref().map(|s| !s.is_empty()).unwrap_or(false);
        let sender_key = peer_keys.read().await.get(&env.header.sender_id).cloned();

        if has_signature && sender_key.is_none() {
            eprintln!(
                "[TPCPNode] signed envelope from unknown peer '{}' (message_id: {}) — routing to DLQ",
                env.header.sender_id, env.header.message_id
            );
            if !dlq.enqueue(env) {
                eprintln!("[TPCPNode] DLQ full — dropping signed-unknown-peer envelope");
            }
            return;
        }

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

        // --- Replay protection ---
        let now = chrono::Utc::now().timestamp();
        let message_id = env.header.message_id.clone();
        {
            let mut seen = seen_messages.write().await;
            // Evict entries older than 300 seconds.
            seen.retain(|_, &mut ts| now - ts < 300);
            // Check for duplicate.
            if seen.contains_key(&message_id) {
                // Silently drop replayed messages.
                return;
            }
            // Record first-seen timestamp.
            seen.insert(message_id, now);
        }

        let handler = handlers.read().await.get(&env.header.intent).cloned();
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
