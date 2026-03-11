<p align="center">
  <h1 align="center">🧠 TPCP</h1>
  <p align="center"><strong>Telepathy Communication Protocol</strong></p>
  <p align="center">
    Framework-agnostic, mathematically merged, cryptographically secure<br/>
    state synchronization for autonomous AI agents.
  </p>
</p>

<p align="center">
  <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="License: AGPL v3"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://www.typescriptlang.org/"><img src="https://img.shields.io/badge/TypeScript-Ready-3178c6?logo=typescript&logoColor=white" alt="TypeScript"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <img src="https://img.shields.io/badge/version-0.2.0-orange" alt="Version 0.2.0">
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-why-tpcp">Why TPCP</a> •
  <a href="#-core-concepts">Concepts</a> •
  <a href="#-documentation">Docs</a> •
  <a href="#%EF%B8%8F-licensing">License</a>
</p>

---

## 🎯 What is TPCP?

TPCP is an **open protocol and dual-SDK** (Python + TypeScript) for connecting heterogeneous AI agent frameworks — CrewAI, LangGraph, AutoGen, custom agents — into a unified, self-organizing swarm.

It replaces brittle text-chain integrations with **mathematically sound state synchronization**, backed by CRDTs, Ed25519 cryptographic signatures, and a global discovery relay.

```
┌─────────────┐     TPCP Protocol      ┌─────────────┐
│  CrewAI      │◄──────────────────────►│  LangGraph   │
│  Agent       │   Signed Envelopes     │  Agent       │
│  (Python)    │   CRDT State Sync      │  (Python)    │
└──────┬───────┘   Vector Telepathy     └──────┬───────┘
       │                                        │
       └──────────┐            ┌───────────────┘
                  ▼            ▼
            ┌─────────────────────┐
            │    A-DNS Relay       │
            │  Global Discovery   │
            │ Challenge-Response  │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  React Dashboard    │
            │  (TypeScript SDK)   │
            │  Real-time Sync     │
            └─────────────────────┘
```

---

## 💡 Why TPCP?

Most multi-agent systems fall apart the moment you need two agents built with **different frameworks** to share context. You end up with fragile string-passing, polling loops, and zero guarantees around consistency.

TPCP solves this at the protocol level:

| Problem | TPCP Solution |
|:--------|:--------------|
| **Framework lock-in** | Adapter pattern decouples any LLM framework from the wire format |
| **Race conditions in shared state** | LWW-Map CRDT — mathematically conflict-free, no locks needed |
| **Identity spoofing** | Ed25519 signatures — every packet is signed and verified |
| **Text bottleneck** | Vector Telepathy — share 1536d embeddings directly, skip tokenization |
| **Peer discovery** | A-DNS Relay — dynamic registration with challenge-response auth |
| **Data loss on network partitions** | Dead-Letter Queue with exponential backoff and safe re-queueing |
| **State loss on restart** | Optional SQLite-backed CRDT persistence |

---

## 🚀 Quick Start

### Python SDK (`tpcp-core`)

```bash
# Install
cd tpcp
pip install -e ".[dev]"

# Run the demos
python examples/01_handshake_demo.py     # P2P identity exchange
python examples/02_shared_memory_demo.py  # CRDT state synchronization
python examples/03_telepathy_demo.py      # Vector embedding sharing

# Run tests (20 tests)
pytest -v
```

**Minimal example — two agents sharing state:**

```python
import asyncio
from tpcp.schemas.envelope import AgentIdentity, Intent, TextPayload
from tpcp.core.node import TPCPNode

identity = AgentIdentity(framework="MyAgent", public_key="")

async def main():
    async with TPCPNode(identity, "127.0.0.1", 8000) as node:
        # State changes propagate via CRDT — no conflicts, ever
        node.shared_memory.set("task_status", "complete")
        
        # Broadcast presence to the network
        await node.broadcast_discovery(seed_nodes=["ws://peer:8001"])

asyncio.run(main())
```

### TypeScript SDK (`tpcp-ts`)

```bash
# Install & build
cd tpcp-ts
npm install
npm run build
```

**Minimal example — React/Next.js real-time dashboard:**

