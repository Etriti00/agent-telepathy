/*
 * Copyright (c) 2026 Principal Systems Architect
 * This file is part of TPCP.
 * 
 * TPCP is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * TPCP is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 * 
 * You should have received a copy of the GNU Affero General Public License
 * along with TPCP. If not, see <https://www.gnu.org/licenses/>.
 * 
 * For commercial licensing inquiries, see COMMERCIAL_LICENSE.md
 */

import { EventEmitter } from 'events';
import WebSocket from 'ws';

import { 
  AgentIdentity, 
  TPCPEnvelope, 
  Intent, 
  MessageHeader, 
  TPCPEnvelopeSchema, 
  CRDTSyncPayload,
  VectorEmbeddingPayload,
  PROTOCOL_VERSION
} from '../schemas/envelope';
import { LWWMap } from '../memory/crdt';
import { AgentIdentityManager } from '../security/crypto';


// ── MESSAGE QUEUE (DLQ) ──────────────────────────────────────────────
interface QueuedEnvelope {
  data: string;
  messageId: string;
}

class MessageQueue {
  private _dlq: Map<string, QueuedEnvelope[]> = new Map();
  private _maxSize: number;

  constructor(maxSize: number = 500) {
    this._maxSize = maxSize;
  }

  enqueue(targetId: string, serialized: string, messageId: string): void {
    if (!this._dlq.has(targetId)) {
      this._dlq.set(targetId, []);
    }
    const q = this._dlq.get(targetId)!;
    if (q.length >= this._maxSize) {
      q.shift(); // Evict oldest
    }
    q.push({ data: serialized, messageId });
  }

  enqueueFront(targetId: string, serialized: string, messageId: string): void {
    if (!this._dlq.has(targetId)) {
      this._dlq.set(targetId, []);
    }
    this._dlq.get(targetId)!.unshift({ data: serialized, messageId });
  }

  dequeueOne(targetId: string): QueuedEnvelope | null {
    const q = this._dlq.get(targetId);
    if (!q || q.length === 0) return null;
    const msg = q.shift()!;
    if (q.length === 0) this._dlq.delete(targetId);
    return msg;
  }

  hasMessages(targetId: string): boolean {
    const q = this._dlq.get(targetId);
    return q !== undefined && q.length > 0;
  }
}
// ─────────────────────────────────────────────────────────────────────


// ── VECTOR BANK ─────────────────────────────────────────────────────
interface VectorEntry {
  vector: number[];
  norm: number;
  modelId: string;
  rawText?: string;
}

class VectorBank {
  private _embeddings: Map<string, VectorEntry> = new Map();
  public readonly nodeId: string;

  constructor(nodeId: string) {
    this.nodeId = nodeId;
  }

  store(payloadId: string, vector: number[], modelId: string, rawText?: string): void {
    const norm = Math.sqrt(vector.reduce((sum, x) => sum + x * x, 0));
    this._embeddings.set(payloadId, { vector, norm, modelId, rawText });
  }

  get(payloadId: string): VectorEntry | undefined {
    return this._embeddings.get(payloadId);
  }

  search(queryVector: number[], topK: number = 5): { payloadId: string; similarity: number; rawText?: string }[] {
    const queryNorm = Math.sqrt(queryVector.reduce((sum, x) => sum + x * x, 0));
    if (queryNorm === 0) return [];

    const results: { payloadId: string; similarity: number; rawText?: string }[] = [];

    for (const [pid, entry] of this._embeddings) {
      if (entry.norm === 0) continue;
      if (entry.vector.length !== queryVector.length) {
        throw new Error(`Dimension mismatch: query is ${queryVector.length}d, stored vector '${pid}' is ${entry.vector.length}d.`);
      }
      const dot = queryVector.reduce((sum, a, i) => sum + a * entry.vector[i], 0);
      const similarity = dot / (queryNorm * entry.norm);
      results.push({ payloadId: pid, similarity, rawText: entry.rawText });
    }

    results.sort((a, b) => b.similarity - a.similarity);
    return results.slice(0, topK);
  }

  get totalVectors(): number {
    return this._embeddings.size;
  }
}
// ─────────────────────────────────────────────────────────────────────


