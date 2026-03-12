# TPCP Architecture Deep-Dive

TPCP is built on five foundational pillars designed to let any AI agent — regardless of framework, model, or modality — communicate seamlessly with any other.

---

## 1. Ed25519 Cryptographic Trust Layer

In decentralized agent swarms, identity spoofing is a critical vulnerability. TPCP guarantees source authenticity via elliptic-curve cryptography rather than centralized tokens.

### How It Works

1. **Identity Generation:** On startup, each node generates (or loads from disk) an Ed25519 keypair via `AgentIdentityManager`. Keys can be persisted to `~/.tpcp/identity.key` or injected via the `TPCP_PRIVATE_KEY` environment variable for stable identity across restarts.

2. **Signing:** Every outbound payload is serialized into a deterministic JSON string (keys sorted, no whitespace). The private key signs these exact bytes, producing a base64 signature attached to the `TPCPEnvelope`.

3. **Verification:** Inbound envelopes hit the node's security middleware. The node looks up the sender's registered `public_key` and mathematically verifies the signature against the payload. Any tampering → packet is dropped immediately.

4. **Challenge-Response (A-DNS):** When connecting to the global relay, nodes must prove they own the private key matching their declared public key by signing a random nonce the relay sends them. This prevents UUID spoofing.

---

## 2. LWW-Map CRDT — Conflict-Free Shared Memory

Agents operating asynchronously across the globe will inevitably write data concurrently. Traditional architectures require slow database locking. TPCP uses Conflict-Free Replicated Data Types (CRDTs) — data structures that are *mathematically guaranteed* to converge without coordination.

### The Lamport Clock Tie-Breaker

The `LWWMap` (Last-Writer-Wins Map) tracks three values for every key: the raw `value`, a `logical_timestamp` (Lamport clock), and a `writer_id`.

When two nodes broadcast a `State_Sync` for the same key simultaneously:

1. The `merge()` operation compares timestamps.
2. The **higher timestamp wins**.
3. If timestamps are **perfectly identical** → deterministic tie-breaker via lexical sort of the `writer_id` UUID.
4. Both nodes arrive at the **exact same state** — no central coordinator needed.

### Mathematical Properties
- **Commutativity:** `merge(A, B) == merge(B, A)`
- **Associativity:** `merge(merge(A, B), C) == merge(A, merge(B, C))`
- **Idempotence:** `merge(A, A) == A`

### Optional Persistence
Pass `db_path` to enable SQLite write-through:
```python
crdt = LWWMap(node_id="agent-1", db_path=Path(".tpcp/memory.db"))
# State survives restarts — hydrated from disk automatically
```

---

## 3. Multimodal Communication

TPCP doesn't limit agents to text. The protocol supports **seven payload types** covering every modality:

| Payload Type | Use Case | Example Models |
|:-------------|:---------|:---------------|
| `TextPayload` | Natural language messages, instructions, reasoning | GPT-4, Claude, Gemini, Llama, Qwen |
| `VectorEmbeddingPayload` | Semantic memory via dense embeddings | text-embedding-3-small, all-MiniLM-L6-v2 |
| `CRDTSyncPayload` | Conflict-free shared state | Any agent framework |
| `ImagePayload` | Photos, screenshots, generated images | DALL-E 3, Stable Diffusion, GPT-4V, Gemini Vision |
| `AudioPayload` | Voice recordings, TTS output, music | Whisper, ElevenLabs, OpenAI TTS |
| `VideoPayload` | Screen recordings, generated video | Sora, Runway Gen-3, Gemini Video |
| `BinaryPayload` | PDFs, datasets, 3D models, any file | Any agent |

### Cross-Modal Fallbacks

Every multimodal payload includes an optional **text fallback** field (`caption`, `transcript`, `description`). This means:

- A **vision agent** sends an `ImagePayload` with `caption="A chart showing revenue growth"` → a **text-only agent** can read the caption and still participate.
- A **voice agent** sends an `AudioPayload` with `transcript="Meeting notes from the team call"` → every agent gets the content.
- A **video agent** sends a `VideoPayload` with `description="A walkthrough of the UI changes"` → text agents understand the context.

This design ensures **no agent is ever excluded from the conversation**, regardless of its modality.

---

## 4. A-DNS — Agent Domain Name System

Instead of forcing static IP tracking, TPCP uses a global WebSocket relay with security built in.

### Registration Flow

```
Agent                          A-DNS Relay
  │                                │
  │── HANDSHAKE (identity + pubkey) ──►│
  │                                │
  │◄── ADNS_CHALLENGE (nonce) ─────│  (relay generates random nonce)
  │                                │
  │── signed(nonce, private_key) ──►│  (agent proves identity ownership)
  │                                │
  │◄── ADNS_REGISTERED ───────────│  (relay adds to verified registry)
  │                                │
  │◄──────── routed messages ──────│  (can now send/receive globally)
```

### Security Features
- **Challenge-response authentication** — prevents UUID spoofing
- **Rate limiting** — token bucket at 30 msg/sec per connection (configurable)
- **TTL enforcement** — packets with expired TTL are dropped before forwarding
- **Stale connection cleanup** — dead connections are pruned automatically

---

## 5. Dead-Letter Queue (DLQ) — Network Resilience

Messages destined for offline peers are not dropped. They are cached in a bounded, per-peer queue:

- **Max 500 messages per peer** with LRU eviction (won't eat your RAM)
- **Exponential backoff reconnection** — automatically retries until the peer is back
- **One-at-a-time safe drain** — if the connection drops mid-drain, the failed message is re-queued at the front, preventing data loss
- **Atomic front-queuing** via `enqueue_front()` — no messages lost, ever

---

## Protocol Envelope Structure

Every TPCP message is a signed envelope:

```json
{
  "header": {
    "message_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-03-11T18:00:00Z",
    "sender_id": "agent-claude-uuid",
    "receiver_id": "agent-gemini-uuid",
    "intent": "Media_Share",
    "ttl": 30,
    "protocol_version": "0.3.0"
  },
  "payload": {
    "payload_type": "image",
    "data_base64": "/9j/4AAQSkZJRg...",
    "mime_type": "image/jpeg",
    "width": 1024,
    "height": 768,
    "source_model": "dall-e-3",
    "caption": "Architecture diagram of the payment system"
  },
  "signature": "base64-ed25519-signature"
}
```
