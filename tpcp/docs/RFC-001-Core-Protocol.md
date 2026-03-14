# RFC-001: TPCP — Telepathy Communication Protocol
**Version:** 0.4.0
**Status:** Draft
**Authors:** TPCP Contributors
**Updated:** 2026-03-14

---

## Abstract

The Telepathy Communication Protocol (TPCP) is a framework-agnostic, LLM-agnostic, and modality-agnostic messaging standard for autonomous AI agents. It defines a cryptographically signed envelope format, a structured intent taxonomy, and a relay-based discovery layer (A-DNS) that together allow agents built on different frameworks — CrewAI, LangGraph, AutoGen, ROS2, and others — to communicate without bilateral coupling. TPCP v0.4.0 extends the original text-only design with multimodal payloads, industrial IoT bridge adapters, conflict-free shared memory, and a portable IDL so that conformant SDK implementations can exist in any language.

---

## 1. Motivation

Modern multi-agent systems are built as silos. A CrewAI crew cannot natively delegate to a LangGraph graph. A Python agent cannot exchange state with a TypeScript agent. An industrial IoT sensor bridge has no standard interface to an LLM reasoning node. The underlying problems are:

1. **Framework lock-in.** Each orchestration framework defines its own internal message types. Crossing framework boundaries requires custom glue code that is brittle and non-reusable.
2. **LLM lock-in.** Embedding vectors are model-specific. There is no standard envelope for passing a `text-embedding-3-small` vector from an OpenAI agent to a local `all-MiniLM-L6-v2` agent alongside a text fallback.
3. **Modality gap.** Text-only protocols cannot carry images, audio, video, or sensor telemetry without out-of-band channels, defeating end-to-end auditability.
4. **Hardware gap.** Industrial protocols — OPC-UA, Modbus TCP, CANbus, MQTT — have no defined mapping onto agent-to-agent semantics.
5. **No verifiable identity.** Ad-hoc string-based agent IDs cannot be authenticated; any node can claim any identity.
6. **No global discovery.** Agents must know peer addresses in advance; there is no equivalent of DNS for agent identifiers.

TPCP addresses all six problems with a single, versioned wire format and a small set of normative rules.

---

## 2. Design Goals

1. **Framework-agnostic.** No runtime dependency on any orchestration library. Adapters exist at the edges; the protocol core is pure data.
2. **LLM-agnostic.** `VectorEmbeddingPayload` carries `model_id` and `dimensions` alongside the vector, plus a `raw_text_fallback` for receivers that cannot consume the embedding directly.
3. **Modality-agnostic.** Native payload types for text, vector embeddings, images, audio, video, binary, CRDT state, and telemetry.
4. **Cryptographically secure.** Every envelope MAY be signed with Ed25519. The relay (A-DNS) REQUIRES a signed nonce before routing messages for a node.
5. **Conflict-free distributed state.** The `CRDTSyncPayload` and `LWWMap` implementation provide mathematically guaranteed convergence without a central coordinator.
6. **Globally discoverable.** The A-DNS relay acts as a rendezvous point. Agents register by UUID; the relay routes by UUID without needing IP addresses.
7. **Hardware-bridgeable.** The `TelemetryPayload` and `BaseFrameworkAdapter` interface give OPC-UA, Modbus, CANbus, MQTT, HomeAssistant, and ROS2 a normalized path into the agent mesh.
8. **Language-portable via IDL.** Protobuf and JSON Schema definitions in `tpcp/proto/` allow conformant SDKs in Go, Rust, Java, and any other language without re-deriving the schema from Python source.

---

## 3. Core Concepts

### 3.1 Agent Identity

Every agent operating on the TPCP network MUST possess a unique `AgentIdentity`. This object is exchanged during the `Handshake` intent and stored in each peer's registry.

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | UUID v4 | yes | Globally unique identifier. Assigned once; never reused. |
| `framework` | string | yes | Framework powering the agent, e.g. `"CrewAI"`, `"LangGraph"`, `"ROS2"`. |
| `capabilities` | list[string] | no | Declared skills, e.g. `["web_search", "code_execution"]`. Used for tag-based multicast routing. |
| `public_key` | string | yes | Base64-encoded Ed25519 public key. Used to verify signed envelopes. |
| `modality` | list[string] | no | Supported payload modalities, e.g. `["text", "image", "audio"]`. Defaults to `["text"]`. |

