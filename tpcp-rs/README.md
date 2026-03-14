# tpcp-rs — Rust SDK for TPCP

Rust implementation of the Telepathy Communication Protocol (TPCP) v0.4.0.

## Workspace Crates

| Crate | Description |
|---|---|
| `tpcp-core` | no_std-compatible types, Ed25519, LWW-Map CRDT |
| `tpcp-std` | Async TPCPNode with tokio + tokio-tungstenite |

## Quick Start

```toml
# Cargo.toml
[dependencies]
tpcp-std = { git = "https://github.com/tpcp-protocol/tpcp-rs" }
```

```rust
use tpcp_std::{TPCPNode, AgentIdentity, Intent};

#[tokio::main]
async fn main() {
    let identity = AgentIdentity {
        agent_id: "my-agent".into(),
        agent_type: "rust-agent".into(),
        public_key_b64: "".into(),
    };
    let node = TPCPNode::new(identity);
    node.register_handler(Intent::TaskRequest, |env| {
        println!("Task: {}", env.payload);
    }).await;
    node.listen("0.0.0.0:8765").await.unwrap();
}
```

## no_std Usage (embedded / ARM Cortex-M)

```toml
[dependencies]
tpcp-core = { git = "...", default-features = false }  # no_std
```

## Run Example

```bash
cargo run --example hello -p tpcp-std
```
