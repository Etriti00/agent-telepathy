//! Minimal two-node TPCP HANDSHAKE example using tpcp-std.
use tpcp_std::{TPCPNode, AgentIdentity, Intent};
use std::sync::Arc;
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    // Server
    let server_identity = AgentIdentity {
        agent_id: "server-001".into(),
        agent_type: "hello-server".into(),
        public_key_b64: "".into(),
    };
    let server = Arc::new(TPCPNode::new(server_identity));

    server.register_handler(Intent::Handshake, |env| {
        println!("Server received HANDSHAKE from {}", env.header.sender_id);
        println!("Payload: {}", env.payload);
    }).await;

    server.listen("127.0.0.1:9001").await.expect("failed to listen");
    sleep(Duration::from_millis(100)).await; // let server bind

    // Client
    let client_identity = AgentIdentity {
        agent_id: "client-001".into(),
        agent_type: "hello-client".into(),
        public_key_b64: "".into(),
    };
    let client = TPCPNode::new(client_identity);

    client.send_message(
        "ws://127.0.0.1:9001",
        Intent::Handshake,
        serde_json::json!({"payload_type": "text", "content": "hello from Rust client"}),
    ).await.expect("send failed");

    sleep(Duration::from_millis(200)).await;
    println!("TPCP Rust SDK hello example completed.");
}