### 3.2 Intent Taxonomy

Every envelope MUST include an `intent` field in its header. Implementations MUST handle all ten intents; unknown values encountered by an older receiver SHOULD log a warning and drop the message rather than crash.

| Intent | Direction | Description |
|---|---|---|
| `Handshake` | bidirectional | Initial peer discovery. Payload MUST be an `AgentIdentity` serialized as a `TextPayload`. |
| `Task_Request` | requester → worker | Delegate a unit of work to another agent. |
| `State_Sync` | any | Push CRDT state (`CRDTSyncPayload`) to a peer for convergence. |
| `State_Sync_Vector` | any | Push a vector embedding (`VectorEmbeddingPayload`) representing shared semantic context. |
| `Media_Share` | any | Transfer an image, audio clip, video, or binary artifact. |
| `Critique` | reviewer → author | Structured feedback on a prior result; `content` references original `message_id`. |
| `Terminate` | any | Signal graceful end of a session or task. Receivers MUST NOT ignore this intent. |
| `ACK` | receiver → sender | Positive delivery confirmation. MUST include `ack_info.acked_message_id`. |
| `NACK` | receiver → sender | Negative delivery confirmation (parsing error, ACL denial, etc.). MUST include `ack_info.acked_message_id`. |
| `Broadcast` | sender → mesh | Addressed to the nil UUID; the relay delivers to all registered peers. |

### 3.3 Payload Types

Payloads use a discriminated union keyed on `payload_type`. Parsers MUST use `payload_type` to select the correct schema before deserializing remaining fields.

| Payload Type | `payload_type` discriminator | Description | Text fallback field |
|---|---|---|---|
| TextPayload | `"text"` | Plain text message with ISO 639-1 language tag. | `content` |
| VectorEmbeddingPayload | `"vector_embedding"` | Dense vector with `model_id`, `dimensions`, and `vector` array. | `raw_text_fallback` |
| CRDTSyncPayload | `"crdt_sync"` | LWW-Map state with `vector_clock` for convergence. | — |
| ImagePayload | `"image"` | Base64-encoded image with `mime_type`, optional `width`/`height`. | `caption` |
| AudioPayload | `"audio"` | Base64-encoded audio with `mime_type`, optional `transcript`. | `transcript` |
| VideoPayload | `"video"` | Base64-encoded video with `mime_type`, optional `description`. | `description` |
| BinaryPayload | `"binary"` | Raw binary, any MIME type, optional `filename` and `description`. | `description` |
| TelemetryPayload | `"telemetry"` | Batch sensor readings from industrial hardware. | — |

### 3.4 Envelope Wire Format

All messages are serialized as UTF-8 JSON objects conforming to `TPCPEnvelope`.

```json
{
  "header": {
    "message_id": "123e4567-e89b-12d3-a456-426614174000",
    "timestamp": "2026-03-14T12:00:00Z",
    "sender_id": "987f6543-e21b-12d3-a456-426614174111",
    "receiver_id": "111a2222-b33c-44d5-e555-666677778888",
    "intent": "Task_Request",
    "ttl": 30,
    "protocol_version": "0.4.0"
  },
  "payload": {
    "payload_type": "text",
    "content": "Summarize the attached error logs.",
    "language": "en"
  },
  "signature": "<base64-encoded Ed25519 signature>",
  "ack_info": null,
  "chunk_info": null
}
```

`ack_info` and `chunk_info` are `null` in normal messages and populated only for ACK/NACK responses and chunked transfers respectively. Unknown top-level fields MUST be ignored by receivers.

---

## 4. Security Model

### 4.1 Ed25519 Cryptographic Identity

Each agent generates an Ed25519 keypair at initialization. The public key is advertised in `AgentIdentity.public_key` (base64-encoded). The private key never leaves the agent process.

**Signing procedure (normative):**

1. Serialize `envelope.payload` as canonical JSON: `json.dumps(payload_dict, sort_keys=True, separators=(',', ':'))`.
2. Encode the resulting UTF-8 string as bytes.
3. Sign with Ed25519 private key using `cryptography.hazmat.primitives.asymmetric.ed25519`.
4. Base64-encode the 64-byte signature.
5. Place in `envelope.signature`.

**Verification procedure (normative):**

