# TPCP TypeScript SDK

![Version](https://img.shields.io/badge/version-0.4.1-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-green)
![Node](https://img.shields.io/badge/node-%3E%3D18-brightgreen)

TypeScript/Node.js implementation of the **Telepathy Communication Protocol (TPCP)** -- a universal wire protocol for multi-agent AI communication.

## Installation

```bash
npm install tpcp-ts
```

## Quick Start

```typescript
import {
  AgentIdentityManager,
  TPCPEnvelopeSchema,
  Intent,
  PROTOCOL_VERSION,
  TPCPNode,
} from "tpcp-ts";
import { v4 as uuidv4 } from "uuid";

// 1. Create (or load) an Ed25519 identity
const idManager = new AgentIdentityManager();

const identity = {
  agent_id: uuidv4(),
  framework: "my-agent",
  capabilities: ["text", "critique"],
  public_key: idManager.publicKeyBase64,
  modality: ["text"],
};

// 2. Build a signed envelope
const envelope = {
  header: {
    message_id: uuidv4(),
    timestamp: new Date().toISOString(),
    sender_id: identity.agent_id,
    receiver_id: "TARGET_AGENT_UUID",
    intent: Intent.TASK_REQUEST,
    ttl: 30,
    protocol_version: PROTOCOL_VERSION,
  },
  payload: {
    payload_type: "text" as const,
    content: "Summarise the latest telemetry readings.",
    language: "en",
  },
  signature: null,
};

// Validate with Zod
const parsed = TPCPEnvelopeSchema.parse(envelope);

// 3. Connect to a relay
const node = new TPCPNode(identity, "127.0.0.1", 8000);
node.on("message", (env) => {
  console.log("Received:", env.header.intent);
});
```

## Features

- **Ed25519 Cryptography** -- deterministic key generation, signing, and verification via TweetNaCl.
- **Zod Schema Validation** -- every envelope is validated against the TPCP v0.4.0 schema at runtime.
- **CRDT LWW-Map** -- built-in Last-Writer-Wins Map for conflict-free shared agent memory.
- **Dead-Letter Queue (DLQ)** -- automatic message buffering and retry for unreachable peers.
- **Browser + Node Targets** -- conditional exports let you bundle for both server and browser environments.
- **Multimodal Payloads** -- text, image, audio, video, binary, vector embeddings, CRDT sync, and telemetry.
- **ACK / NACK / Broadcast** -- first-class acknowledgement, negative-acknowledgement, and broadcast intents.
- **Chunked Transfers** -- `chunk_info` support for large payloads split across multiple envelopes.

## Protocol Documentation

For the full protocol specification, schema definitions, and multi-language SDK guides, see the [root TPCP README](../README.md).

## License

This project is licensed under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html).
For commercial licensing inquiries, see [COMMERCIAL_LICENSE.md](../COMMERCIAL_LICENSE.md).
