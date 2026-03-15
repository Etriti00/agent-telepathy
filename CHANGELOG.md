# Changelog

All notable changes to TPCP are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

---

## [0.4.0] — 2026-03-14

### Added
- **Go SDK** (`tpcp-go/`): full TPCPNode with gorilla/websocket, Ed25519, LWWMap, DLQ, inbound signature verification
- **Rust SDK** (`tpcp-rs/`): `tpcp-core` (no_std, `thumbv7em-none-eabihf`-compatible) + `tpcp-std` (tokio + tokio-tungstenite)
- **Java SDK** (`tpcp-java/`): OkHttp WebSocket, BouncyCastle Ed25519, Jackson, ConcurrentHashMap LWWMap
- **Industrial IoT adapters**: OPCUAAdapter, ModbusAdapter, CANbusAdapter (bridging factory PLCs and CAN-bus devices into TPCP)
- **7 AI framework adapters**: AutoGen, PydanticAI, smolagents, OpenAI Agents SDK, LlamaIndex, Haystack, SemanticKernel
- **Schema additions**: `AckInfo`, `ChunkInfo`, `TelemetryPayload` / `TelemetryReading` models; `ACK`, `NACK`, `BROADCAST` intents
- **Protocol hardening**: ACK/NACK delivery confirmation, per-agent ACL, chunked transfer (chunker + reassembler), relay-proxy mode, broadcast fan-out
- **Kubernetes infrastructure**: Deployment (3 replicas, anti-affinity), HPA (3–20), Redis StatefulSet, nginx Ingress with WebSocket headers, cert-manager TLS
- **CLI tooling** (`tpcp.cli`): `keygen`, `send`, `listen`, `relay`, `inspect` commands
- **MockTPCPNode** testing utility: in-process no-socket mock with `connect_pair()`, `inject_message()`, `assert_received()`
- **TypeScript browser/WASM target**: `WebSocketFactory` abstraction, `defaultWebSocketFactory()` auto-detects Node.js vs browser; lazy fs/path/os imports
- **Health endpoint** on relay server (`/health`) for Kubernetes readiness probes
- **CI jobs**: `industrial-adapters`, `go-tests`, `rust-tests`, `java-tests`

### Changed
- `PROTOCOL_VERSION` bumped to `"0.4.0"`
- Intent wire values aligned across all SDKs: `Task_Request`, `State_Sync`, `Media_Share` (canonical underscore format)
- `AgentIdentity` field `public_key_b64` renamed to `public_key`; `agent_type` renamed to `framework`; added `capabilities`, `modality`
- `MessageHeader` gains `ttl` field (default 30) and ISO 8601 `timestamp` string (replaces `timestamp_ms` in new SDKs)
- Relay server reads `TPCP_PORT` env var (default 8765) instead of hardcoded 9000
- `send_broadcast` now sends ONE message to `BROADCAST_UUID` via relay (fan-out by relay); P2P fallback retained
- All SDK signatures use standard base64 encoding (not URL-safe) for cross-language compatibility

### Fixed
- Go/Rust/Java SDKs previously used URL-safe base64 for signatures — incompatible with Python's `base64.b64encode()` — now fixed
- Go/Rust/Java SDKs used PascalCase intent wire values (`TaskRequest`) — mismatch with Python/TS (`Task_Request`) — now fixed
- Go SDK had no inbound signature verification — now verifies against registered peer keys
- Java SDK `TPCPNode.onMessage` had no signature verification — now drops tampered envelopes from known peers
- `BaseFrameworkAdapter._logical_clock` AttributeError on first use (MQTT/HomeAssistant adapters)

---

## [0.3.0] — 2026-03-12

### Added
- **Multimodal payloads**: ImagePayload, AudioPayload, VideoPayload, BinaryPayload
- **Universal Edge bridging**: ROS2 (robotics), MQTT (IoT/ESP32), HomeAssistant (smart home), Webhook gateway (Zapier/Siri)
- **Webhook Gateway**: FastAPI-based HTTP bridge for external trigger injection
- **Cross-language test**: TypeScript ↔ Python Ed25519 signature compatibility test
- TypeScript SDK DLQ + VectorBank in `core/node.ts`
- A-DNS challenge-response authentication with Ed25519 signing

### Changed
- `PROTOCOL_VERSION` bumped to `"0.3.0"`
- All payload types use discriminated union via `payload_type` literal field

---

## [0.2.0] — 2026-03-11

### Added
- **Dead-Letter Queue (DLQ)**: In-memory message queue with FIFO drain, max 500/peer, front-enqueue for safe mid-drain failure
- **VectorBank**: Cosine similarity search over stored embeddings
- **A-DNS Relay Server**: Per-connection token bucket rate limiting, TTL enforcement, clean deregistration on disconnect
- **SSL/TLS support**: Optional `ssl_context` on TPCPNode and all outbound connections
- **Key persistence**: `AgentIdentityManager` with file + env var key loading, `auto_save` option
- **SQLite persistence**: Optional for LWWMap CRDT via aiosqlite
- **Connection pooling**: Cached WebSocket connections to peers
- **Exponential backoff**: On A-DNS reconnect and peer DLQ drain

### Fixed
- All initial audit issues from v0.1.0 resolved

---

## [0.1.0] — 2026-03-11

### Added
- **Core Protocol**: TPCPNode WebSocket server/client, peer registry, intent routing
- **Cryptographic Identity**: Ed25519 keypair generation and management via `cryptography` library
- **Message Signing**: `sign_payload()` deterministic JSON serialization + Ed25519 signatures
- **Signature Verification**: `verify_signature()` static method, drops unsigned/tampered packets
- **LWW-Map CRDT**: Lamport clock conflict resolution with UUID tie-breaking
- **Deduplication**: `_seen_messages` replay protection cache
- **TTL Enforcement**: Per-hop TTL decrement, drops at 0
- **7 Payload Types**: Text, VectorEmbedding, CRDTSync, Image, Audio, Video, Binary
- **Framework Adapters**: CrewAI, LangGraph (base class for extensibility)
- **A-DNS Global Discovery**: Agent Domain Name System relay for peer discovery without static IPs
- **TypeScript SDK**: Full parity with Python SDK — TPCPNode EventEmitter, LWWMap CRDT, AgentIdentityManager
- **Dual License**: AGPL v3 (open source) + Commercial License
- **CI/CD**: GitHub Actions for Python (pytest, ruff, mypy) and TypeScript (jest)

[Unreleased]: https://github.com/tpcp-protocol/tpcp/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/tpcp-protocol/tpcp/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tpcp-protocol/tpcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tpcp-protocol/tpcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tpcp-protocol/tpcp/releases/tag/v0.1.0