1. Retrieve `sender_identity.public_key` from the peer registry.
2. Decode from base64 to obtain the 32-byte Ed25519 public key.
3. Re-serialize `envelope.payload` using the identical canonical JSON procedure.
4. Call `public_key.verify(signature_bytes, payload_bytes)`.
5. Reject the message if verification raises.

Envelopes with `signature = null` are accepted but SHOULD be flagged as unverified. Relay servers operating in strict mode MAY reject unsigned envelopes.

### 4.2 A-DNS Challenge-Response Authentication

Before the relay will route any messages on behalf of a connecting node, it performs a challenge-response handshake to prove the node controls the private key corresponding to its claimed `agent_id`:

```
Client                           Relay
  |                                |
  |-- WebSocket connect ---------->|
  |                                |
  |<-- {"type":"ADNS_CHALLENGE",   |
  |      "nonce":"<random-hex>"}   |
  |                                |
  |-- {"type":"ADNS_REGISTER",     |
  |    "agent_id":"<uuid>",        |
  |    "public_key":"<b64>",       |
  |    "nonce_signature":"<b64>"} ->|
  |                                |
  | (relay verifies signature)     |
  |                                |
  |<-- {"type":"ADNS_REGISTERED",  |
  |      "agent_id":"<uuid>"}      |
```

The relay verifies `nonce_signature` against `public_key` before inserting the node into its registry. A node that cannot sign the nonce cannot register and cannot receive routed messages.

### 4.3 Per-Agent ACL

`TPCPNode` exposes an `ACLPolicy` that is evaluated before any inbound envelope is dispatched to the application handler.

- `default_allow: bool` — whether intents not explicitly listed are permitted.
- Per-entry rules: `(sender_agent_id, intent) → allow | deny`.
- The `Terminate` intent has special protection: if a node is configured with `default_allow=False` and has not explicitly allowed `Terminate`, the message is still delivered but flagged. Implementations MUST log all ACL denials.

---

## 5. Communication Patterns

### 5.1 Peer-to-Peer Handshake

Direct connections are established over WebSockets. Agents discover each other either via A-DNS lookup or out-of-band address sharing.

```
Agent A                          Agent B
  |                                |
  |-- WebSocket connect ---------->|
  |                                |
  |-- TPCPEnvelope --------------->|
  |   intent: Handshake            |
  |   payload: AgentIdentity(A)    |
  |                                |
  |   (B validates schema,         |
  |    verifies signature,         |
  |    stores A in peer registry)  |
  |                                |
  |<-- TPCPEnvelope ---------------|
  |    intent: Handshake           |
  |    payload: AgentIdentity(B)   |
  |                                |
  |   (A validates, stores B)      |
  |                                |
  |<====== bidirectional ==------->|
```

After a successful Handshake both peers hold each other's `AgentIdentity`, enabling signature verification on all subsequent messages.

### 5.2 ACK/NACK Delivery Confirmation

For reliable delivery, senders MAY set `require_ack=True` on the node's send call. The protocol then:

1. Sender records the `message_id` in a pending-ack table with a 30-second timeout.
2. Receiver, upon successful parsing and ACL pass, emits an `ACK` envelope with `ack_info.acked_message_id` set to the original `message_id`.
3. Sender removes the entry from the pending-ack table on receipt of `ACK`.
4. If the receiver cannot process the message (schema error, ACL denial, unknown intent), it emits a `NACK` envelope instead.
5. A `NACK` or timeout causes the message to be re-queued to the Dead-Letter Queue (DLQ).

### 5.3 Broadcast and Multicast

**Broadcast** — set `receiver_id` to the nil UUID `00000000-0000-0000-0000-000000000000`. The relay delivers the message to every registered node. The sending node receives its own broadcast only if it is in the registry.

**Tag-based multicast** — set `receiver_id` to the nil UUID and include a capability tag in a `TextPayload`'s `content` or a custom field. Nodes that have subscribed to the matching capability string will process the message; others SHOULD discard it after reading the tag. This is a soft multicast implemented at the application layer; the relay delivers the broadcast to all, and each receiver filters.

### 5.4 Relay-Proxy (Client-Only) Mode

Environments that cannot bind a server port — browsers, serverless functions, NAT-restricted containers — use `RelayTPCPNode`. In this mode:

- The node does not start a local WebSocket server.
- All inbound messages arrive via the relay connection (the same outbound WebSocket used for registration).
- The relay acts as a full proxy: it holds the message in the DLQ until the client's persistent connection drains it.
- Outbound messages are routed through the relay to the destination, same as server-mode nodes.

