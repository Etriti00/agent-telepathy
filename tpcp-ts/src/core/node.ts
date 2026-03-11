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
import * as crypto from 'crypto';
import { 
  AgentIdentity, 
  TPCPEnvelope, 
  Intent, 
  MessageHeader, 
  TPCPEnvelopeSchema, 
  CRDTSyncPayload 
} from '../schemas/envelope';
import { LWWMap } from '../memory/crdt';
import { AgentIdentityManager } from '../security/crypto';

export class TPCPNode extends EventEmitter {
  public identity: AgentIdentity;
  public host: string;
  public port: number;
  public adnsUrl?: string;

  public peerRegistry: Map<string, { identity: AgentIdentity; address: string }> = new Map();
  public sharedMemory: LWWMap;
  public identityManager: AgentIdentityManager;

  private _server?: WebSocket.Server;
  private _adnsWs?: WebSocket;

  constructor(identity: AgentIdentity, host: string = "127.0.0.1", port: number = 8000, adnsUrl?: string) {
    super();
    this.identity = identity;
    this.host = host;
    this.port = port;
    this.adnsUrl = adnsUrl;

    this.identityManager = new AgentIdentityManager();
    this.identity.public_key = this.identityManager.getPublicKeyString();

    this.sharedMemory = new LWWMap(this.identity.agent_id);
  }

  public registerPeer(identity: AgentIdentity, address: string): void {
    this.peerRegistry.set(identity.agent_id, { identity, address });
  }

  public async startListening(): Promise<void> {
    this._server = new WebSocket.Server({ host: this.host, port: this.port });
    
    this._server.on("connection", (ws: WebSocket) => {
      ws.on("message", async (data: WebSocket.RawData) => {
        await this._handleInbound(data.toString());
      });
    });

    if (this.adnsUrl) {
      await this._connectToADNS();
    }
  }

  private async _connectToADNS(): Promise<void> {
    if (!this.adnsUrl) return;
    this._adnsWs = new WebSocket(this.adnsUrl);

    this._adnsWs.on("open", async () => {
      await this.broadcastDiscovery();
    });

    this._adnsWs.on("message", async (data: WebSocket.RawData) => {
      await this._handleInbound(data.toString());
    });
  }

  private async _handleInbound(rawMessage: string): Promise<void> {
    try {
      const parsed = JSON.parse(rawMessage);
      const envelope = TPCPEnvelopeSchema.parse(parsed);

      // SECURITY MIDDLEWARE: Cryptographic Validation
      if (!envelope.signature) {
        console.warn(`SecurityWarning: Dropping unsigned packet from ${envelope.header.sender_id}`);
        return;
      }

      if (envelope.header.intent !== Intent.HANDSHAKE) {
        const peer = this.peerRegistry.get(envelope.header.sender_id);
        if (!peer) {
          console.warn(`SecurityWarning: Unregistered peer ${envelope.header.sender_id}. Dropping packet.`);
          return;
        }

        const senderPubKey = peer.identity.public_key;
        if (!AgentIdentityManager.verifySignature(senderPubKey, envelope.signature, envelope.payload)) {
          console.warn(`SecurityWarning: Invalid signature from ${envelope.header.sender_id}. Dropping packet.`);
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
        console.log(`Handshake received from ${envelope.header.sender_id}`);
        break;
      case Intent.STATE_SYNC:
        this._handleStateSync(envelope.payload as CRDTSyncPayload);
        break;
      // Future handler routing for tasks, critique, vectors...
    }
  }

  private _handleStateSync(payload: CRDTSyncPayload): void {
    if (payload.crdt_type === "LWW-Map") {
      this.sharedMemory.merge(payload.state as Record<string, { value: any; timestamp: number; writer_id: string }>);
      this.emit("onStateSync", this.sharedMemory.toDict());
    }
  }

  public async broadcastDiscovery(seedNodes: string[] = []): Promise<void> {
    const targetId = "00000000-0000-0000-0000-000000000000";
    const header: MessageHeader = {
      message_id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      sender_id: this.identity.agent_id,
      receiver_id: targetId,
      intent: Intent.HANDSHAKE,
      ttl: 30
    };

    const payload = {
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
