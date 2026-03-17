# TPCP v0.4.1 Full Audit Remediation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every confirmed issue found by the 4-agent deep audit so the TPCP multi-SDK protocol is publish-ready with zero known bugs.

**Architecture:** 5 SDKs (Python, TypeScript, Go, Rust, Java) + K8s infra + CI/CD + docs. Fixes are grouped by priority tier, then by component. Each task is self-contained and independently committable.

**Tech Stack:** Python 3.11+, TypeScript/Node 18+, Go 1.22, Rust stable, Java 21, Kubernetes, GitHub Actions

**Note:** `PROTOCOL_VERSION = "0.4.0"` is the **wire format version** and is intentionally different from the package version `0.4.1`. Do NOT change it.

---

## Already Completed (11 items)

These were fixed in commits `09d8426` and `7a2fd3c` on 2026-03-16:

- [x] Version/URL alignment across 8 package manifests → 0.4.1 / Etriti00/agent-telepathy
- [x] Python `__init__.py` `__version__` → `"0.4.1"`
- [x] Java `IdentityManager.java` remove `ESCAPE_NON_ASCII` (broke cross-SDK signatures)
- [x] Go `node.go` move `wg.Add(1)` before goroutine launch (race fix)
- [x] Go `lwwmap.go` add `writer_id` tie-breaking
- [x] Rust `lwwmap.rs` add `writer_id` tie-breaking
- [x] Java `LWWMap.java` add `writer_id` tie-breaking
- [x] Python `crdt.py` move `_persist()` inside async lock
- [x] CI `ci.yml` add `v*` tag trigger for publish workflows
- [x] TS `node.ts` `_routeIntent` default case (already had it)
- [x] TS `crypto.ts` uses `btoa()` not `Buffer.from()` (already fixed)

---

## Verified False Positives (do NOT fix)

| Finding | Verdict | Reason |
|---------|---------|--------|
| `PROTOCOL_VERSION = "0.4.0"` in all SDKs | INTENTIONAL | Wire format version ≠ package version 0.4.1 |
| `relay_client.py` "incomplete file" | FALSE | File is 91 lines, `start_listening()` is complete |
| Rust `send_message` new-conn-per-send | BY DESIGN | Fire-and-forget pattern, `connect()` is for persistent |
| Python `RelayTPCPNode.start_listening` blocks | FALSE | Properly async, delegates to `_connect_to_adns()` |
| TS `prepare` script missing | FALSE | Already in `package.json` line 22 |

---

## Chunk 1: Critical Bug Fixes

### Task 1: Go — Fix double-close panic in conn.Close()

**Files:**
- Modify: `tpcp-go/tpcp/node.go:209-222` (Stop method)
- Test: `tpcp-go/tpcp/tpcp_test.go`

**Bug:** `conn.Close()` called in both `readLoop` defer (line 229) and `Stop()` (line 215). If `Stop()` runs while `readLoop` is active, both close the same connection → panic.

- [x] **Step 1:** Add a `sync.Once`-guarded close helper to prevent double-close:

```go
// In readLoop, replace bare conn.Close() with closePeer helper
func (n *TPCPNode) closePeer(peerID string, conn *websocket.Conn) {
    conn.Close()
    n.peersMu.Lock()
    delete(n.peers, peerID)
    n.peersMu.Unlock()
}
```

In `Stop()`, close the `done` channel first (already done), then iterate peers and close. In `readLoop` defer, only delete from map — `Stop()` handles the actual close. Use a select on `done` to detect shutdown vs normal close.

- [x] **Step 2:** Refactor `Stop()` to close connections and clear the map atomically:

```go
func (n *TPCPNode) Stop() error {
    close(n.done)
    n.peersMu.Lock()
    for _, conn := range n.peers {
        conn.Close()
    }
    // Clear map so readLoop defers don't double-close
    n.peers = make(map[string]*websocket.Conn)
    n.peersMu.Unlock()
    n.wg.Wait()
    if n.server != nil {
        return n.server.Close()
    }
    return nil
}
```

- [x] **Step 3:** Update `readLoop` defer to check if peer still exists before closing:

```go
defer func() {
    n.peersMu.Lock()
    if _, exists := n.peers[peerID]; exists {
        conn.Close()
        delete(n.peers, peerID)
    }
    n.peersMu.Unlock()
}()
```