This mode has identical security guarantees to direct connections; the relay cannot read payloads because it does not hold private keys.

---

## 6. Conflict-Free Shared Memory (CRDT)

### 6.1 LWW-Map Semantics

`LWWMap` is a Last-Writer-Wins Map where each key stores a `(value, lamport_timestamp, node_id)` tuple.

**Merge rule:** for a given key, the entry with the higher Lamport timestamp wins. If timestamps are equal, the entry with the lexicographically greater `node_id` (UUID string) wins. This tie-breaking rule is deterministic and identical across all implementations; it MUST NOT be changed between minor versions.

The LWW-Map is a proper CRDT: merge is commutative, associative, and idempotent. Agents exchange `CRDTSyncPayload` containing the full `state` dict and `vector_clock`. Upon receipt, the local map is merged key-by-key using the rule above.

### 6.2 Persistence

`LWWMap` accepts an optional `db_path: Path` argument. When provided, state is persisted to a SQLite database via `aiosqlite`. The schema is initialized on `await crdt.connect()`. On node restart, the map is hydrated from SQLite before any new messages are processed, providing durable shared memory across process boundaries.

---

## 7. Chunked Transfer

Large payloads — images, audio, video, large binary files — that exceed practical WebSocket frame sizes are split into chunks before transmission.

**`ChunkInfo` fields:**

| Field | Type | Description |
|---|---|---|
| `chunk_index` | int (≥0) | Zero-based index of this chunk within the transfer. |
| `total_chunks` | int (≥1) | Total number of chunks in this transfer. |
| `transfer_id` | UUID | Unique identifier shared by all chunks of a single logical payload. |

**Transfer rules:**

- The default maximum chunk size is 64 KB of base64-encoded payload data.
- Each chunk is a complete, individually signed `TPCPEnvelope` with `chunk_info` populated.
- `ChunkReassembler` buffers received chunks keyed by `transfer_id` and reconstructs the full payload once `chunk_index` 0 through `total_chunks - 1` have all arrived.
- Chunks MAY arrive out of order; the reassembler sorts by `chunk_index` before joining.
- If reassembly is not complete within 60 seconds of the first chunk, the transfer is abandoned and a `NACK` is returned for `transfer_id`.

---

## 8. Industrial IoT Bridge Layer

### 8.1 Supported Protocols

TPCP v0.4.0 ships bridge adapters for the following industrial and IoT protocols:

| Protocol | Python Library | Adapter Class | Typical Use |
|---|---|---|---|
| OPC-UA | `asyncua` | `OPCUAAdapter` | Factory automation, SCADA |
| Modbus TCP | `pymodbus` | `ModbusAdapter` | PLC register polling |
| CANbus | `python-can` | `CANAdapter` | Automotive, robotics |
| MQTT | `paho-mqtt` | `MQTTAdapter` | IoT sensor hubs |
| HomeAssistant | SSE (`aiohttp`) | `HomeAssistantAdapter` | Smart home state events |
| ROS2 | `rclpy` | `ROS2Adapter` | Mobile robotics, drones |

### 8.2 Adapter Pattern

All adapters inherit from `BaseFrameworkAdapter` and implement two methods:

- `pack_thought(thought: Any) -> TPCPEnvelope` — wraps native framework data into a TPCP envelope. Hardware adapters populate a `TelemetryPayload` with `sensor_id`, `unit`, `readings`, and `source_protocol`.
- `unpack_request(envelope: TPCPEnvelope) -> Any` — extracts the native representation from a received envelope for delivery to the framework runtime.

`TelemetryPayload` structure for sensor streams:

```json
{
  "payload_type": "telemetry",
  "sensor_id": "opcua_ns2_i_1001",
  "unit": "celsius",
  "source_protocol": "opcua",
  "readings": [
    {"value": 72.4, "timestamp_ms": 1741953600000, "quality": "Good"},
    {"value": 72.6, "timestamp_ms": 1741953601000, "quality": "Good"}
  ]
}
```

### 8.3 Normative Bridge Behavior

Adapters MUST conform to the following rules:

