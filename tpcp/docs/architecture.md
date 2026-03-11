# TPCP Architecture Deep-Dive

TPCP is built on three foundational pillars designed to eliminate the bottlenecks of traditional LLM text-chat.

## 1. Ed25519 Cryptographic Trust Layer
In decentralized agent swarms, identity spoofing is a critical vulnerability. TPCP guarantees source authenticity via cryptography rather than centralized tokens.

### How it Works
1. **Identity Generation:** Upon initialization (`AgentIdentityManager`), every node generates an explicit Ed25519 elliptic curve keypair via PyNaCl/tweetnacl.
2. **Dynamic Signature:** Every outbound `Payload` is serialized into a stable JSON string (`fast-json-stable-stringify`). The private key signs these exact byte sequences, affixing a Base64 signature to the `TPCPEnvelope`.
3. **Receipt Validation:** Inbound payloads hit the `TPCPNode` middleware. The node parses the sender's known `public_key` from the peer registry and mathematically asserts the `signature` against the payload buffer. Any tampering is immediately dropped.

## 2. LWW-Map CRDT Resolution (Conflict-Free Memory)
Agents operating asynchronously across the world will inevitably write data concurrently. Traditional architectures require slow database locking mechanisms to handle this. TPCP uses Conflict-Free Replicated Data Types (CRDTs).

### The Lamport Clock Tie-Breaker
The `LWWMap` (Last-Writer-Wins Map) tracks three variables for every key: the raw `value`, a `logical_timestamp`, and a `writer_id`.

When two nodes broadcast a `State_Sync` for the same key simultaneously:
1. The mathematical `merge()` operation compares the `logical_timestamp` locally against the inbound packet.
2. The larger timestamp mathematically wins.
3. **If timestamps are perfectly identical**, a deterministic tie-breaker enforces lexical sorting of the agent UUID (`writer_id`).
4. Both nodes arrive at the **exact same internal state** instantly, completely resolving the race condition without central authority.

## 3. A-DNS (Agent Domain Name System)
Instead of forcing static IP tracking, TPCP utilizes an opt-in global WebSocket relay registry. 

Nodes boot up and fire a `DISCOVER_SYN` packet to the `ADNSRelayServer`. The relay maps their unique `agent_id` to their active socket stream. Nodes can address packets directly to remote UUIDs without knowing their physical host IP, letting the relay forward the payloads dynamically.
