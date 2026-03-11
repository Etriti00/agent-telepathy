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

import * as nacl from 'tweetnacl';
import stringify from 'fast-json-stable-stringify';

export class AgentIdentityManager {
  private _privateKey: Uint8Array;
  private _publicKey: Uint8Array;

  constructor(privateKeyBytes?: Uint8Array) {
    if (privateKeyBytes) {
      if (privateKeyBytes.length === 64) {
        this._privateKey = privateKeyBytes;
        this._publicKey = privateKeyBytes.slice(32);
      } else if (privateKeyBytes.length === 32) {
        const keyPair = nacl.sign.keyPair.fromSeed(privateKeyBytes);
        this._privateKey = keyPair.secretKey;
        this._publicKey = keyPair.publicKey;
      } else {
        throw new Error("Invalid private key length");
      }
    } else {
      const keyPair = nacl.sign.keyPair();
      this._privateKey = keyPair.secretKey;
      this._publicKey = keyPair.publicKey;
    }
  }

  public getPublicKeyString(): string {
    return Buffer.from(this._publicKey).toString('base64');
  }

  public signPayload(payloadDict: Record<string, any>): string {
    const serialized = stringify(payloadDict);
    const messageUint8 = new TextEncoder().encode(serialized);
    const signature = nacl.sign.detached(messageUint8, this._privateKey);
    return Buffer.from(signature).toString('base64');
  }

  public static verifySignature(publicKeyStr: string, signatureStr: string, payloadDict: Record<string, any>): boolean {
    try {
      const publicKey = new Uint8Array(Buffer.from(publicKeyStr, 'base64'));
      const signature = new Uint8Array(Buffer.from(signatureStr, 'base64'));
      const serialized = stringify(payloadDict);
      const messageUint8 = new TextEncoder().encode(serialized);
      
      return nacl.sign.detached.verify(messageUint8, signature, publicKey);
    } catch (e) {
      return false;
    }
  }
}