1. **Sign every envelope.** Hardware bridges authenticate with their own Ed25519 keypair registered under a `framework` of the originating protocol name (e.g., `"OPC-UA"`).
2. **Increment logical clock.** Each outbound envelope MUST reflect the adapter's current Lamport clock value, then increment it. This enables causal ordering of telemetry from mixed sources.
3. **Handle reconnection.** Adapters MUST implement exponential back-off reconnection to both the hardware endpoint and the TPCP relay. Loss of either connection MUST NOT silently drop data; buffering is required.
4. **Non-blocking dispatch.** Adapter `pack_thought()` MUST be non-blocking with respect to TPCP send operations; it MUST NOT await TPCP delivery before returning to the hardware poll loop. Use fire-and-forget async dispatch.

---

## 9. A-DNS Global Discovery Relay

### 9.1 Registration Flow

```
Client                           Relay
  |                                |
  |-- WebSocket connect ---------->|
  |<-- ADNS_CHALLENGE (nonce) -----|
  |-- ADNS_REGISTER                |
  |   (agent_id, public_key,       |
  |    signed nonce) ------------->|
  |   [relay verifies signature]   |
  |<-- ADNS_REGISTERED ------------|
  |                                |
  |   [now reachable by UUID]      |
```

The relay stores `{agent_id → websocket_connection}` in a registry. Multiple connections from the same `agent_id` replace the previous entry; the old connection is closed with a displacement notice.

### 9.2 Message Routing

When the relay receives an envelope from a registered sender:

1. Parse `header.receiver_id`.
2. If `receiver_id` is the nil UUID, deliver to all registered connections (broadcast).
3. Otherwise, look up `receiver_id` in the registry.
4. If not found, enqueue to the DLQ for that `receiver_id`.
5. If found, decrement `header.ttl` by 1. Drop (and NACK to sender) if `ttl` reaches 0.
6. Forward the envelope verbatim over the receiver's WebSocket.

The relay does not inspect or modify `payload` or `signature`. It only touches `header.ttl`.

Rate limiting: each connection is subject to a token bucket of 30 messages/second sustained throughput with a burst capacity of 60.

### 9.3 Dead-Letter Queue

Messages that cannot be delivered immediately (receiver offline or not yet registered) are held in a per-peer DLQ:

- Maximum capacity: 500 messages per receiver UUID.
- On capacity exceeded: oldest messages are evicted (FIFO drop).
- Auto-drain: when a peer reconnects and completes the challenge-response, the relay immediately begins draining its DLQ.
- DLQ entries are not persisted across relay restarts by default; a persistent relay MAY use a database backend for durability.

---

## 10. Multi-Language SDK Support

### 10.1 Protocol Definition Files

Machine-readable schema definitions are provided at:

- `tpcp/proto/tpcp.proto` — Protobuf 3 IDL covering all message types. Use to generate native types in Go, Java, C++, C#, Kotlin, etc.
- `tpcp/proto/tpcp.schema.json` — JSON Schema (Draft 2020-12) covering all message types. Use for TypeScript (`zod`/`ajv`), Rust (`schemars`), and runtime validation in any language.

Both files are the normative source of truth for non-Python SDKs. Any discrepancy between these files and this RFC should be treated as a bug in the files.

### 10.2 Canonical JSON Serialization (Cross-Language Requirement)

> **CRITICAL — read this before implementing a new SDK.**

The `signature` field in a `TPCPEnvelope` is computed over the serialized payload. For signature verification to succeed across language boundaries, every SDK MUST produce byte-for-byte identical serialization of the same payload object. The canonical form is:

```python
json.dumps(payload_dict, sort_keys=True, separators=(',', ':'))
```

Concretely:

- Keys are sorted **lexicographically** (Unicode code-point order).
- No spaces after `:` or `,`.
- The result is encoded as **UTF-8** bytes before signing.
- Floating-point values MUST be serialized without trailing zeros where the language runtime allows, and MUST NOT use scientific notation for values in the range `[1e-6, 1e21)`. Where rounding behavior differs across runtimes, the JSON string representation from the signing side is canonical; verifiers MUST preserve the exact bytes received rather than re-parsing floats.

**Example — Python:**
```python
import json
canonical = json.dumps(payload.model_dump(), sort_keys=True, separators=(',', ':'))
signature_bytes = private_key.sign(canonical.encode('utf-8'))
```

**Example — TypeScript:**
```typescript
import stableStringify from 'fast-json-stable-stringify';
const canonical = stableStringify(payloadObj);
const signatureBytes = ed25519.sign(Buffer.from(canonical, 'utf-8'), privateKey);
```

