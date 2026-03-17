# tpcp-java — Java SDK for TPCP

Java implementation of the Telepathy Communication Protocol (TPCP) v0.4.1 (Java 17+, tested on Java 21).

## Features

- **Jackson** — JSON serialization with snake_case field mapping
- **BouncyCastle** — Ed25519 signing/verification
- **OkHttp** — WebSocket transport (client mode)
- **LWWMap** — Thread-safe Last-Write-Wins CRDT
- **DLQ** — Dead Letter Queue (capped at 100)

## Build & Test

```bash
cd tpcp-java
mvn test
```

## Quick Start

```java
IdentityManager mgr = new IdentityManager();
AgentIdentity identity = mgr.createIdentity("my-java-agent");
TPCPNode node = new TPCPNode(identity, mgr);

node.registerHandler(Intent.TASK_REQUEST, env ->
    System.out.println("Task: " + env.payload));

node.connect("ws://relay.tpcp.io:8765").join();
node.sendMessage("ws://relay.tpcp.io:8765", Intent.HANDSHAKE,
    mapper.valueToTree(new TextPayload("hello from Java")));
```
