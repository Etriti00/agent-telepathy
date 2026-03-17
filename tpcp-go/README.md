# tpcp-go — Go SDK for TPCP

Go implementation of the Telepathy Communication Protocol (TPCP) v0.4.1.

## Install

```bash
go get github.com/tpcp-protocol/tpcp-go
```

## Quick Start

```go
import "github.com/tpcp-protocol/tpcp-go/tpcp"

// Generate identity
identity, privKey, _ := tpcp.GenerateIdentity("my-agent")

// Create node
node := tpcp.NewTPCPNode(identity, privKey)

// Register handlers
node.RegisterHandler(tpcp.IntentTaskRequest, func(env *tpcp.TPCPEnvelope) {
    fmt.Printf("Task from %s\n", env.Header.SenderID)
})

// Listen (server mode)
node.Listen(":9000")

// Connect to peer (client mode)
node.Connect("ws://other-agent:9000")

// Send message
node.SendMessage("ws://other-agent:9000", tpcp.IntentHandshake,
    tpcp.NewTextPayload("hello"))
```

## Features

- **Ed25519 signing** — all messages optionally signed with canonical JSON
- **LWW-Map CRDT** — conflict-free shared memory (`node.Memory`)
- **Dead Letter Queue** — unhandled intents go to `node.DLQ`
- **WebSocket transport** — server and client modes via gorilla/websocket

## Run Example

```bash
cd examples/hello
go run main.go
```