```typescript
import { TPCPNode } from 'tpcp-ts';

const node = new TPCPNode({
  agent_id: crypto.randomUUID(),
  framework: "React-Dashboard",
  capabilities: ["visualization"],
  public_key: ""  // Auto-generated Ed25519
}, "127.0.0.1", 9000);

// Real-time CRDT state sync
node.on("onStateSync", (mergedState) => {
  console.log("Swarm state updated:", mergedState);
});

// Vector embedding ingestion
node.on("onVectorSync", ({ modelId, dimensions, bankSize }) => {
  console.log(`Received ${dimensions}d vector (${modelId}). Bank: ${bankSize}`);
});

await node.startListening();
```

---

## 🧩 Core Concepts

### 🔗 LWW-Map CRDT — Conflict-Free Shared Memory
No database locks. No polling. No coordinator. Two agents write to the same key simultaneously — the one with the higher Lamport timestamp wins. If timestamps collide, the tie-breaker is deterministic lexical sort. Both agents **always** converge to the same state. Optionally backed by SQLite for persistence across restarts.

### 🛡️ Ed25519 Trust Layer
Every node generates (or loads) an Ed25519 keypair. All outbound messages are signed. Inbound messages are **rejected** if the signature fails verification. Keys can be persisted to disk (`~/.tpcp/identity.key`) or loaded via the `TPCP_PRIVATE_KEY` environment variable for stable identity across restarts.

### 🧠 Vector Telepathy
Bypass the text bottleneck entirely. Share raw embedding arrays across agents using `VectorEmbeddingPayload`. The receiving `VectorBank` stores them and supports **cosine similarity search** for semantic retrieval across the swarm's collective knowledge.

### 🌍 A-DNS Global Discovery
Run the standalone relay for zero-config global peer discovery:
```bash
python -m tpcp.relay.server
# ✓ A-DNS Relay running on ws://0.0.0.0:9000
# ✓ Challenge-response authentication: ENABLED
# ✓ Rate limiting: 30 msg/sec per connection
```
Agents connect with `adns_url="ws://your-relay:9000"` and are authenticated via a cryptographic challenge-response handshake before registration.

### 📦 Dead-Letter Queue
Messages destined for offline peers are cached locally (bounded at 500/peer with LRU eviction). When the connection is restored, messages are drained one-at-a-time with safe re-queueing on failure — **zero data loss** during network partitions.

---

## 🏗️ Architecture

```
TPCP-Workspace/
├── tpcp/                    # Python SDK (tpcp-core)
│   ├── tpcp/
│   │   ├── core/            # TPCPNode, MessageQueue (DLQ)
│   │   ├── schemas/         # Pydantic envelope schemas (discriminated union)
│   │   ├── security/        # Ed25519 identity with key persistence
│   │   ├── memory/          # LWWMap CRDT (+ SQLite), VectorBank (+ cosine search)
│   │   ├── adapters/        # CrewAI, LangGraph framework adapters
│   │   └── relay/           # A-DNS relay (challenge-response + rate limiting)
│   ├── examples/            # Runnable demos
│   ├── tests/               # 20 pytest tests
│   └── pyproject.toml
│
├── tpcp-ts/                 # TypeScript SDK — Node.js / React / Next.js
│   ├── src/
│   │   ├── core/            # TPCPNode (EventEmitter), DLQ, VectorBank
│   │   ├── schemas/         # Zod envelope schemas (discriminated union)
│   │   ├── security/        # tweetnacl Ed25519 with key persistence
│   │   └── memory/          # LWWMap CRDT
│   └── package.json
│
├── LICENSE                  # AGPL v3
├── COMMERCIAL_LICENSE.md    # Enterprise licensing terms
├── CONTRIBUTING.md          # Development setup & PR guidelines
└── SECURITY.md              # Vulnerability reporting policy
```

---

## 📖 Documentation

| Document | Description |
|:---------|:------------|
| [Architecture Deep-Dive](tpcp/docs/architecture.md) | Ed25519 cryptography, CRDT mathematical proofs, A-DNS protocol |
| [API Reference](tpcp/docs/api_reference.md) | `TPCPNode` methods, intents, payload types |
| [Contributing Guide](CONTRIBUTING.md) | Dev setup, code style, PR workflow |
| [Security Policy](SECURITY.md) | Vulnerability reporting and security model |
| [Commercial License](COMMERCIAL_LICENSE.md) | Terms for closed-source integration |

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
  Built for the multi-agent era. ⚡
</p>
