"use strict";
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
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TPCPNode = void 0;
const events_1 = require("events");
const ws_1 = __importDefault(require("ws"));
const crypto = __importStar(require("crypto"));
const envelope_1 = require("../schemas/envelope");
const crdt_1 = require("../memory/crdt");
const crypto_1 = require("../security/crypto");
class TPCPNode extends events_1.EventEmitter {
    identity;
    host;
    port;
    adnsUrl;
    peerRegistry = new Map();
    sharedMemory;
    identityManager;
    _server;
    _adnsWs;
    constructor(identity, host = "127.0.0.1", port = 8000, adnsUrl) {
        super();
        this.identity = identity;
        this.host = host;
        this.port = port;
        this.adnsUrl = adnsUrl;
        this.identityManager = new crypto_1.AgentIdentityManager();
        this.identity.public_key = this.identityManager.getPublicKeyString();
        this.sharedMemory = new crdt_1.LWWMap(this.identity.agent_id);
    }
    registerPeer(identity, address) {
        this.peerRegistry.set(identity.agent_id, { identity, address });
    }
    async startListening() {
        this._server = new ws_1.default.Server({ host: this.host, port: this.port });
        this._server.on("connection", (ws) => {
            ws.on("message", async (data) => {
                await this._handleInbound(data.toString());
            });
        });
        if (this.adnsUrl) {
            await this._connectToADNS();
        }
    }
    async _connectToADNS() {
        if (!this.adnsUrl)
            return;
        this._adnsWs = new ws_1.default(this.adnsUrl);
        this._adnsWs.on("open", async () => {
            await this.broadcastDiscovery();
        });
        this._adnsWs.on("message", async (data) => {
            await this._handleInbound(data.toString());
        });
    }
    async _handleInbound(rawMessage) {
        try {
            const parsed = JSON.parse(rawMessage);
            const envelope = envelope_1.TPCPEnvelopeSchema.parse(parsed);
            // SECURITY MIDDLEWARE: Cryptographic Validation
            if (!envelope.signature) {
                console.warn(`SecurityWarning: Dropping unsigned packet from ${envelope.header.sender_id}`);
                return;
            }
            if (envelope.header.intent !== envelope_1.Intent.HANDSHAKE) {
                const peer = this.peerRegistry.get(envelope.header.sender_id);
                if (!peer) {
                    console.warn(`SecurityWarning: Unregistered peer ${envelope.header.sender_id}. Dropping packet.`);
                    return;
                }
                const senderPubKey = peer.identity.public_key;
                if (!crypto_1.AgentIdentityManager.verifySignature(senderPubKey, envelope.signature, envelope.payload)) {
                    console.warn(`SecurityWarning: Invalid signature from ${envelope.header.sender_id}. Dropping packet.`);
                    return;
                }
            }
            await this._routeIntent(envelope);
        }
        catch (e) {
            console.error(`Failed to process inbound message:`, e);
        }
    }
    async _routeIntent(envelope) {
        switch (envelope.header.intent) {
            case envelope_1.Intent.HANDSHAKE:
                console.log(`Handshake received from ${envelope.header.sender_id}`);
                break;
            case envelope_1.Intent.STATE_SYNC:
                this._handleStateSync(envelope.payload);
                break;
            // Future handler routing for tasks, critique, vectors...
        }
    }
    _handleStateSync(payload) {
        if (payload.crdt_type === "LWW-Map") {
            this.sharedMemory.merge(payload.state);
            this.emit("onStateSync", this.sharedMemory.toDict());
        }
    }
    async broadcastDiscovery(seedNodes = []) {
        const targetId = "00000000-0000-0000-0000-000000000000";
        const header = {
            message_id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            sender_id: this.identity.agent_id,
            receiver_id: targetId,
            intent: envelope_1.Intent.HANDSHAKE,
            ttl: 30
        };
        const payload = {
            content: JSON.stringify(this.identity),
            language: "en"
        };
        const signature = this.identityManager.signPayload(payload);
        const envelope = { header, payload, signature };
        const serialized = JSON.stringify(envelope);
        if (this._adnsWs && this._adnsWs.readyState === ws_1.default.OPEN) {
            this._adnsWs.send(serialized);
        }
        for (const address of seedNodes) {
            try {
                const ws = new ws_1.default(address);
                ws.on('open', () => {
                    ws.send(serialized);
                    ws.close();
                });
            }
            catch (e) {
                console.error(`Discovery failed for ${address}`);
            }
        }
    }
}
exports.TPCPNode = TPCPNode;
