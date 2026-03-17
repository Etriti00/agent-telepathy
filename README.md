<p align="center">
  <h1 align="center">🧠 TPCP</h1>
  <p align="center"><strong>Telepathy Communication Protocol</strong></p>
  <p align="center">
    The open protocol that lets AI agents communicate like they're telepathic.<br/>
    Any framework. Any model. Any modality. Zero friction.
  </p>
</p>

<p align="center">
  <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="License: AGPL v3"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://www.typescriptlang.org/"><img src="https://img.shields.io/badge/TypeScript-Ready-3178c6?logo=typescript&logoColor=white" alt="TypeScript"></a>
  <a href="https://go.dev/"><img src="https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go&logoColor=white" alt="Go"></a>
  <a href="https://www.rust-lang.org/"><img src="https://img.shields.io/badge/Rust-stable-DEA584?logo=rust&logoColor=white" alt="Rust"></a>
  <a href="https://openjdk.org/"><img src="https://img.shields.io/badge/Java-21+-ED8B00?logo=openjdk&logoColor=white" alt="Java"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <img src="https://img.shields.io/badge/version-0.4.1-orange" alt="Version 0.4.1">
  <a href="https://github.com/Etriti00/agent-telepathy/actions/workflows/ci.yml"><img src="https://github.com/Etriti00/agent-telepathy/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <a href="#-the-problem">Problem</a> •
  <a href="#-the-solution">Solution</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-multimodal-communication">Multimodal</a> •
  <a href="#-documentation">Docs</a> •
  <a href="#%EF%B8%8F-licensing">License</a>
</p>

---

## 🔥 The Problem

Right now, the AI agent ecosystem is fragmented. You build an agent in **CrewAI**, another in **LangGraph**, maybe one in **AutoGen** — and they **cannot talk to each other**. Every framework is a walled garden.

Want to connect a Claude-powered research agent with a Gemini-powered analyst and an Ollama-hosted local executor? Today, you'd have to write hundreds of lines of glue code — fragile text-passing, polling loops, no security, no state consistency, and it breaks the moment you change anything.

**Multi-agent AI is supposed to be the future. But right now, agents can't even have a conversation.**

---

## 💡 The Solution

TPCP gives agents **telepathy**.

It's an open protocol that lets any AI agent — regardless of what LLM powers it, what framework it runs on, or what modality it works with — **seamlessly communicate with any other agent**, as if they were sharing one brain.

```
┌──────────────────┐                          ┌──────────────────┐
│  Claude Opus 4.6 │◄────── TPCP Protocol ───►│  Gemini 2.5 Pro  │
│  (Research Agent) │    Signed Envelopes      │  (Analysis Agent) │
│  CrewAI / Python  │    CRDT Memory Sync      │  LangGraph / Py   │
└────────┬─────────┘    Vector Telepathy       └────────┬─────────┘
         │              Multimodal Media                │
         └──────────┐                   ┌───────────────┘
                    ▼                   ▼
              ┌──────────────────────────┐
              │      A-DNS Relay         │
              │   Global Discovery       │
              │  Challenge-Response Auth  │
              └────────────┬─────────────┘
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  Ollama Llama  │ │  Whisper Voice │ │  DALL-E Vision │
│  (Local Exec)  │ │  (Audio Agent) │ │  (Image Agent) │
│  Custom / Py   │ │  OpenAI / Py   │ │  React / TS    │
└────────────────┘ └────────────────┘ └────────────────┘
```

**A Claude agent, a Gemini agent, an Ollama agent, a voice agent, and a vision agent — all sharing state, sending media, and collaborating in real-time. Different LLMs. Different frameworks. Different modalities. One protocol.**

---

## ⚡ What Makes It a Game-Changer