export class TPCPNode extends EventEmitter {
  public identity: AgentIdentity;
  public host: string;
  public port: number;
  public adnsUrl?: string;

  public peerRegistry: Map<string, { identity: AgentIdentity; address: string }> = new Map();
  public sharedMemory: LWWMap;
  public vectorBank: VectorBank;
  public identityManager: AgentIdentityManager;
  public messageQueue: MessageQueue;

  private _server?: WebSocket.Server;
  private _adnsWs?: WebSocket;
  private _adnsRegistered: boolean = false;
  protected _running: boolean = false;
  private _peerConnections: Map<string, WebSocket> = new Map();

  constructor(identity: AgentIdentity, host: string = "127.0.0.1", port: number = 8000, adnsUrl?: string) {
    super();
    this.identity = identity;
    this.host = host;
    this.port = port;
    this.adnsUrl = adnsUrl;

    this.identityManager = new AgentIdentityManager();
    this.identity.public_key = this.identityManager.getPublicKeyString();

    this.sharedMemory = new LWWMap(this.identity.agent_id);
    this.vectorBank = new VectorBank(this.identity.agent_id);
    this.messageQueue = new MessageQueue(500);
  }

  public registerPeer(identity: AgentIdentity, address: string): void {
    this.peerRegistry.set(identity.agent_id, { identity, address });
  }

  public removePeer(agentId: string): void {
    this.peerRegistry.delete(agentId);
    const ws = this._peerConnections.get(agentId);
    if (ws) {
      ws.close();
      this._peerConnections.delete(agentId);
    }
  }

  public async startListening(): Promise<void> {
    this._server = new WebSocket.Server({ host: this.host, port: this.port });
    this._running = true;
    
    this._server.on("connection", (ws: WebSocket) => {
      ws.on("message", async (data: WebSocket.RawData) => {
        await this._handleInbound(data.toString());
      });
    });

    console.log(`Node ${this.identity.agent_id} listening on ws://${this.host}:${this.port} (v${PROTOCOL_VERSION})`);

    if (this.adnsUrl) {
      this._connectToADNS();
    }
  }

  public async stopListening(): Promise<void> {
    this._running = false;
    
    for (const [_, ws] of this._peerConnections) {
      try { ws.close(); } catch (e) {}
    }
    this._peerConnections.clear();

    if (this._adnsWs) {
      try { this._adnsWs.close(); } catch (e) {}
    }

    if (this._server) {
      this._server.close();
    }
  }

  protected _connectToADNS(): void {
    if (!this.adnsUrl || !this._running) return;

    let backoff = 1000;
    const maxBackoff = 60000;

    const connect = () => {
      if (!this._running) return;

      const ws = new WebSocket(this.adnsUrl!);
      this._adnsWs = ws;
      this._adnsRegistered = false;

      ws.on("open", async () => {
        console.log(`Connected to A-DNS Relay at ${this.adnsUrl}`);
        backoff = 1000;
        await this.broadcastDiscovery();
      });

      ws.on("message", async (data: WebSocket.RawData) => {
        const raw = data.toString();
        try {
          const parsed = JSON.parse(raw);

          // Handle ADNS challenge
          if (parsed.type === "ADNS_CHALLENGE") {
            const nonce = parsed.nonce || "";
            const nonceBytes = new TextEncoder().encode(nonce);
            const signedNonce = this.identityManager.signBytes(nonceBytes);
            
            const response = JSON.stringify({
              header: {
                sender_id: this.identity.agent_id,
                intent: "Challenge_Response"
              },
              payload: { content: signedNonce }
            });
            ws.send(response);
            console.log("Sent signed challenge response to A-DNS.");
            return;
          }

          // Handle registration confirmation
          if (parsed.type === "ADNS_REGISTERED") {
            this._adnsRegistered = true;
            console.log("✓ Verified and registered with A-DNS relay.");
            return;
          }

          // Standard TPCP message
          await this._handleInbound(raw);
        } catch (e) {
          console.error("Error processing A-DNS message:", e);
        }
      });

      ws.on("close", () => {
        this._adnsWs = undefined;
        this._adnsRegistered = false;
        if (this._running) {
          console.log(`A-DNS connection lost. Retrying in ${backoff / 1000}s...`);
          setTimeout(connect, backoff);
          backoff = Math.min(backoff * 2, maxBackoff);
        }
      });

      ws.on("error", (err) => {
        console.error(`A-DNS error: ${err.message}`);
      });
    };

    connect();
  }

