package tpcp

import (
	"crypto/ed25519"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// defaultUpgrader is kept for non-node uses; TPCPNode uses a per-node upgrader
// built in handleUpgrade to enforce AllowedOrigins.
var defaultUpgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return false },
}

// Validatable is implemented by payload types that can self-validate.
type Validatable interface {
	Validate() error
}

// TPCPNode is a TPCP agent node that can send and receive messages over WebSocket.
type TPCPNode struct {
	Identity *AgentIdentity
	PrivKey  ed25519.PrivateKey
	Memory   *LWWMap
	DLQ      *DLQ

	// AllowedOrigins is the list of permitted WebSocket origins for browser clients.
	// If empty, all origins are rejected when an Origin header is present.
	// Non-browser clients (no Origin header) are always allowed.
	AllowedOrigins []string

	// Ready is closed by Listen() once the server is bound and ready to accept connections.
	Ready chan struct{}

	handlers   map[Intent]func(*TPCPEnvelope)
	handlersMu sync.RWMutex

	// peerKeys maps agent_id → base64 public key for inbound signature verification.
	peerKeys   map[string]string
	peerKeysMu sync.RWMutex

	peers   map[string]*websocket.Conn
	peersMu sync.RWMutex

	seenMessages   map[string]int64
	seenMessagesMu sync.Mutex

	server *http.Server
	done   chan struct{}
	wg     sync.WaitGroup
}

// NewTPCPNode creates a TPCPNode with the given identity and optional private key.
func NewTPCPNode(identity *AgentIdentity, privKey ed25519.PrivateKey) *TPCPNode {
	return &TPCPNode{
		Identity: identity,
		PrivKey:  privKey,
		Memory:   NewLWWMap(),
		DLQ:      NewDLQ(),
		Ready:    make(chan struct{}),
		handlers: make(map[Intent]func(*TPCPEnvelope)),
		peerKeys:     make(map[string]string),
		peers:        make(map[string]*websocket.Conn),
		seenMessages: make(map[string]int64),
		done:         make(chan struct{}),
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
// It binds the listener synchronously so that when Listen returns the port is
// already accepting connections. The Ready channel is closed immediately after
// the listener is bound.
func (n *TPCPNode) Listen(addr string) error {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("listen %s: %w", addr, err)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/", n.handleUpgrade)
	n.server = &http.Server{Addr: addr, Handler: mux}
	// Signal that the server is bound and ready to accept connections.
	close(n.Ready)
	n.wg.Add(1)
	go func() {
		defer n.wg.Done()
		if err := n.server.Serve(ln); err != nil && err != http.ErrServerClosed {
			log.Printf("[TPCPNode] server error: %v", err)
		}
	}()
	return nil
}

func (n *TPCPNode) handleUpgrade(w http.ResponseWriter, r *http.Request) {
	upgrader := websocket.Upgrader{
		CheckOrigin: func(req *http.Request) bool {
			origin := req.Header.Get("Origin")
			// Non-browser clients (no Origin header) are always allowed.
			if origin == "" {
				return true
			}
			// If no allowed origins are configured, deny all browser origins.
			if len(n.AllowedOrigins) == 0 {
				return false
			}
			for _, allowed := range n.AllowedOrigins {
				if origin == allowed {
					return true
				}
			}
			return false
		},
	}
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[TPCPNode] upgrade error: %v", err)
		return
	}
	peerID := r.RemoteAddr
	n.peersMu.Lock()
	n.peers[peerID] = conn
	n.peersMu.Unlock()
	n.wg.Add(1)
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
	n.wg.Add(1)
	go n.readLoop(peerID, conn)
	return nil
}

// SendMessage sends a message with the given intent and payload to a peer.
// peerID is the connection key (URL or remote address).
// receiverID is the agent_id of the target agent (used in the envelope header).
// payload must be JSON-serializable.
func (n *TPCPNode) SendMessage(peerID string, receiverID string, intent Intent, payload interface{}) error {
	if v, ok := payload.(Validatable); ok {
		if err := v.Validate(); err != nil {
			return fmt.Errorf("payload validation: %w", err)
		}
	}

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
			ReceiverID:      receiverID,
			Intent:          intent,
			TTL:             30,
			ProtocolVersion: PROTOCOL_VERSION,
		},
		Payload: rawPayload,
	}

	// Sign the payload with canonical JSON if we have a private key.
	if n.PrivKey != nil {
		canonical, err := CanonicalJSON(payload)
		if err != nil {
			return fmt.Errorf("canonical JSON for signing: %w", err)
		}
		envelope.Signature = Sign(n.PrivKey, canonical)
	}

	data, err := json.Marshal(envelope)
	if err != nil {
		return fmt.Errorf("marshal envelope: %w", err)
	}
	return conn.WriteMessage(websocket.TextMessage, data)
}

// Stop shuts down the WebSocket server and closes all peer connections.
// Connections are closed here and the peers map is replaced so that readLoop
// defers see an empty map and skip the redundant Close().
func (n *TPCPNode) Stop() error {
	close(n.done)
	// Close server FIRST so Serve() returns and the goroutine can exit.
	var serverErr error
	if n.server != nil {
		serverErr = n.server.Close()
	}
	n.peersMu.Lock()
	for _, conn := range n.peers {
		conn.Close()
	}
	n.peers = make(map[string]*websocket.Conn)
	n.peersMu.Unlock()
	n.wg.Wait()
	return serverErr
}

func (n *TPCPNode) readLoop(peerID string, conn *websocket.Conn) {
	defer n.wg.Done()
	defer func() {
		n.peersMu.Lock()
		if _, exists := n.peers[peerID]; exists {
			conn.Close()
			delete(n.peers, peerID)
		}
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

		// Replay protection: drop duplicate message IDs; clean up entries older than 300s.
		n.seenMessagesMu.Lock()
		if _, dup := n.seenMessages[env.Header.MessageID]; dup {
			n.seenMessagesMu.Unlock()
			continue
		}
		n.seenMessages[env.Header.MessageID] = time.Now().Unix()
		for id, ts := range n.seenMessages {
			if time.Now().Unix()-ts > 300 {
				delete(n.seenMessages, id)
			}
		}
		n.seenMessagesMu.Unlock()

		// Verify inbound signature if a public key is registered for the sender.
		// Fail-closed: if the message carries a signature but the sender's public key
		// is not registered, treat it as unverifiable and drop it.
		if env.Signature != "" {
			n.peerKeysMu.RLock()
			pubKey, known := n.peerKeys[env.Header.SenderID]
			n.peerKeysMu.RUnlock()
			if !known {
				log.Printf("[TPCPNode] signed message from unknown peer %s — dropping", env.Header.SenderID)
				continue
			}
			var payloadVal interface{}
			if err := json.Unmarshal(env.Payload, &payloadVal); err == nil {
				canonical, err := CanonicalJSON(payloadVal)
				if err == nil && !Verify(pubKey, canonical, env.Signature) {
					log.Printf("[TPCPNode] signature verification FAILED for message from %s — dropping", env.Header.SenderID)
					continue
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