| What You Get | How It Works |
|:-------------|:-------------|
| **Any LLM ↔ Any LLM** | Claude, GPT, Gemini, Llama, Mistral, Qwen, Kimi — TPCP doesn't care what model powers the agent. It just moves signed envelopes between nodes. |
| **Any Framework ↔ Any Framework** | CrewAI, LangGraph, AutoGen, Semantic Kernel, custom code — adapters decouple the framework from the wire format. |
| **Text ↔ Image ↔ Audio ↔ Video** | A vision agent sends an image → a text agent reads the caption. A voice agent sends audio → everyone gets the transcript. **No agent is ever excluded.** |
| **Conflict-Free Shared Memory** | Multiple agents write to the same state simultaneously → the CRDT mathematically guarantees they all converge to the same result. No locks. No coordinator. |
| **Cryptographic Trust** | Every message is signed with Ed25519. Unsigned or tampered messages are dropped. No spoofing possible. |
| **Works Anywhere** | Agents discover each other globally via the A-DNS relay. No static IPs. No VPNs. Just connect and go. |
| **Zero Data Loss** | If an agent goes offline, messages queue up and drain automatically when it's back. No messages are ever lost. |
| **Universal Edge Bridging** | Bridge autonomous robots (ROS2), Smart Homes (HomeAssistant/Matter), Industrial Sensors (MQTT), and Zapier/Siri Webhooks natively into the swarm constraint-free. |
| **5 SDK Languages** | First-class SDKs for Python, TypeScript, Go, Rust, and Java — use whatever your team already knows. |

---

## 🚀 Quick Start

### Python — Connect agents, robotics, and smart homes

```bash
cd tpcp
pip install -e ".[dev]"
pip install "tpcp-core[edge]"  # Required for Edge hardware adapters (ROS2, MQTT, HA, Webhook)
```

```python
import asyncio
from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
from tpcp.core.node import TPCPNode

# Agent powered by ANY model — Claude, GPT, Gemini, Llama, anything
identity = AgentIdentity(
    framework="MyAgent",
    public_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    modality=["text", "image"]
)

async def main():
    async with TPCPNode(identity, port=8000) as node:
        # Share state — all peers see this instantly
        node.shared_memory.set("status", "analyzing")

        # Send a message to another agent (any LLM, any framework)
        await node.send_message(
            target_id=peer_uuid,
            intent=Intent.TASK_REQUEST,
            payload=TextPayload(content="Summarize the Q3 report")
        )

asyncio.run(main())
```

### TypeScript — Real-time dashboard

```bash
cd tpcp-ts && npm install && npm run build
```

```typescript
import { TPCPNode } from 'tpcp-sdk';

const node = new TPCPNode({
  agent_id: crypto.randomUUID(),
  framework: "React-Dashboard",
  capabilities: ["visualization"],
  public_key: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
  modality: ["text"]
}, "127.0.0.1", 9000);

// Live CRDT state updates from the Python agent swarm
node.on("onStateSync", (state) => {
  console.log("Swarm state:", state);
  // Update your React UI here
});

// Receive vector embeddings for semantic search
node.on("onVectorSync", ({ modelId, dimensions }) => {
  console.log(`Got ${dimensions}d embedding from ${modelId}`);
});

await node.startListening();
```

### Go — High-performance microservices

```bash
cd tpcp-go && go mod tidy
```

```go
package main

import (
	"fmt"
	"github.com/tpcp-protocol/tpcp-go/tpcp"
)

func main() {
	// Generate a cryptographic identity (Ed25519 keypair)
	identity, privKey, _ := tpcp.GenerateIdentity("GoService")
	node := tpcp.NewTPCPNode(identity, privKey)

	// Handle incoming task requests
	node.RegisterHandler(tpcp.IntentTaskRequest, func(env *tpcp.TPCPEnvelope) {
		fmt.Printf("Received task from %s\n", env.Header.SenderID)
	})

	// Start listening for peer connections
	go node.Listen(":9000")
	<-node.Ready

	// Connect to another agent and send a message
	node.Connect("ws://localhost:8000")
	node.SendMessage("ws://localhost:8000", tpcp.IntentTaskRequest,
		tpcp.NewTextPayload("Analyze dataset"))

	select {} // Block forever
}
```

### Rust — Embedded and systems agents

```bash
cd tpcp-rs && cargo build
```

```rust
use tpcp_std::{TPCPNode, AgentIdentity, Intent};
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let identity = AgentIdentity {
        agent_id: uuid::Uuid::new_v4().to_string(),
        framework: "RustAgent".into(),
        public_key: "".into(),
        capabilities: vec![],
        modality: vec!["text".into()],
    };

    let node = TPCPNode::new(identity);

    // Register a handler for incoming messages
    node.register_handler(Intent::TaskRequest, |envelope| {
        println!("Got task: {:?}", envelope.payload);
    }).await;

    // Send a signed message to a peer
    node.send_message(
        "ws://127.0.0.1:8000",
        Intent::TaskRequest,
        json!({"payload_type": "text", "content": "Process sensor data"}),
    ).await?;

    Ok(())
}
```