  private async _handleInbound(rawMessage: string): Promise<void> {
    try {
      const parsed = JSON.parse(rawMessage);
      const envelope = TPCPEnvelopeSchema.parse(parsed);

      // TTL enforcement
      if (envelope.header.ttl <= 0) {
        console.warn(`TTL expired for packet from ${envelope.header.sender_id}. Dropping.`);
        return;
      }

      // Security middleware
      if (envelope.header.intent !== Intent.HANDSHAKE) {
        if (!envelope.signature) {
          console.warn(`Dropping unsigned packet from ${envelope.header.sender_id}`);
          return;
        }

        const peer = this.peerRegistry.get(envelope.header.sender_id);
        if (!peer) {
          console.warn(`Unregistered peer ${envelope.header.sender_id}. Dropping.`);
          return;
        }

        if (!AgentIdentityManager.verifySignature(peer.identity.public_key, envelope.signature, envelope.payload)) {
          console.warn(`Invalid signature from ${envelope.header.sender_id}. Dropping.`);
          return;
        }
      }

      await this._routeIntent(envelope);
    } catch (e) {
      console.error(`Failed to process inbound message:`, e);
    }
  }

  private async _routeIntent(envelope: TPCPEnvelope): Promise<void> {
    switch (envelope.header.intent) {
      case Intent.HANDSHAKE:
        this._handleHandshake(envelope);
        break;
      case Intent.STATE_SYNC:
        this._handleStateSync(envelope.payload as CRDTSyncPayload);
        break;
      case Intent.STATE_SYNC_VECTOR:
        this._handleVectorSync(envelope);
        break;
      default:
        // ACK, NACK, BROADCAST, TASK_REQUEST, CRITIQUE, TERMINATE
        // forwarded to user-registered handlers via EventEmitter
        this.emit('message', envelope);
        break;
    }
  }

  private _handleHandshake(envelope: TPCPEnvelope): void {
    console.log(`Handshake received from ${envelope.header.sender_id}`);

    // Auto-register from payload
    const payload = envelope.payload as any;
    if (payload && payload.content) {
      try {
        const senderIdentity = JSON.parse(payload.content) as AgentIdentity;

        // Security: verify handshake signature before auto-registering the peer
        if (!envelope.signature) {
          console.warn(`Handshake dropped: unsigned packet from ${envelope.header.sender_id}`);
          return;
        }
        if (!AgentIdentityManager.verifySignature(senderIdentity.public_key, envelope.signature, payload)) {
          console.warn(`Handshake dropped: invalid signature from ${envelope.header.sender_id}`);
          return;
        }

        this.peerRegistry.set(senderIdentity.agent_id, {
          identity: senderIdentity,
          // TODO: address must be resolved via A-DNS relay or direct connection context;
          // the actual remote address is not available here without websocket refactoring.
          address: `ws://unknown`
        });
        console.log(`Auto-registered peer: ${senderIdentity.framework} (${senderIdentity.agent_id})`);
      } catch (e) {
        // Not parseable, skip
      }
    }
  }

  private _handleStateSync(payload: CRDTSyncPayload): void {
    if (payload.crdt_type === "LWW-Map") {
      this.sharedMemory.merge(payload.state as unknown as Record<string, { value: any; timestamp: number; writer_id: string }>);
      this.emit("onStateSync", this.sharedMemory.toDict());
    }
  }

  private _handleVectorSync(envelope: TPCPEnvelope): void {
    const payload = envelope.payload as VectorEmbeddingPayload;
    if (!payload.model_id || !payload.vector) {
      console.error("Invalid VectorEmbeddingPayload in STATE_SYNC_VECTOR.");
      return;
    }

    this.vectorBank.store(
      envelope.header.message_id,
      payload.vector,
      payload.model_id,
      payload.raw_text_fallback || undefined
    );

    console.log(`[Vector Bank] Ingested ${payload.dimensions}d vector (${payload.model_id}). Bank size: ${this.vectorBank.totalVectors}`);
    this.emit("onVectorSync", {
      payloadId: envelope.header.message_id,
      modelId: payload.model_id,
      dimensions: payload.dimensions,
      bankSize: this.vectorBank.totalVectors
    });
  }

