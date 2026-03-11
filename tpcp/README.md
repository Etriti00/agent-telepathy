# TPCP: Telepathy Communication Protocol

**Framework-agnostic, mathematically merged, cryptographically secure state synchronization for autonomous AI agents.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Ready-blue)](https://www.typescriptlang.org/)

TPCP natively connects disparate AI agents (e.g., CrewAI, LangGraph, React Dashboards) into a unified, decentralized swarm. It moves beyond simple text-based chat strings, enabling agents to natively share semantic brain states, merge conflict-free memory, and guarantee network security using cryptographic mathematics.

---

## ⚡ Core Features

*   **🧠 Semantic Vector Sync (Telepathy):** Bypass the text bottleneck. Agents transmit compressed 1536-dimensional conceptual representations directly to peers using `VectorEmbeddingPayload`s. 
*   **🔗 Conflict-Free Shared Memory:** No external database locks required. The internal `LWWMap` (Last-Writer-Wins) CRDT utilizes Lamport logical clocks to deterministically merge distributed state across the network.
*   **🛡️ Ed25519 Cryptographic Trust:** Every agent spawns a mathematical identity. All payloads are signed and strictly verified by the `TPCPNode` middleware to prevent spoofing or tampering.
*   **🌍 A-DNS Global Discovery:** Dynamic Agent Domain Name System (A-DNS) relays allow local nodes to discover and route payloads to autonomous peers globally across decoupled subnets.
*   **📦 Cross-Language Architecture:** Fully featured SDKs available in both Python (`tpcp-core`) and TypeScript (`tpcp-ts`) for full-stack swarm intelligence.

---

## 🚀 Quick Start

Initialize a node, register a peer, and synchronize semantic memory in three lines of code.

### Python (Backend Node)
```python
import asyncio
from tpcp import TPCPNode, AgentIdentity, Intent, CRDTSyncPayload

async def main():
    # 1. Initialize cryptographic identity
    identity = AgentIdentity(framework="LangGraph")
    node = TPCPNode(identity=identity, host="127.0.0.1", port=8000)
    
    # 2. Update local state
    node.shared_memory.set("system_status", "DEFCON 1")
    
    # 3. Synchronize mathematically with a peer
    payload = CRDTSyncPayload(
        crdt_type="LWW-Map",
        state=node.shared_memory.serialize_state(),
        vector_clock={}
    )
    # The payload is auto-signed and encrypted on dispatch
    await node.send_message(peer_uuid, Intent.STATE_SYNC, payload)

asyncio.run(main())
```

### TypeScript (Frontend Client)
```typescript
import { TPCPNode, AgentIdentity } from 'tpcp-ts';

// 1. Initialize the UI Node
const identity: AgentIdentity = {
  agent_id: crypto.randomUUID(),
  framework: "React-Dashboard",
  capabilities: ["visualization"],
  public_key: "" // Auto-generated Ed25519
};

const node = new TPCPNode(identity, "127.0.0.1", 9000);

// 2. Wrap the node in reactive state hooks
node.on("onStateSync", (mergedState) => {
    // The LWWMap has safely resolved any merge conflicts!
    console.log("Global Swarm State Updated:", mergedState);
});

await node.startListening();
```

---

## ⚖️ Licensing & Commercial Use

TPCP is dual-licensed to support both the open-source community and enterprise integrations.

### Open-Source License (AGPLv3)
This project is open-sourced under the **GNU Affero General Public License v3.0 (AGPLv3)**. 
If you integrate TPCP into your project, **your entire project must also be open-sourced under the AGPLv3.** This includes any backend SaaS server actively routing TPCP network traffic.

### Commercial License
If you wish to integrate TPCP into **proprietary, closed-source enterprise applications** or utilize the network architecture within a commercial backend without being forced to open-source your intellectual property, you **MUST purchase a Commercial Use License**.

Please review the [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md) file for more information on terms and obtaining a license.