### Java — Enterprise integration

```bash
cd tpcp-java && mvn compile
```

```java
import io.tpcp.core.TPCPNode;
import io.tpcp.core.IdentityManager;
import io.tpcp.schema.*;
import com.fasterxml.jackson.databind.ObjectMapper;

public class Main {
    public static void main(String[] args) throws Exception {
        // Generate identity with Ed25519 keypair
        IdentityManager im = new IdentityManager();
        AgentIdentity identity = im.createIdentity("JavaService");

        TPCPNode node = new TPCPNode(identity, im);

        // Handle incoming messages
        node.registerHandler(Intent.TASK_REQUEST, envelope -> {
            System.out.println("Task from: " + envelope.header.senderId);
        });

        // Connect to a peer and send a message
        node.connect("ws://localhost:8000").join();

        ObjectMapper mapper = new ObjectMapper();
        TextPayload payload = new TextPayload("Generate quarterly report");
        node.sendMessage("ws://localhost:8000",
            Intent.TASK_REQUEST, mapper.valueToTree(payload));
    }
}
```

### Run the demos

```bash
python examples/01_handshake_demo.py      # Identity exchange
python examples/02_shared_memory_demo.py   # CRDT state sync
python examples/03_telepathy_demo.py       # Vector sharing
```

---

## 🎨 Multimodal Communication

TPCP isn't limited to text. Agents can share **images, audio, video, and any binary file** — with automatic text fallbacks so no agent is left out.

### Every payload type at a glance

| Payload | What It Carries | Text Fallback | Example Use Case |
|:--------|:----------------|:-------------|:-----------------|
| `TextPayload` | Natural language | — | Agent reasoning, instructions, reports |
| `ImagePayload` | PNG, JPEG, WebP images | `caption` | DALL-E output → vision analysis → text agent reads caption |
| `AudioPayload` | WAV, MP3, OGG audio | `transcript` | Whisper transcription → ElevenLabs TTS → text agent reads transcript |
| `VideoPayload` | MP4, WebM video | `description` | Sora generation → video analysis → text agent reads description |
| `VectorEmbeddingPayload` | Dense float arrays | `raw_text_fallback` | Semantic search across the swarm's collective knowledge |
| `CRDTSyncPayload` | Key-value state | — | Conflict-free shared memory between all agents |
| `BinaryPayload` | Any file (PDF, dataset) | `description` | Sharing documents, spreadsheets, 3D models |
| `TelemetryPayload` | Industrial sensor readings | — | OPC-UA, Modbus, CANbus, MQTT sensor data streams |

### How cross-modal communication works

```
┌─────────────────────────┐
│  DALL-E Agent (Vision)  │
│  Generates image        │──► ImagePayload
│                         │    caption: "Revenue chart Q3"
└─────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  Claude Agent (Text)    │
│  Reads the caption      │──► "I see the revenue chart shows 23% growth..."
│  Can't see the image    │
│  But understands it     │    ✅ Still participates fully
└─────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  Whisper Agent (Voice)  │
│  Reads Claude's text    │──► AudioPayload
│  Generates speech       │    transcript: "Revenue grew 23%..."
└─────────────────────────┘
```

**Every agent participates. Every modality connects. Nobody is excluded.**

---

## 🧩 Core Concepts

### 🔗 LWW-Map CRDT
Two agents write to the same key at the same time. Instead of a conflict, the CRDT resolves it mathematically — the higher Lamport timestamp wins. If they're identical, the agent UUID breaks the tie deterministically. Both agents **always converge to the same state**. Optionally backed by SQLite for persistence.

### 🛡️ Ed25519 Cryptographic Identity
Every message is signed. Every signature is verified. Keys can persist across restarts via file or environment variable. The A-DNS relay uses challenge-response — agents must *prove* they own their private key before registering.

### 🧠 Vector Telepathy
Share raw 1536-dimensional embeddings between agents. The `VectorBank` stores them and supports **cosine similarity search** — find the most relevant knowledge fragment across the entire swarm.