  public async sendMessage(targetId: string, intent: Intent, payload: Record<string, any>): Promise<void> {
    const header: MessageHeader = {
      message_id: globalThis.crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      sender_id: this.identity.agent_id,
      receiver_id: targetId,
      intent,
      ttl: 30,
      protocol_version: PROTOCOL_VERSION
    };

    const signature = this.identityManager.signPayload(payload);
    const envelope: TPCPEnvelope = { header, payload: payload as any, signature };
    const serialized = JSON.stringify(envelope);

    await this._dispatchEnvelope(targetId, serialized, header.message_id);
  }

  private async _dispatchEnvelope(targetId: string, serialized: string, messageId: string): Promise<void> {
    const peer = this.peerRegistry.get(targetId);
    if (!peer) {
      console.warn(`Peer ${targetId} not in registry. Pushing to DLQ.`);
      this.messageQueue.enqueue(targetId, serialized, messageId);
      return;
    }

    try {
      let ws = this._peerConnections.get(targetId);
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        ws = new WebSocket(peer.address);
        await new Promise<void>((resolve, reject) => {
          ws!.on('open', resolve);
          ws!.on('error', reject);
        });
        this._peerConnections.set(targetId, ws);
      }
      ws.send(serialized);
    } catch (e) {
      console.warn(`Connection to ${targetId} failed. Pushing to DLQ.`);
      this._peerConnections.delete(targetId);
      this.messageQueue.enqueue(targetId, serialized, messageId);
      this._reconnectAndDrain(targetId);
    }
  }

  private _reconnectAndDrain(targetId: string): void {
    const peer = this.peerRegistry.get(targetId);
    if (!peer) return;

    let backoff = 1000;
    const maxBackoff = 60000;

    const attempt = () => {
      if (!this._running || !this.messageQueue.hasMessages(targetId)) return;

      const ws = new WebSocket(peer.address);
      ws.on('open', () => {
        console.log(`[Network Restored] Draining DLQ for ${targetId}...`);
        this._peerConnections.set(targetId, ws);
        backoff = 1000;

        const drainNext = () => {
          const msg = this.messageQueue.dequeueOne(targetId);
          if (!msg) return;
          try {
            ws.send(msg.data);
            console.log(`Drained ${msg.messageId} to ${targetId}.`);
            if (this.messageQueue.hasMessages(targetId)) {
              drainNext();
            }
          } catch (e) {
            this.messageQueue.enqueueFront(targetId, msg.data, msg.messageId);
          }
        };
        drainNext();
      });

      ws.on('error', () => {
        console.log(`Reconnection to ${targetId} failed. Retrying in ${backoff / 1000}s...`);
        setTimeout(attempt, backoff);
        backoff = Math.min(backoff * 2, maxBackoff);
      });
    };

    attempt();
  }

  public async broadcastDiscovery(seedNodes: string[] = []): Promise<void> {
    const targetId = "00000000-0000-0000-0000-000000000000";
    const header: MessageHeader = {
      message_id: globalThis.crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      sender_id: this.identity.agent_id,
      receiver_id: targetId,
      intent: Intent.HANDSHAKE,
      ttl: 30,
      protocol_version: PROTOCOL_VERSION
    };

    const payload = {
      payload_type: "text" as const,
      content: JSON.stringify(this.identity),
      language: "en"
    };

    const signature = this.identityManager.signPayload(payload);
    const envelope: TPCPEnvelope = { header, payload, signature };
    const serialized = JSON.stringify(envelope);

    if (this._adnsWs && this._adnsWs.readyState === WebSocket.OPEN) {
      this._adnsWs.send(serialized);
    }

    for (const address of seedNodes) {
      try {
        const ws = new WebSocket(address);
        ws.on('open', () => {
          ws.send(serialized);
          ws.close();
        });
      } catch (e) {
        console.error(`Discovery failed for ${address}`);
      }
    }
  }
}