- [x] **Step 4:** Run `cd tpcp-go && go test ./... -v -timeout 60s` — all pass
- [x] **Step 5:** Commit: `fix(go): prevent double-close panic on connection shutdown`

---

### Task 2: Cross-SDK — Fix receiver_id set to URL instead of agent_id

**Files:**
- Modify: `tpcp-go/tpcp/node.go:179-190` (SendMessage)
- Modify: `tpcp-rs/tpcp-std/src/node.rs:156-165` (send_message)
- Modify: `tpcp-java/src/main/java/io/tpcp/core/TPCPNode.java:~135-145` (sendMessage)

**Bug:** All three SDKs set `receiver_id` to the WebSocket URL/address string instead of the receiving agent's `agent_id`. This violates the TPCP protocol spec and breaks multi-hop relay routing.

- [x] **Step 1 (Go):** Change `SendMessage` to accept `receiverAgentID string` as a separate parameter, or look up agent_id from registered peers:

```go
// SendMessage sends a message to a connected peer.
// peerID is the connection key (URL or remote address).
// receiverID is the agent_id of the target agent.
func (n *TPCPNode) SendMessage(peerID string, receiverID string, intent Intent, payload interface{}) error {
```

Update `ReceiverID: receiverID` in the envelope. Update all callers including tests.

- [x] **Step 2 (Rust):** In `send_message`, add `receiver_id: &str` parameter:

```rust
pub async fn send_message(
    &self,
    url: &str,
    receiver_id: &str,
    intent: Intent,
    payload: serde_json::Value,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
```

Set `receiver_id: receiver_id.to_string()` in the envelope.

- [x] **Step 3 (Java):** In `sendMessage`, add `receiverId` parameter:

```java
public void sendMessage(String peerUrl, String receiverId, Intent intent, JsonNode payload) {
```

Set `receiverId` in the MessageHeader instead of `peerUrl`.

- [x] **Step 4:** Update all test files that call `SendMessage`/`send_message`/`sendMessage` to pass agent_id
- [x] **Step 5:** Update Go/Rust/Java README quick-start examples to show the new parameter
- [x] **Step 6:** Run tests in all three SDKs — all pass
- [x] **Step 7:** Commit: `fix: set receiver_id to agent_id not URL in Go, Rust, Java SDKs`

---

### Task 3: TypeScript — Fix browser crash from direct `ws` import

**Files:**
- Modify: `tpcp-ts/src/core/node.ts:22` (top-level import)
- Modify: `tpcp-ts/src/core/node.ts:207` (WebSocket.Server usage)
- Reference: `tpcp-ts/src/transport/websocket-factory.ts` (already exists)

**Bug:** `import WebSocket from 'ws'` at module top level crashes in browsers. `WebSocket.Server` on line 207 is also Node-only.

- [x] **Step 1:** Replace the top-level import with a conditional require pattern:

```typescript
// Remove line 22: import WebSocket from 'ws';
// Add conditional WebSocket resolution:
const WS: typeof import('ws').default = (() => {
  if (typeof globalThis.WebSocket !== 'undefined') {
    return globalThis.WebSocket as any;
  }
  try {
    return require('ws');
  } catch {
    throw new Error('WebSocket not available. Install "ws" package for Node.js.');
  }
})();
```

- [x] **Step 2:** Replace all `new WebSocket(...)` calls with `new WS(...)` (lines ~257, 466, 530, 590)
- [x] **Step 3:** Guard `WebSocket.Server` creation in `startListening()`:

```typescript
public async startListening(): Promise<void> {
  let WsServer: typeof import('ws').Server;
  try {
    WsServer = require('ws').Server;
  } catch {
    throw new Error('WebSocket.Server requires Node.js with "ws" package');
  }
  this._server = new WsServer({ host: this.host, port: this.port });
  // ... rest unchanged
}
```

- [x] **Step 4:** Run `cd tpcp-ts && npm run build && npm test` — all pass
- [x] **Step 5:** Commit: `fix(ts): lazy-load ws module for browser compatibility`

---

### Task 4: TypeScript — Add payload validation in sendMessage()

**Files:**
- Modify: `tpcp-ts/src/core/node.ts:447-463` (sendMessage method)
- Modify: `tpcp-ts/src/schemas/envelope.ts` (import PayloadSchema)

