package tpcp

import (
	"crypto/ed25519"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// TPCPNode is a TPCP agent node that can send and receive messages over WebSocket.
type TPCPNode struct {
	Identity *AgentIdentity
	PrivKey  ed25519.PrivateKey
	Memory   *LWWMap
	DLQ      *DLQ

	handlers   map[Intent]func(*TPCPEnvelope)
	handlersMu sync.RWMutex

	// peerKeys maps agent_id → base64 public key for inbound signature verification.
	peerKeys   map[string]string
	peerKeysMu sync.RWMutex

	peers   map[string]*websocket.Conn
	peersMu sync.RWMutex

	server *http.Server
	done   chan struct{}
}

// NewTPCPNode creates a TPCPNode with the given identity and optional private key.
func NewTPCPNode(identity *AgentIdentity, privKey ed25519.PrivateKey) *TPCPNode {
	return &TPCPNode{
		Identity:   identity,
		PrivKey:    privKey,
		Memory:     NewLWWMap(),
		DLQ:        NewDLQ(),
		handlers:   make(map[Intent]func(*TPCPEnvelope)),
		peerKeys:   make(map[string]string),
		peers:      make(map[string]*websocket.Conn),
		done:       make(chan struct{}),
	}
}

// RegisterHandler registers a handler function for a specific intent.
func (n *TPCPNode) RegisterHandler(intent Intent, handler func(*TPCPEnvelope)) {
	n.handlersMu.Lock()
	defer n.handlersMu.Unlock()
	n.handlers[intent] = handler
}

// RegisterPeerKey registers the public key for a known peer so inbound messages can be verified.
func (n *TPCPNode) RegisterPeerKey(agentID, pubKeyB64 string) {
	n.peerKeysMu.Lock()
	defer n.peerKeysMu.Unlock()
	n.peerKeys[agentID] = pubKeyB64
}

// Listen starts a WebSocket server on the given address (e.g. ":8765").
func (n *TPCPNode) Listen(addr string) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/", n.handleUpgrade)
	n.server = &http.Server{Addr: addr, Handler: mux}
	go func() {
		if err := n.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("[TPCPNode] server error: %v", err)
		}
	}()
	return nil
}

func (n *TPCPNode) handleUpgrade(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[TPCPNode] upgrade error: %v", err)
		return
	}
	peerID := r.RemoteAddr
	n.peersMu.Lock()
	n.peers[peerID] = conn
	n.peersMu.Unlock()
	go n.readLoop(peerID, conn)
}

// Connect establishes a WebSocket client connection to a peer URL.
func (n *TPCPNode) Connect(peerURL string) error {
	conn, _, err := websocket.DefaultDialer.Dial(peerURL, nil)
	if err != nil {
		return fmt.Errorf("connect to %s: %w", peerURL, err)
	}
	peerID := peerURL
	n.peersMu.Lock()
	n.peers[peerID] = conn
	n.peersMu.Unlock()
	go n.readLoop(peerID, conn)
	return nil
}

// SendMessage sends a message with the given intent and payload to a peer.
// payload must be JSON-serializable.
func (n *TPCPNode) SendMessage(peerID string, intent Intent, payload interface{}) error {
	n.peersMu.RLock()
	conn, ok := n.peers[peerID]
	n.peersMu.RUnlock()
	if !ok {
		return fmt.Errorf("unknown peer: %s", peerID)
	}

	rawPayload, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	envelope := &TPCPEnvelope{
		Header: MessageHeader{
			MessageID:       randomUUID(),
			Timestamp:       time.Now().UTC().Format("2006-01-02T15:04:05.000Z"),
			SenderID:        n.Identity.AgentID,
			ReceiverID:      peerID,
			Intent:          intent,
			TTL:             30,
			ProtocolVersion: PROTOCOL_VERSION,
		},
		Payload: rawPayload,
	}

	// Sign the payload with canonical JSON if we have a private key.
	if n.PrivKey != nil {
		canonical, err := CanonicalJSON(payload)
		if err == nil {
			envelope.Signature = Sign(n.PrivKey, canonical)
		}
	}

	data, err := json.Marshal(envelope)
	if err != nil {
		return fmt.Errorf("marshal envelope: %w", err)
	}
	return conn.WriteMessage(websocket.TextMessage, data)
}

// Stop shuts down the WebSocket server and closes all peer connections.
func (n *TPCPNode) Stop() error {
	close(n.done)
	n.peersMu.Lock()
	for id, conn := range n.peers {
		conn.Close()
		delete(n.peers, id)
	}
	n.peersMu.Unlock()
	if n.server != nil {
		return n.server.Close()
	}
	return nil
}

func (n *TPCPNode) readLoop(peerID string, conn *websocket.Conn) {
	defer func() {
		conn.Close()
		n.peersMu.Lock()
		delete(n.peers, peerID)
		n.peersMu.Unlock()
	}()
	for {
		select {
		case <-n.done:
			return
		default:
		}
		_, data, err := conn.ReadMessage()
		if err != nil {
			return
		}
		var env TPCPEnvelope
		if err := json.Unmarshal(data, &env); err != nil {
			log.Printf("[TPCPNode] invalid envelope from %s: %v", peerID, err)
			continue
		}

		// Verify inbound signature if a public key is registered for the sender.
		if env.Signature != "" {
			n.peerKeysMu.RLock()
			pubKey, known := n.peerKeys[env.Header.SenderID]
			n.peerKeysMu.RUnlock()
			if known {
				var payloadVal interface{}
				if err := json.Unmarshal(env.Payload, &payloadVal); err == nil {
					canonical, err := CanonicalJSON(payloadVal)
					if err == nil && !Verify(pubKey, canonical, env.Signature) {
						log.Printf("[TPCPNode] signature verification FAILED for message from %s — dropping", env.Header.SenderID)
						continue
					}
				}
			}
		}

		n.dispatch(&env)
	}
}

func (n *TPCPNode) dispatch(env *TPCPEnvelope) {
	n.handlersMu.RLock()
	handler, ok := n.handlers[env.Header.Intent]
	n.handlersMu.RUnlock()
	if !ok {
		n.DLQ.Enqueue(env)
		return
	}
	handler(env)
}
