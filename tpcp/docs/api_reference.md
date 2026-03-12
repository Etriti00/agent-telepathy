# TPCP API Reference & Step-by-Step Guide

This guide walks you through everything you need to connect AI agents using TPCP, from first install to production deployment.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Creating Your First Node](#2-creating-your-first-node)
3. [Connecting Two Agents](#3-connecting-two-agents)
4. [Sharing State with CRDTs](#4-sharing-state-with-crdts)
5. [Sending Images, Audio & Video](#5-sending-images-audio--video)
6. [Vector Telepathy](#6-vector-telepathy)
7. [Global Discovery via A-DNS](#7-global-discovery-via-a-dns)
8. [Using Framework Adapters](#8-using-framework-adapters)
9. [API Reference](#9-api-reference)

---

## 1. Installation

### Python
```bash
cd tpcp
pip install -e ".[dev]"
pip install "tpcp-core[edge]"  # Install hardware bridging optional dependencies
```

### TypeScript
```bash
cd tpcp-ts
npm install
npm run build
```

---

## 2. Creating Your First Node

A TPCP node is the entry point for any agent. It handles identity, connections, and message routing.

### Python
```python
import asyncio
from tpcp.schemas.envelope import AgentIdentity
from tpcp.core.node import TPCPNode

# Create an identity — Ed25519 keys are auto-generated
identity = AgentIdentity(
    framework="MyAgent",
    public_key="",                    # Auto-filled on node creation
    capabilities=["research", "code"],
    modality=["text", "image"]        # What modalities this agent supports
)

async def main():
    # The async context manager handles startup and graceful shutdown
    async with TPCPNode(identity, host="127.0.0.1", port=8000) as node:
        print(f"Node {node.identity.agent_id} is live!")
        # Your agent logic here...
        await asyncio.sleep(60)  # Keep alive

asyncio.run(main())
```

### TypeScript
```typescript
import { TPCPNode } from 'tpcp-ts';

const identity = {
  agent_id: crypto.randomUUID(),
  framework: "ReactDashboard",
  capabilities: ["visualization"],
  public_key: "",     // Auto-filled
  modality: ["text"]
};

const node = new TPCPNode(identity, "127.0.0.1", 9000);
await node.startListening();
```

---

## 3. Connecting Two Agents

### Direct P2P Connection

```python
# Agent A (port 8000)
async with TPCPNode(identity_a, port=8000) as agent_a:
    
    # Agent B (port 8001) 
    async with TPCPNode(identity_b, port=8001) as agent_b:
        
        # Register each other
        agent_a.register_peer(agent_b.identity, "ws://127.0.0.1:8001")
        agent_b.register_peer(agent_a.identity, "ws://127.0.0.1:8000")
        
        # Now they can talk!
        from tpcp.schemas.envelope import Intent, TextPayload
        
        await agent_a.send_message(
            target_id=agent_b.identity.agent_id,
            intent=Intent.TASK_REQUEST,
            payload=TextPayload(content="Analyze the Q3 earnings report")
        )
```

### Via Broadcast Discovery

```python
# Agent auto-discovers peers via seed nodes
async with TPCPNode(identity, port=8000) as node:
    await node.broadcast_discovery(seed_nodes=[
        "ws://192.168.1.50:8001",
        "ws://192.168.1.51:8002"
    ])
    # Peers auto-register from handshake payloads
```

---

## 4. Sharing State with CRDTs

The LWW-Map CRDT lets any number of agents share a consistent key-value store without conflicts.

```python
async with TPCPNode(identity, port=8000) as node:
    # Write to shared memory (automatically increments the Lamport clock)
    node.shared_memory.set("task_status", "in_progress")
    node.shared_memory.set("findings", {"anomaly_detected": True, "confidence": 0.94})
    
    # Read from shared memory
    status = node.shared_memory.get("task_status")  # "in_progress"
    
    # Broadcast state to all peers
    from tpcp.schemas.envelope import Intent, CRDTSyncPayload
    
    state_payload = CRDTSyncPayload(
        crdt_type="LWW-Map",
        state=node.shared_memory.serialize_state(),
        vector_clock={"agent-1": node.shared_memory.logical_clock}
    )
    
    await node.send_message(
        target_id=peer_id,
        intent=Intent.STATE_SYNC,
        payload=state_payload
    )
    # The receiving node's shared_memory.merge() runs automatically
```

---

## 5. Sending Images, Audio & Video

TPCP lets agents share any media type. Each media payload includes a text fallback so that agents which don't support that modality can still participate.

### Sending an Image

```python
import base64
from tpcp.schemas.envelope import Intent, ImagePayload

# Read an image file
with open("chart.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

await node.send_message(
    target_id=peer_id,
    intent=Intent.MEDIA_SHARE,
    payload=ImagePayload(
        data_base64=image_data,
        mime_type="image/png",
        width=1024,
        height=768,
        source_model="dall-e-3",
        caption="Revenue growth chart for Q3 2026"  # Text fallback
    )
)
```

### Sending Audio

```python
from tpcp.schemas.envelope import AudioPayload

with open("meeting_notes.wav", "rb") as f:
    audio_data = base64.b64encode(f.read()).decode()

await node.send_message(
    target_id=peer_id,
    intent=Intent.MEDIA_SHARE,
    payload=AudioPayload(
        data_base64=audio_data,
        mime_type="audio/wav",
        sample_rate=16000,
        duration_seconds=45.2,
        source_model="whisper-1",
        transcript="The team discussed the launch timeline..."  # Text fallback
    )
)
```

### Sending Video

```python
from tpcp.schemas.envelope import VideoPayload

with open("demo.mp4", "rb") as f:
    video_data = base64.b64encode(f.read()).decode()

await node.send_message(
    target_id=peer_id,
    intent=Intent.MEDIA_SHARE,
    payload=VideoPayload(
        data_base64=video_data,
        mime_type="video/mp4",
        width=1920,
        height=1080,
        duration_seconds=120.0,
        fps=30.0,
        source_model="sora-1",
        description="A walkthrough of the new UI redesign"  # Text fallback
    )
)
```

### Sending Any Binary File

```python
from tpcp.schemas.envelope import BinaryPayload

with open("report.pdf", "rb") as f:
    pdf_data = base64.b64encode(f.read()).decode()

await node.send_message(
    target_id=peer_id,
    intent=Intent.MEDIA_SHARE,
    payload=BinaryPayload(
        data_base64=pdf_data,
        mime_type="application/pdf",
        filename="quarterly_report.pdf",
        description="Q3 2026 financial report (47 pages)"
    )
)
```

---

## 6. Vector Telepathy

Skip tokenization entirely. Share raw embeddings for semantic search across the swarm.

```python
from tpcp.schemas.envelope import Intent, VectorEmbeddingPayload

# Generate an embedding (using your preferred model)
embedding = openai.embeddings.create(input="AI agent architectures", model="text-embedding-3-small")
vector = embedding.data[0].embedding  # 1536 floats

await node.send_message(
    target_id=peer_id,
    intent=Intent.STATE_SYNC_VECTOR,
    payload=VectorEmbeddingPayload(
        model_id="text-embedding-3-small",
        dimensions=1536,
        vector=vector,
        raw_text_fallback="AI agent architectures"
    )
)

# On the receiving node, search semantically:
results = node.vector_bank.search(query_vector=my_query_embedding, top_k=5)
for payload_id, similarity, text in results:
    print(f"  Score: {similarity:.3f} — {text}")
```

---

## 7. Global Discovery via A-DNS

### Start the Relay Server

```bash
python -m tpcp.relay.server
# ✓ A-DNS Global Relay on ws://0.0.0.0:9000
# ✓ Challenge-response authentication: ENABLED
# ✓ Rate limiting: 30 msg/sec per connection
```

### Connect Agents to the Relay

```python
# Any agent anywhere in the world can discover any other
async with TPCPNode(identity, port=8000, adns_url="ws://your-relay:9000") as node:
    # Automatically:
    # 1. Connects to relay
    # 2. Completes challenge-response authentication
    # 3. Registers in global directory
    # 4. Can now send/receive from any other registered agent by UUID
    
    await node.send_message(remote_agent_uuid, Intent.TASK_REQUEST, payload)
```

---

## 8. Using Framework Adapters

TPCP ships adapters for popular frameworks. Use `create_adapter()` to auto-wire identity.

### CrewAI

```python
from tpcp.adapters.crewai_adapter import CrewAIAdapter

async with TPCPNode(identity, port=8000) as node:
    adapter = node.create_adapter(CrewAIAdapter)
    
    # Convert CrewAI task output to a signed TPCP envelope
    envelope = adapter.pack_thought(
        target_id=peer_uuid,
        raw_output="The analysis shows a 23% increase in engagement...",
        intent=Intent.TASK_REQUEST
    )
```

### LangGraph

```python
from tpcp.adapters.langgraph_adapter import LangGraphAdapter

async with TPCPNode(identity, port=8000) as node:
    adapter = node.create_adapter(LangGraphAdapter)
    
    # Convert LangGraph state dict to a signed TPCP envelope
    envelope = adapter.pack_thought(
        target_id=peer_uuid,
        raw_output={"status": "complete", "findings": [....]},
        intent=Intent.STATE_SYNC
    )
```

### Edge Hardware Adapters (v0.3.0+)

The Universal Edge modules securely bridge the physical world to the swarm and require `pip install "tpcp-core[edge]"`.

- **`ROS2Adapter`**: Bridges Nvidia Jetsons and robotics natively to Swarm memory mapping optical telemetry to `ImagePayload` loops.
- **`HomeAssistantAdapter`**: Hooks directly into the HA REST/SSE events bus wrapping Apple HomeKit and Matter events into TPCP CRDT vectors.
- **`MQTTAdapter`**: Acts natively as a lightweight IoT subscriber linking standard ESP32/Pico industrial sensors tightly to AI analysis states dynamically. 
- **`Stateless Webhook Gateway`** (`tpcp/relay/webhook.py`): Secure FastAPI proxy verifying inbound POST requests from Siri / Zapier / iOS scripts and pipelining them directly into the WebSocket Mesh via a localized node.

*See the [Universal Edge Architecture Guide](universal_edge.md) for setup and deployment workflows.*

---

## 9. API Reference

### `TPCPNode`

| Method | Description |
|:-------|:------------|
| `__init__(identity, host, port, adns_url, identity_manager, key_path, auto_save_key)` | Create a node with optional key persistence and A-DNS |
| `async start_listening()` | Start WebSocket server and A-DNS connection |
| `async stop_listening()` | Graceful shutdown of all connections |
| `register_peer(identity, address)` | Add a peer to the routing table |
| `remove_peer(agent_id)` | Remove a peer and close cached connection |
| `async send_message(target_id, intent, payload)` | Sign and send a message (DLQ on failure) |
| `async broadcast_discovery(seed_nodes)` | Announce presence to peers or A-DNS |
| `register_handler(intent, handler)` | Register a custom async handler for an intent |
| `create_adapter(adapter_class)` | Factory for framework adapters with auto-wired identity |

### `LWWMap`

| Method | Description |
|:-------|:------------|
| `set(key, value, timestamp?, writer_id?)` | Write a value (auto-increments Lamport clock) |
| `get(key)` | Read the resolved value |
| `merge(other_state)` | Merge remote CRDT state (commutative, associative, idempotent) |
| `serialize_state()` | Export for transport |
| `to_dict()` | Clean key→value dictionary |

### `VectorBank`

| Method | Description |
|:-------|:------------|
| `store_vector(payload_id, vector, model_id, raw_text?)` | Store an embedding |
| `get_vector(payload_id)` | Retrieve by ID |
| `search(query_vector, top_k=5)` | Cosine similarity search |
| `list_vectors()` | Metadata listing (no raw arrays) |

### `AgentIdentityManager`

| Method | Description |
|:-------|:------------|
| `__init__(private_key_bytes?, key_path?, auto_save?)` | Load or generate Ed25519 keypair |
| `save_key(path?)` | Persist private key to disk |
| `sign_payload(payload_dict)` | Sign a JSON payload |
| `sign_bytes(data)` | Sign raw bytes (for challenge-response) |
| `verify_signature(public_key, signature, payload)` | Static: verify a signed payload |
| `verify_bytes(public_key, signature, data)` | Static: verify signed bytes |

### Intents

| Intent | Description |
|:-------|:------------|
| `HANDSHAKE` | Identity exchange and peer registration |
| `TASK_REQUEST` | Request another agent to perform work |
| `STATE_SYNC` | CRDT state synchronization |
| `STATE_SYNC_VECTOR` | Vector embedding sharing |
| `MEDIA_SHARE` | Image, audio, video, or binary data sharing |
| `CRITIQUE` | Feedback on another agent's output |
| `TERMINATE` | Signal graceful shutdown |

### Payload Types

| Type | Fields | Text Fallback Field |
|:-----|:-------|:-------------------|
| `TextPayload` | `content`, `language` | — (is text) |
| `VectorEmbeddingPayload` | `model_id`, `dimensions`, `vector` | `raw_text_fallback` |
| `CRDTSyncPayload` | `crdt_type`, `state`, `vector_clock` | — (structured data) |
| `ImagePayload` | `data_base64`, `mime_type`, `width`, `height`, `source_model` | `caption` |
| `AudioPayload` | `data_base64`, `mime_type`, `sample_rate`, `duration_seconds`, `source_model` | `transcript` |
| `VideoPayload` | `data_base64`, `mime_type`, `width`, `height`, `duration_seconds`, `fps`, `source_model` | `description` |
| `BinaryPayload` | `data_base64`, `mime_type`, `filename` | `description` |