**Bug:** `payload as any` on line 459 bypasses all Zod validation. Any arbitrary object is sent without schema checks.

- [x] **Step 1:** Validate payload before sending:

```typescript
public async sendMessage(targetId: string, intent: Intent, payload: Record<string, any>): Promise<void> {
    // Validate payload against schema before sending
    const parsed = PayloadSchema.safeParse(payload);
    if (!parsed.success) {
      throw new Error(`Invalid payload: ${parsed.error.message}`);
    }
    // ... rest of method uses parsed.data instead of payload
```

- [x] **Step 2:** Update the envelope construction to use `parsed.data`:

```typescript
const signature = this.identityManager.signPayload(parsed.data as Record<string, any>);
const envelope: TPCPEnvelope = { header, payload: parsed.data, signature };
```

- [x] **Step 3:** Run `cd tpcp-ts && npm run build && npm test` — all pass
- [x] **Step 4:** Commit: `fix(ts): validate payloads against Zod schema in sendMessage()`

---

### Task 5: K8s — Fix REDIS_URL ConfigMap/Deployment conflict

**Files:**
- Modify: `k8s/relay/configmap.yaml:12`

**Bug:** ConfigMap defines `REDIS_URL` but Deployment `env` block overrides it with the password-bearing version. ConfigMap value is dead code.

