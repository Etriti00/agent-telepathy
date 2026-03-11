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
exports.AgentIdentityManager = void 0;
const nacl = __importStar(require("tweetnacl"));
const fast_json_stable_stringify_1 = __importDefault(require("fast-json-stable-stringify"));
class AgentIdentityManager {
    _privateKey;
    _publicKey;
    constructor(privateKeyBytes) {
        if (privateKeyBytes) {
            if (privateKeyBytes.length === 64) {
                this._privateKey = privateKeyBytes;
                this._publicKey = privateKeyBytes.slice(32);
            }
            else if (privateKeyBytes.length === 32) {
                const keyPair = nacl.sign.keyPair.fromSeed(privateKeyBytes);
                this._privateKey = keyPair.secretKey;
                this._publicKey = keyPair.publicKey;
            }
            else {
                throw new Error("Invalid private key length");
            }
        }
        else {
            const keyPair = nacl.sign.keyPair();
            this._privateKey = keyPair.secretKey;
            this._publicKey = keyPair.publicKey;
        }
    }
    getPublicKeyString() {
        return Buffer.from(this._publicKey).toString('base64');
    }
    signPayload(payloadDict) {
        const serialized = (0, fast_json_stable_stringify_1.default)(payloadDict);
        const messageUint8 = new TextEncoder().encode(serialized);
        const signature = nacl.sign.detached(messageUint8, this._privateKey);
        return Buffer.from(signature).toString('base64');
    }
    static verifySignature(publicKeyStr, signatureStr, payloadDict) {
        try {
            const publicKey = new Uint8Array(Buffer.from(publicKeyStr, 'base64'));
            const signature = new Uint8Array(Buffer.from(signatureStr, 'base64'));
            const serialized = (0, fast_json_stable_stringify_1.default)(payloadDict);
            const messageUint8 = new TextEncoder().encode(serialized);
            return nacl.sign.detached.verify(messageUint8, signature, publicKey);
        }
        catch (e) {
            return false;
        }
    }
}
exports.AgentIdentityManager = AgentIdentityManager;