Any SDK that does not follow this exact serialization will produce signatures that cannot be verified by any other SDK. This is the single most common source of cross-language interoperability failures.

### 10.3 Available SDKs

| Language | Package | Repository | Status |
|---|---|---|---|
| Python | `tpcp-core` | `tpcp/` | Stable (reference implementation) |
| TypeScript | `tpcp-ts` | `tpcp-ts/` | Stable |
| Go | `tpcp-go` | TBD | Planned |
| Rust | `tpcp-rs` | TBD | Planned |
| Java | `tpcp-java` | TBD | Planned |

---

## 11. Forward Compatibility

TPCP follows a compatible evolution policy across minor and patch versions:

- **New optional fields** MAY be added to any message type in a minor version bump. Older receivers using Pydantic (Python) or Zod (TypeScript) will silently strip unknown fields on deserialization.
- **New `Intent` values** MAY be added in a minor version bump. Older receivers that encounter an unknown intent MUST log a warning and drop the message; they MUST NOT raise an unhandled exception or crash.
- **New `payload_type` discriminators** MAY be added in a minor version bump. Older receivers that encounter an unknown `payload_type` MUST log a warning and drop the message.
- **Removal or renaming** of any existing field or intent value requires a major version bump.
- `protocol_version` in `MessageHeader` allows receivers to detect and log version mismatches proactively.

**v0.3.0 ↔ v0.4.0 interoperability:** v0.3.0 senders do not include `modality` in `AgentIdentity` or `chunk_info` in envelopes. v0.4.0 receivers treat these as absent-optional and operate normally. v0.4.0 senders that include these fields are handled transparently by v0.3.0 Pydantic receivers because `Extra.ignore` strips unknown fields.

---

## Appendix A: Full Field Reference

### AgentIdentity

| Field | Type | Required | Default |
|---|---|---|---|
| `agent_id` | UUID | yes | `uuid4()` |
| `framework` | string | yes | — |
| `capabilities` | list[string] | no | `[]` |
| `public_key` | string | yes | — |
| `modality` | list[string] | no | `["text"]` |

### MessageHeader

| Field | Type | Required | Default |
|---|---|---|---|
| `message_id` | UUID | yes | `uuid4()` |
| `timestamp` | datetime (UTC) | yes | `now(utc)` |
| `sender_id` | UUID | yes | — |
| `receiver_id` | UUID | yes | — |
| `intent` | Intent enum | yes | — |
| `ttl` | int (≥0) | no | `30` |
| `protocol_version` | string | no | `"0.4.0"` |

### TPCPEnvelope

| Field | Type | Required | Notes |
|---|---|---|---|
| `header` | MessageHeader | yes | Routing and metadata. |
| `payload` | Payload (discriminated union) | yes | One of 8 payload types. |
| `signature` | string \| null | no | Base64 Ed25519 signature over canonical payload JSON. |
| `ack_info` | AckInfo \| null | no | Present only on ACK/NACK intents. |
| `chunk_info` | ChunkInfo \| null | no | Present only on chunked transfer envelopes. |

### AckInfo

| Field | Type | Description |
|---|---|---|
| `acked_message_id` | UUID | `message_id` of the envelope being acknowledged. |

### ChunkInfo

| Field | Type | Description |
|---|---|---|
| `chunk_index` | int (≥0) | Zero-based position of this chunk. |
| `total_chunks` | int (≥1) | Total chunks in this transfer. |
| `transfer_id` | UUID | Shared identifier for all chunks of one logical payload. |

---

## Appendix B: Compatibility Matrix

| Sender version | Receiver version | Result |
|---|---|---|
| 0.3.0 | 0.4.0 | Works — v0.4.0 receiver ignores missing optional fields (`modality`, `chunk_info`, etc.) |
| 0.4.0 | 0.3.0 | Works — v0.3.0 receiver ignores unknown optional fields and logs unknown intents |
| 0.4.0 | 0.4.0 | Full feature set available |
| 0.2.x | 0.4.0 | Partial — `State_Sync_Vector`, `Media_Share`, `Broadcast`, `ACK`, `NACK` intents absent; receivers log unknown intent warnings |
| 0.4.0 | 0.2.x | Not recommended — v0.2.x receivers may not implement graceful unknown-intent handling |