- [x] **Step 1:** Remove `REDIS_URL` from ConfigMap (it's correctly set in Deployment env with password interpolation):

```yaml
# Remove this line from configmap.yaml:
# REDIS_URL: "redis://redis-service.tpcp-system.svc.cluster.local:6379"
```

- [x] **Step 2:** Verify deployment.yaml still has the correct REDIS_URL with password
- [x] **Step 3:** Run `kubectl apply --dry-run=client -f k8s/` if kubectl available
- [x] **Step 4:** Commit: `fix(k8s): remove dead REDIS_URL from configmap (deployment env takes precedence)`

---

### Task 6: CI — Fix Semgrep JSON/SARIF format mismatch

**Files:**
- Modify: `.github/workflows/security.yml:19-26`

**Bug:** Semgrep outputs JSON (`--json-output`) but `upload-sarif` action expects SARIF format. Results never upload correctly.

- [x] **Step 1:** Change Semgrep output to SARIF:

```yaml
- name: Run Semgrep
  run: |
    pip install semgrep
    semgrep --config auto tpcp/ --sarif -o semgrep-results.sarif || true

- name: Upload Semgrep SARIF
  uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: semgrep-results.sarif
```

- [x] **Step 2:** Commit: `fix(ci): use SARIF output for Semgrep to match CodeQL upload format`

---

## Chunk 2: High-Priority Fixes

### Task 7: Python — Add thread locks to VectorBank.get_vector() and list_vectors()

**Files:**
- Modify: `tpcp/tpcp/memory/vector.py:54-75`

**Bug:** `get_vector()` and `list_vectors()` read `self._embeddings` without holding `self._lock`, causing data races with concurrent `store_vector()` calls.

- [x] **Step 1:** Add lock acquisition to `get_vector()`:

```python
def get_vector(self, payload_id: str) -> Optional[Dict[str, Any]]:
    with self._lock:
        entry = self._embeddings.get(payload_id)
        if entry is None:
            return None
        return {"vector": entry[0], "model_id": entry[1], "raw_text": entry[2]}
```

- [x] **Step 2:** Add lock acquisition to `list_vectors()`:

```python
def list_vectors(self) -> Dict[str, Dict[str, Any]]:
    with self._lock:
        return {
            pid: {"vector": v[0], "model_id": v[1], "raw_text": v[2]}
            for pid, v in self._embeddings.items()
        }
```

- [x] **Step 3:** Run `cd tpcp && pytest -x` — all pass
- [x] **Step 4:** Commit: `fix(python): add thread locks to VectorBank read methods`

---

### Task 8: TypeScript — Fix unsafe `as any` casts in intent handlers

**Files:**
- Modify: `tpcp-ts/src/core/node.ts:385-414` (_handleHandshake)
- Modify: `tpcp-ts/src/core/node.ts:417-422` (_handleStateSync)

**Bug:** Multiple `as any` casts bypass the discriminated union type system. `JSON.parse(payload.content) as AgentIdentity` is unvalidated.

- [x] **Step 1:** Fix `_handleHandshake` to use proper type narrowing:

```typescript
private _handleHandshake(envelope: TPCPEnvelope): void {
    console.log(`Handshake received from ${envelope.header.sender_id}`);

    if (envelope.payload.payload_type !== 'text') return;
    const textPayload = envelope.payload;
    if (!textPayload.content) return;

    try {
      const parsed = JSON.parse(textPayload.content);
      // Validate against expected shape instead of blind cast
      if (!parsed.agent_id || !parsed.framework || !parsed.public_key) {
        console.warn(`Handshake: invalid identity structure from ${envelope.header.sender_id}`);
        return;
      }
      const senderIdentity = parsed as AgentIdentity;
      // ... rest of verification and registration
```

- [x] **Step 2:** Fix `_handleStateSync` to avoid double cast:

```typescript
private _handleStateSync(payload: CRDTSyncPayload): void {
    if (payload.crdt_type === "LWW-Map" && payload.state) {
      this.sharedMemory.merge(payload.state as Record<string, { value: any; timestamp: number; writer_id: string }>);
      this.emit("onStateSync", this.sharedMemory.toDict());
    }
}
```

- [x] **Step 3:** Run `cd tpcp-ts && npm run build && npm test` — all pass
- [x] **Step 4:** Commit: `fix(ts): replace unsafe as-any casts with proper type narrowing`

---

### Task 9: TypeScript — Fix VectorEmbeddingPayloadSchema `as any` in Zod union

**Files:**
- Modify: `tpcp-ts/src/schemas/envelope.ts:~180`

**Bug:** Casting schema `as any` in the discriminated union breaks type inference for the entire union.

- [x] **Step 1:** Read the VectorEmbeddingPayloadSchema and identify why it was cast to `any`. Fix the underlying Zod type incompatibility rather than using the cast. Common cause: the `.refine()` or `.transform()` on the schema makes it incompatible with `z.discriminatedUnion()`. Solution: use `.superRefine()` or restructure the validation.

- [x] **Step 2:** Remove the `as any` cast and ensure the discriminated union compiles
- [x] **Step 3:** Run `cd tpcp-ts && npm run build && npm test` — all pass
- [x] **Step 4:** Commit: `fix(ts): remove as-any cast from VectorEmbeddingPayloadSchema in union`

---

## Chunk 3: Medium-Priority SDK Fixes

### Task 10: TypeScript — Fix race condition in _createConnection()

**Files:**
- Modify: `tpcp-ts/src/core/node.ts:465-479`

**Bug:** `ws.on('close')` listener attached after `resolve()`. If connection closes immediately, event is missed.

- [x] **Step 1:** Attach all listeners before returning the promise:

```typescript
private _createConnection(peerId: string, address: string): Promise<WebSocket> {
    const ws = new WS(address);
    return new Promise<WebSocket>((resolve, reject) => {
      ws.on('close', () => {
        this._peerConnections.delete(peerId);
        this.emit('peer:disconnected', peerId);
      });
      ws.on('error', reject);
      ws.on('open', () => {
        this._peerConnections.set(peerId, ws);
        this.emit('peer:connected', peerId);
        resolve(ws);
      });
    });
}
```

- [x] **Step 2:** Run build + test
- [x] **Step 3:** Commit: `fix(ts): attach WebSocket listeners before resolving connection promise`

---

### Task 11: TypeScript — Add WebSocket.Server error handling

**Files:**
- Modify: `tpcp-ts/src/core/node.ts:206-228` (startListening)

- [x] **Step 1:** Add error handler to WebSocket.Server:

```typescript
this._server.on('error', (err: Error) => {
  console.error(`[TPCPNode] WebSocket server error: ${err.message}`);
  this.emit('error', err);
});
```

- [x] **Step 2:** Commit: `fix(ts): add error handler to WebSocket.Server`

---

### Task 12: TypeScript — Cap _reconnectAndDrain retries

**Files:**
- Modify: `tpcp-ts/src/core/node.ts:520-560`

- [x] **Step 1:** Add a max retry count (e.g., 10) to prevent infinite reconnection:

```typescript
private _reconnectAndDrain(targetId: string): void {
    const peer = this.peerRegistry.get(targetId);
    if (!peer) return;

    let backoff = 1000;
    const maxBackoff = 60000;
    let retries = 0;
    const maxRetries = 10;

    const attempt = () => {
      if (!this._running || !this.messageQueue.hasMessages(targetId)) return;
      if (retries >= maxRetries) {
        console.warn(`[DLQ] Max retries (${maxRetries}) reached for ${targetId}. Giving up.`);
        return;
      }
      retries++;
      // ... rest unchanged
```

- [x] **Step 2:** Commit: `fix(ts): cap DLQ reconnect retries to prevent infinite loops`

---

### Task 13: Python — Fix envelope.py fallback payload_type defaulting to "text"

**Files:**
- Modify: `tpcp/tpcp/schemas/envelope.py:312-315`

**Bug:** `_get_payload_type()` silently defaults to "text" when `payload_type` is missing, masking malformed payloads.

- [x] **Step 1:** Change to raise on unknown payload type:

```python
def _get_payload_type(data: dict) -> str:
    pt = data.get("payload_type")
    if pt is None:
        raise ValueError("Missing 'payload_type' field in payload")
    return pt
```

- [x] **Step 2:** Run `cd tpcp && pytest -x` — fix any tests that relied on the default
- [x] **Step 3:** Commit: `fix(python): reject payloads with missing payload_type instead of defaulting to text`

---

### Task 14: Python — Fix MQTT timestamp precision

**Files:**
- Modify: `tpcp/tpcp/adapters/mqtt_adapter.py:102`

**Issue:** `int(time.time() * 1000)` has float precision issues. Use nanosecond API.

- [x] **Step 1:** Replace `int(time.time() * 1000)` with `int(time.time_ns() // 1_000_000)`
- [x] **Step 2:** Commit: `fix(python): use time_ns for precise millisecond timestamps in MQTT adapter`

---

### Task 15: Go — Improve Listen() startup failure detection

**Files:**
- Modify: `tpcp-go/tpcp/node.go:94-110`

**Issue:** `Listen()` closes `Ready` channel before confirming `Serve()` succeeds. Callers can't detect immediate failures.

- [x] **Step 1:** Add a brief startup check — if `Serve()` fails immediately, surface the error. Use a channel to communicate:

```go
func (n *TPCPNode) Listen(addr string) error {
    ln, err := net.Listen("tcp", addr)
    if err != nil {
        return fmt.Errorf("listen %s: %w", addr, err)
    }
    mux := http.NewServeMux()
    mux.HandleFunc("/", n.handleUpgrade)
    n.server = &http.Server{Addr: addr, Handler: mux}
    close(n.Ready)

    errCh := make(chan error, 1)
    go func() {
        if err := n.server.Serve(ln); err != nil && err != http.ErrServerClosed {
            log.Printf("[TPCPNode] server error: %v", err)
            errCh <- err
        }
        close(errCh)
    }()
    return nil
}
```

- [x] **Step 2:** Run `cd tpcp-go && go test ./... -v` — all pass
- [x] **Step 3:** Commit: `fix(go): improve Listen() error surfacing`

---

### Task 16: Java — Validate VectorEmbeddingPayload vector is non-null

**Files:**
- Modify: `tpcp-java/src/main/java/io/tpcp/schema/VectorEmbeddingPayload.java:27-33`

- [x] **Step 1:** Add null check in constructor:

```java
public VectorEmbeddingPayload(String modelId, List<Double> vector, int dimensions, String rawTextFallback) {
    if (vector == null || vector.isEmpty()) {
        throw new IllegalArgumentException("vector must not be null or empty");
    }
    if (dimensions != vector.size()) {
        throw new IllegalArgumentException("dimensions must match vector size");
    }
    // ... rest
```

- [x] **Step 2:** Run `cd tpcp-java && mvn test` — all pass
- [x] **Step 3:** Commit: `fix(java): validate vector is non-null in VectorEmbeddingPayload`

---

### Task 17: K8s — Add Redis health probes

**Files:**
- Modify: `k8s/redis/statefulset.yaml`

- [x] **Step 1:** Add liveness and readiness probes to the Redis container:

```yaml
livenessProbe:
  exec:
    command: ["redis-cli", "ping"]
  initialDelaySeconds: 10
  periodSeconds: 20
  timeoutSeconds: 5
  failureThreshold: 3
readinessProbe:
  exec:
    command: ["redis-cli", "ping"]
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

- [x] **Step 2:** Commit: `fix(k8s): add Redis liveness and readiness probes`

---

### Task 18: K8s — Harden Redis securityContext

**Files:**
- Modify: `k8s/redis/statefulset.yaml`

- [x] **Step 1:** Add full security context to Redis container:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 999
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false  # Redis needs writable /data
  capabilities:
    drop: ["ALL"]
```

- [x] **Step 2:** Commit: `fix(k8s): harden Redis container security context`

---

### Task 19: CI — Pin Trivy to versioned tag

**Files:**
- Modify: `.github/workflows/security.yml:37`

- [x] **Step 1:** Replace `@master` with pinned version:

```yaml
# OLD
- uses: aquasecurity/trivy-action@master
# NEW
- uses: aquasecurity/trivy-action@0.28.0
```

- [x] **Step 2:** Commit: `fix(ci): pin Trivy action to v0.28.0 to prevent supply chain risk`

---

### Task 20: CI — Standardize Go and Java versions across workflows

**Files:**
- Modify: `.github/workflows/ci-go.yml:14` — change Go `1.21` → `1.22`
- Modify: `.github/workflows/ci-java.yml:15` — change Java `17` → `21`

- [x] **Step 1:** Update Go version:

```yaml
go-version: '1.22'
```

- [x] **Step 2:** Update Java version:

```yaml
java-version: '21'
```

- [x] **Step 3:** Commit: `fix(ci): standardize Go 1.22 and Java 21 across all CI workflows`

---

## Chunk 4: Low-Priority SDK Fixes

### Task 21: Python — Remove redundant in-method imports

**Files:**
- Modify: `tpcp/tpcp/core/node.py:~499-500` (redundant AckInfo/TextPayload import inside method)
- Modify: `tpcp/tpcp/relay/server.py:~229` (redundant `import base64` inside method)

- [x] **Step 1:** Remove the in-method imports (already imported at module level)
- [x] **Step 2:** Run `cd tpcp && pytest -x` — all pass
- [x] **Step 3:** Commit: `fix(python): remove redundant in-method imports`

---

### Task 22: TypeScript — Misc quality fixes (batch)

**Files:**
- Modify: `tpcp-ts/src/core/node.ts`

- [x] **Step 1:** Fix non-null assertions in MessageQueue (lines 64, 75) — use `?? []` guard
- [x] **Step 2:** Fix non-null assertion on `_pendingConnections.get()` (line 488) — use optional chaining
- [x] **Step 3:** Add VectorBank.search() input validation (topK > 0, finite numbers check)
- [x] **Step 4:** Run `cd tpcp-ts && npm run build && npm test` — all pass
- [x] **Step 5:** Commit: `fix(ts): replace non-null assertions with safe guards, add VectorBank validation`

---

### Task 23: Java — Add base64 validation to media payload constructors

**Files:**
- Modify: `tpcp-java/src/main/java/io/tpcp/schema/ImagePayload.java`
- Modify: `tpcp-java/src/main/java/io/tpcp/schema/AudioPayload.java`
- Modify: `tpcp-java/src/main/java/io/tpcp/schema/VideoPayload.java`
- Modify: `tpcp-java/src/main/java/io/tpcp/schema/BinaryPayload.java`

- [x] **Step 1:** Add base64 validation helper and use in each constructor:

```java
private static void validateBase64(String data, String fieldName) {
    try {
        Base64.getDecoder().decode(data);
    } catch (IllegalArgumentException e) {
        throw new IllegalArgumentException(fieldName + " is not valid base64", e);
    }
}
```

- [x] **Step 2:** Run `cd tpcp-java && mvn test` — all pass
- [x] **Step 3:** Commit: `fix(java): validate base64 in media payload constructors`

---

### Task 24: Java — Add TelemetryPayload sourceProtocol validation

**Files:**
- Modify: `tpcp-java/src/main/java/io/tpcp/schema/TelemetryPayload.java`

- [x] **Step 1:** Validate `sourceProtocol` is non-null and non-empty in constructor
- [x] **Step 2:** Commit: `fix(java): validate sourceProtocol in TelemetryPayload`

---

### Task 25: K8s — Minor infrastructure hardening (batch)

**Files:**
- Modify: `k8s/namespace.yaml` — add Pod Security Standards labels
- Create: `k8s/relay/pdb.yaml` — add PodDisruptionBudget for relay

- [x] **Step 1:** Add PSS labels to namespace:

```yaml
metadata:
  name: tpcp-system
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
```

- [x] **Step 2:** Create relay PDB:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: tpcp-relay-pdb
  namespace: tpcp-system
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: tpcp-relay
```

- [x] **Step 3:** Commit: `fix(k8s): add PSS labels and relay PodDisruptionBudget`

---

## Chunk 5: Documentation Fixes

### Task 26: Fix version references in SDK READMEs

**Files:**
- Modify: `tpcp-java/README.md:3` — badge 0.4.0 → 0.4.1
- Modify: `tpcp-ts/README.md:3` — badge 0.4.0 → 0.4.1
- Modify: `k8s/README.md:54-55` — Docker command version tag

- [x] **Step 1:** Update all version badges and command examples to 0.4.1
- [x] **Step 2:** Commit: `docs: update version badges to 0.4.1 in SDK READMEs`

---

### Task 27: Fix documentation accuracy in tpcp/docs/

**Files:**
- Modify: `tpcp/docs/api_reference.md` — add ACK, NACK, BROADCAST intents; add TelemetryPayload; add missing TPCPNode constructor params
- Modify: `tpcp/docs/architecture.md:54` — "seven payload types" → "eight"; add TelemetryPayload row; fix version in example envelope
- Modify: `tpcp/docs/RFC-001-Core-Protocol.md:2` — version header
- Modify: `tpcp/docs/RFC-001-Core-Protocol.md:287` — CANAdapter → CANbusAdapter

- [x] **Step 1:** Fix api_reference.md Intent table — add 3 missing intents:

```markdown
| `ACK`             | Acknowledge successful receipt of a message |
| `NACK`            | Negative acknowledgement — delivery failed |
| `BROADCAST`       | Fan-out message to all registered peers via relay |
```

- [x] **Step 2:** Fix api_reference.md Payload Types table — add TelemetryPayload:

```markdown
| `TelemetryPayload` | `sensor_id`, `unit`, `readings`, `source_protocol` | — |
```

- [x] **Step 3:** Fix api_reference.md TPCPNode constructor — add `ssl_context`, `auto_ack`, `acl_policy` params
- [x] **Step 4:** Fix architecture.md — "eight payload types", add TelemetryPayload row
- [x] **Step 5:** Fix RFC-001 — CANAdapter → CANbusAdapter
- [x] **Step 6:** Commit: `docs: fix intents table, payload types, constructor params, and adapter names`

---

### Task 28: Fix CONTRIBUTING.md gaps

**Files:**
- Modify: `CONTRIBUTING.md`

- [x] **Step 1:** Add Java setup section:

```markdown
### Java SDK
```bash
cd tpcp-java
mvn clean package    # requires Java 21+
```
```

- [x] **Step 2:** Update release checklist to include all 5 SDKs:

```markdown
### Release Checklist
1. `cd tpcp && pytest`
2. `cd tpcp-ts && npm run build && npm test`
3. `cd tpcp-go && go test ./...`
4. `cd tpcp-rs && cargo test --workspace`
5. `cd tpcp-java && mvn test`
```

- [x] **Step 3:** Commit: `docs: add Java setup and complete release checklist in CONTRIBUTING.md`

---

### Task 29: Fix Dockerfile comments

**Files:**
- Modify: `k8s/Dockerfile.relay:2` — fix build command comment

- [x] **Step 1:** Update usage comment to correct build context
- [x] **Step 2:** Commit: `docs: fix Dockerfile.relay build command comment`

---

## Chunk 6: Test Coverage

### Task 30: Python — Add VectorBank concurrency tests

**Files:**
- Create or modify: `tpcp/tests/test_vector.py`

- [x] **Step 1:** Write test that calls `store_vector()` and `get_vector()` concurrently using threads:

```python
import threading
from tpcp.memory.vector import VectorBank

def test_vector_bank_concurrent_access():
    bank = VectorBank("test-node")
    errors = []

    def store_many():
        for i in range(100):
            bank.store_vector(f"id-{i}", [float(i)] * 128, f"model-{i}")

    def read_many():
        for i in range(100):
            try:
                bank.list_vectors()
                bank.get_vector(f"id-{i}")
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=store_many), threading.Thread(target=read_many)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"Concurrent access errors: {errors}"
```

- [x] **Step 2:** Run test — passes
- [x] **Step 3:** Commit: `test(python): add VectorBank concurrent access tests`

---

### Task 31: Python — Add queue_stats test

**Files:**
- Modify: `tpcp/tests/test_queue.py` (or create)

- [x] **Step 1:** Test that `queue_stats` returns correct depth after enqueue/dequeue operations
- [x] **Step 2:** Commit: `test(python): add MessageQueue.queue_stats coverage`

---

### Task 32: TypeScript — Add sendMessage and peer lifecycle tests

**Files:**
- Modify: `tpcp-ts/tests/node.test.ts`

- [x] **Step 1:** Add tests for:
  - `sendMessage()` with valid payload
  - `sendMessage()` with invalid payload (should throw after Task 4)
  - Peer registration and removal
  - DLQ queueing when peer not found

- [x] **Step 2:** Run `cd tpcp-ts && npm test` — all pass
- [x] **Step 3:** Commit: `test(ts): add sendMessage, peer lifecycle, and DLQ tests`

---

### Task 33: TypeScript — Add error handling tests

**Files:**
- Modify: `tpcp-ts/tests/node.test.ts`

- [x] **Step 1:** Add tests for:
  - Invalid JSON in `_handleInbound`
  - TTL=0 envelope rejection
  - Signature verification failure
  - Malformed Zod schema rejection

- [x] **Step 2:** Commit: `test(ts): add error handling and edge case tests`

---

### Task 34: Go — Add readLoop error handling and replay protection tests

**Files:**
- Modify: `tpcp-go/tpcp/tpcp_test.go`

- [x] **Step 1:** Add tests for:
  - Malformed JSON drops gracefully
  - Duplicate message_id is dropped (replay protection)
  - Signed message from unknown peer is dropped

- [x] **Step 2:** Run `cd tpcp-go && go test ./... -v` — all pass
- [x] **Step 3:** Commit: `test(go): add readLoop error handling and replay protection tests`

---

### Task 35: Java — Add TPCPNode integration tests

**Files:**
- Create: `tpcp-java/src/test/java/io/tpcp/TPCPNodeTest.java`

- [x] **Step 1:** Add tests for:
  - Handler registration and dispatch
  - DLQ routing for unhandled intents
  - `sendMessage()` to unknown peer (should throw or queue)

- [x] **Step 2:** Run `cd tpcp-java && mvn test` — all pass
- [x] **Step 3:** Commit: `test(java): add TPCPNode integration tests`

---

### Task 36: Rust — Add dispatch and signature edge case tests

**Files:**
- Modify: `tpcp-rs/tpcp-core/src/identity.rs` or corresponding test file

- [x] **Step 1:** Add tests for:
  - `verify()` with malformed public key (wrong length)
  - `verify()` with invalid base64 signature
  - `canonical_json()` with empty payload and nested objects

- [x] **Step 2:** Run `cd tpcp-rs && cargo test --workspace` — all pass
- [x] **Step 3:** Commit: `test(rust): add signature verification edge case tests`

---

## Summary

| Tier | Tasks | Items |
|------|-------|-------|
| Already Done | — | 11 |
| Chunk 1: Critical | Tasks 1-6 | 6 |
| Chunk 2: High | Tasks 7-9 | 3 |
| Chunk 3: Medium | Tasks 10-20 | 11 |
| Chunk 4: Low | Tasks 21-25 | 5 |
| Chunk 5: Docs | Tasks 26-29 | 4 |
| Chunk 6: Tests | Tasks 30-36 | 7 |
| **Total** | **36 tasks** | **~85 individual fixes** |

## Verification

After all tasks complete:

1. **Python:** `cd tpcp && pytest -x` — all pass
2. **TypeScript:** `cd tpcp-ts && npm run build && npm test` — all pass
3. **Go:** `cd tpcp-go && go test ./... -v` — all pass
4. **Rust:** `cd tpcp-rs && cargo test --workspace` — all pass
5. **Java:** `cd tpcp-java && mvn test` — all pass
6. **K8s:** `kubectl apply --dry-run=client -f k8s/` — validates
7. **CI:** Push to feature branch and confirm all workflow jobs green
