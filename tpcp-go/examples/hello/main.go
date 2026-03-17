// hello demonstrates a minimal two-node TPCP handshake using the Go SDK.
package main

import (
	"fmt"
	"log"
	"time"

	"github.com/tpcp-protocol/tpcp-go/tpcp"
)

func main() {
	// --- Server node ---
	serverIdentity, serverKey, err := tpcp.GenerateIdentity("server")
	if err != nil {
		log.Fatal(err)
	}
	server := tpcp.NewTPCPNode(serverIdentity, serverKey)

	received := make(chan string, 1)
	server.RegisterHandler(tpcp.IntentHandshake, func(env *tpcp.TPCPEnvelope) {
		received <- fmt.Sprintf("server got HANDSHAKE from %s", env.Header.SenderID)
	})

	if err := server.Listen(":9000"); err != nil {
		log.Fatal(err)
	}
	defer server.Stop()
	time.Sleep(100 * time.Millisecond) // let server start

	// --- Client node ---
	clientIdentity, clientKey, err := tpcp.GenerateIdentity("client")
	if err != nil {
		log.Fatal(err)
	}
	client := tpcp.NewTPCPNode(clientIdentity, clientKey)

	if err := client.Connect("ws://localhost:9000"); err != nil {
		log.Fatal(err)
	}
	defer client.Stop()

	payload := tpcp.NewTextPayload("hello from Go client")
	if err := client.SendMessage("ws://localhost:9000", serverIdentity.AgentID, tpcp.IntentHandshake, payload); err != nil {
		log.Fatal(err)
	}

	select {
	case msg := <-received:
		fmt.Println(msg)
		fmt.Println("TPCP Go SDK hello example completed successfully.")
	case <-time.After(3 * time.Second):
		log.Fatal("timeout waiting for handshake")
	}
}
