# Changelog

All notable changes to TPCP are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

### Fixed
- Protocol version default in MessageHeader (was "0.2.0", now uses PROTOCOL_VERSION constant)
- Python CRDT tests now properly await async methods
- TypeScript SDK build errors (Zod v4 compatibility)
- TypeScript handshake signature verification (security parity with Python SDK)
- Webhook gateway standalone example used nonexistent `public_key_base64` attribute
- `BaseFrameworkAdapter._create_header()` now passes correct protocol version
- CI pipeline now actually gates on failures (removed `|| true` from all commands)

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

[Unreleased]: https://github.com/tpcp-protocol/tpcp/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/tpcp-protocol/tpcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tpcp-protocol/tpcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tpcp-protocol/tpcp/releases/tag/v0.1.0
