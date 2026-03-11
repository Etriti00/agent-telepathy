# TPCP — Telepathy Communication Protocol

> **Framework-agnostic, mathematically merged, cryptographically secure state synchronization for autonomous AI agents.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Ready-3178c6?logo=typescript)](https://www.typescriptlang.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

TPCP is an open protocol and SDK for connecting heterogeneous AI agent frameworks — CrewAI, LangGraph, AutoGen, custom agents — into a unified, self-organizing swarm. It replaces brittle text-chain integrations with mathematically sound state synchronization.

---

## Why TPCP?

Most multi-agent systems fall apart the moment you need two agents built with **different frameworks** to share context. You end up with fragile string-passing, polling loops, and no guarantees around consistency.

TPCP solves this at the protocol level:

| Problem | TPCP Solution |
|---|---|
| Framework lock-in | Adapter pattern decouples any LLM framework from the wire format |
| Race conditions in shared state | LWW-Map CRDT — mathematically conflict-free without locks |
| Identity spoofing | Ed25519 signatures — every packet is signed and verified |
| Text bottleneck | Vector Telepathy — share 1536d embeddings directly, skip tokenization |
| Peer discovery | A-DNS Relay — dynamic agent registration, no static IPs |

---

## Repository Structure

```
TPCP-Workspace/
├── tpcp/               # Python SDK & core server (tpcp-core)
│   ├── tpcp/
│   │   ├── core/       # TPCPNode, MessageQueue (DLQ)
│   │   ├── schemas/    # Pydantic envelope schemas
│   │   ├── security/   # Ed25519 AgentIdentityManager
│   │   ├── memory/     # LWWMap (CRDT), VectorBank
│   │   ├── adapters/   # CrewAI, LangGraph adapters
│   │   └── relay/      # A-DNS relay server
│   ├── examples/       # Runnable demos (handshake, memory, vectors)
│   ├── tests/          # pytest suite
│   └── pyproject.toml
│
└── tpcp-ts/            # TypeScript SDK (tpcp-ts) — Node.js / React / Next.js
    ├── src/
    │   ├── core/       # TPCPNode (EventEmitter-based)
    │   ├── schemas/    # Zod envelope schemas
    │   ├── security/   # tweetnacl Ed25519
    │   └── memory/     # LWWMap CRDT
    └── package.json
```

---

## Quick Start — Python (`tpcp-core`)

### 1. Install
```bash
cd tpcp
pip install -e ".[dev]"
```

### 2. Run the Handshake Demo
```bash
python examples/01_handshake_demo.py
```

### 3. Run the CRDT Shared Memory Demo
```bash
python examples/02_shared_memory_demo.py
```

### 4. Run the Vector Telepathy Demo
```bash
python examples/03_telepathy_demo.py
```

### 5. Run the Test Suite
```bash
pytest
```

---

## Quick Start — TypeScript (`tpcp-ts`)

### 1. Install
```bash
cd tpcp-ts
npm install
npm run build
```

### 2. Connect a Node (Node.js)
```typescript
import { TPCPNode } from './dist';

const identity = {
  agent_id: crypto.randomUUID(),
  framework: "React-Dashboard",
  capabilities: ["visualization"],
  public_key: ""  // auto-generated Ed25519
};

const node = new TPCPNode(identity, "127.0.0.1", 9000);

// Subscribe to merged CRDT state updates
node.on("onStateSync", (mergedState) => {
  console.log("Swarm State:", mergedState);
});

await node.startListening();
```

---

## Core Concepts

### 🔗 LWW-Map CRDT (Conflict-Free Memory)
No database locks. No polling. Two agents write to the same key simultaneously — the one with the higher Lamport timestamp wins. If timestamps collide, the tie-breaker is deterministic UUID lexical sort. Both agents always converge to the **same state**.

### 🛡️ Ed25519 Trust Layer
Every node generates an Ed25519 keypair on startup. All outbound messages are signed with the private key. Inbound messages are rejected if the signature fails verification against the registered public key.

### 🧠 Vector Telepathy
Bypass the text bottleneck entirely. Share raw embedding arrays (`List[float]`) across agents using `VectorEmbeddingPayload`. The receiving `VectorBank` stores them for semantic search or context injection.

### 🌍 A-DNS Global Discovery
Run the standalone relay to allow agents to discover each other globally without static IPs:
```bash
python -m tpcp.relay.server
# Relay now running on ws://0.0.0.0:9000
```
Agents connect with `adns_url="ws://your-relay:9000"` and are instantly discoverable by UUID.

---

## Documentation

- [Architecture Deep-Dive](tpcp/docs/architecture.md) — Ed25519, CRDT math, A-DNS
- [API Reference](tpcp/docs/api_reference.md) — TPCPNode, methods, intents
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

---

## ⚖️ Licensing

TPCP is dual-licensed.

**Open Source:** [AGPL v3](LICENSE) — free to use, modify, and distribute if your project is also open-source.

**Commercial:** Integrating TPCP in a closed-source SaaS or proprietary backend requires a [Commercial License](COMMERCIAL_LICENSE.md). Contact the maintainer for pricing.