### 🌍 A-DNS Global Discovery
One command to run the relay. Agents connect from anywhere — home lab, AWS, a phone — and find each other by UUID. No static IPs, no VPN, no DNS records.

### 📦 Dead-Letter Queue
Agent goes offline? Messages queue up (max 500/peer). When it's back, they drain one-at-a-time with safe re-queueing. **Zero data loss, guaranteed.**

---

## 🏗️ Repository Structure

```
agent-telepathy/
├── tpcp/                    # Python SDK (tpcp-core)
│   ├── tpcp/
│   │   ├── core/            # TPCPNode, MessageQueue (DLQ)
│   │   ├── schemas/         # Pydantic schemas (8 payload types)
│   │   ├── security/        # Ed25519 with key persistence
│   │   ├── memory/          # LWWMap CRDT (+ SQLite), VectorBank (+ cosine search)
│   │   ├── adapters/        # CrewAI, LangGraph, ROS2, HomeAssistant, MQTT adapters
│   │   └── relay/           # A-DNS relay & FastAPI Webhook Gateway
│   ├── examples/            # Runnable demos
│   ├── tests/               # pytest test suite
│   └── pyproject.toml
│
├── tpcp-ts/                 # TypeScript SDK — Node.js / React / Next.js
│   ├── src/
│   │   ├── core/            # TPCPNode (EventEmitter), DLQ, VectorBank
│   │   ├── schemas/         # Zod schemas (8 payload types)
│   │   ├── security/        # tweetnacl Ed25519 with key persistence
│   │   └── memory/          # LWWMap CRDT
│   └── package.json
│
├── tpcp-go/                 # Go SDK
│   ├── tpcp/                # TPCPNode, envelope schemas, Ed25519 signing
│   └── go.mod
│
├── tpcp-rs/                 # Rust SDK (workspace: tpcp-core + tpcp-std)
│   ├── tpcp-core/           # Schema types, Ed25519, CRDT
│   ├── tpcp-std/            # TPCPNode with tokio-tungstenite transport
│   └── Cargo.toml
│
├── tpcp-java/               # Java SDK
│   ├── src/main/java/io/tpcp/
│   │   ├── schema/          # Jackson-annotated envelope types
│   │   └── core/            # TPCPNode with Java-WebSocket transport
│   └── pom.xml
│
├── k8s/                     # Kubernetes deployment manifests
│   ├── relay/               # A-DNS relay Deployment, Service, NetworkPolicy
│   └── redis/               # Redis StatefulSet, Secret, NetworkPolicy
│
├── docs/                    # Project-level documentation
├── LICENSE                  # AGPL v3
├── COMMERCIAL_LICENSE.md    # Enterprise terms
├── CONTRIBUTING.md          # Dev setup & PR guide
└── SECURITY.md              # Vulnerability policy
```

---

## 📖 Documentation

| Document | What's Inside |
|:---------|:-------------|
| [Step-by-Step Guide & API Reference](tpcp/docs/api_reference.md) | Full walkthrough: install → connect → share state → send media → global discovery |
| [Architecture Deep-Dive](tpcp/docs/architecture.md) | Ed25519, CRDT math, multimodal design, A-DNS flow, DLQ mechanics |
| [Universal Edge Architecture](tpcp/docs/universal_edge.md) | Hardware integration: ROS2 (Nvidia Jetson), MQTT (ESP32), HA (Matter), Webhook Gateway |
| [Contributing](CONTRIBUTING.md) | Dev setup, code style, PR workflow |
| [Security Policy](SECURITY.md) | Vulnerability reporting and crypto model |

---

## ⚖️ Licensing

TPCP is **dual-licensed** to support both open-source and commercial use.

| Use Case | License | Cost |
|:---------|:--------|:-----|
| Open-source projects | [AGPL v3](LICENSE) | Free |
| Internal tools & research | [AGPL v3](LICENSE) | Free |
| Closed-source SaaS / proprietary backends | [Commercial License](COMMERCIAL_LICENSE.md) | Contact maintainer |

---

<p align="center">
  <strong>Built for the multi-agent era.</strong><br/>
  Give your agents telepathy. ⚡
</p>
