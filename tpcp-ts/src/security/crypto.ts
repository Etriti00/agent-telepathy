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

// Node.js-specific APIs are lazy-required so this module is safe to bundle for
// the browser. In a browser environment, file-based key loading is skipped and
// saveKey() throws an informative error.
const isNode = typeof process !== 'undefined' && process.versions != null && process.versions.node != null;

const ENV_VAR_PRIVATE_KEY = 'TPCP_PRIVATE_KEY';

function getDefaultKeyPath(): string {
  if (!isNode) return '';
  // Dynamic require to avoid browser bundle failures.
  const os = require('os') as typeof import('os');
  const path = require('path') as typeof import('path');
  return path.join(os.homedir(), '.tpcp', 'identity.key');
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export class AgentIdentityManager {
  private _privateKey: Uint8Array;
  private _publicKey: Uint8Array;
  public readonly wasLoaded: boolean;

  /**
   * Key resolution order:
   * 1. Explicit privateKeyBytes
   * 2. TPCP_PRIVATE_KEY env var (base64 raw 32 bytes) — Node.js only
   * 3. Key file at keyPath (default ~/.tpcp/identity.key) — Node.js only
   * 4. Generate new keypair (auto-save if autoSave=true, Node.js only)
   */
  constructor(options?: {
    privateKeyBytes?: Uint8Array;
    keyPath?: string;
    autoSave?: boolean;
  }) {
    const opts = options || {};

    if (opts.privateKeyBytes) {
      if (opts.privateKeyBytes.length === 64) {
        this._privateKey = opts.privateKeyBytes;
        this._publicKey = opts.privateKeyBytes.slice(32);
      } else if (opts.privateKeyBytes.length === 32) {
        const keyPair = nacl.sign.keyPair.fromSeed(opts.privateKeyBytes);
        this._privateKey = keyPair.secretKey;
        this._publicKey = keyPair.publicKey;
      } else {
        throw new Error("Invalid private key length");
      }
      this.wasLoaded = true;
    } else if (isNode && process.env[ENV_VAR_PRIVATE_KEY]) {
      const raw = Buffer.from(process.env[ENV_VAR_PRIVATE_KEY]!, 'base64');
      const keyPair = nacl.sign.keyPair.fromSeed(new Uint8Array(raw));
      this._privateKey = keyPair.secretKey;
      this._publicKey = keyPair.publicKey;
      this.wasLoaded = true;
      console.log("Loaded Ed25519 identity from TPCP_PRIVATE_KEY env var.");
    } else if (isNode) {
      const fs = require('fs') as typeof import('fs');
      const keyPath = opts.keyPath || getDefaultKeyPath();
      if (fs.existsSync(keyPath)) {
        const encoded = fs.readFileSync(keyPath, 'utf-8').trim();
        const raw = Buffer.from(encoded, 'base64');
        const keyPair = nacl.sign.keyPair.fromSeed(new Uint8Array(raw));
        this._privateKey = keyPair.secretKey;
        this._publicKey = keyPair.publicKey;
        this.wasLoaded = true;
        console.log(`Loaded Ed25519 identity from ${keyPath}`);
      } else {
        const keyPair = nacl.sign.keyPair();
        this._privateKey = keyPair.secretKey;
        this._publicKey = keyPair.publicKey;
        this.wasLoaded = false;
        console.log("Generated new Ed25519 keypair.");
        if (opts.autoSave) {
          this.saveKey(keyPath);
        }
      }
    } else {
      // Browser / WASM environment: always generate a fresh keypair.
      const keyPair = nacl.sign.keyPair();
      this._privateKey = keyPair.secretKey;
      this._publicKey = keyPair.publicKey;
      this.wasLoaded = false;
    }
  }

  public getPublicKeyString(): string {
    // btoa + Uint8Array works in Node.js ≥16 and all modern browsers (no Buffer dependency)
    return btoa(String.fromCharCode(...this._publicKey));
  }

  public getPrivateKeySeed(): Uint8Array {
    // Return the 32-byte seed (first 32 bytes of the 64-byte secret key)
    return this._privateKey.slice(0, 32);
  }

  public saveKey(keyPath?: string): string {
    if (!isNode) {
      throw new Error("saveKey() is only available in Node.js environments");
    }
    const fs = require('fs') as typeof import('fs');
    const path = require('path') as typeof import('path');
    const target = keyPath || getDefaultKeyPath();
    const dir = path.dirname(target);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const seed = this.getPrivateKeySeed();
    const encoded = Buffer.from(seed).toString('base64');
    fs.writeFileSync(target, encoded, { mode: 0o600 });
    console.log(`Saved Ed25519 identity to ${target}`);
    return target;
  }

  public signPayload(payloadDict: Record<string, any>): string {
    const serialized = stringify(payloadDict);
    const messageUint8 = new TextEncoder().encode(serialized);
    const signature = nacl.sign.detached(messageUint8, this._privateKey);
    return btoa(String.fromCharCode(...signature));
  }

  public signBytes(data: Uint8Array): string {
    const signature = nacl.sign.detached(data, this._privateKey);
    return btoa(String.fromCharCode(...signature));
  }

  public static verifySignature(publicKeyStr: string, signatureStr: string, payloadDict: Record<string, any>): boolean {
    try {
      const publicKey = base64ToBytes(publicKeyStr);
      const signature = base64ToBytes(signatureStr);
      const serialized = stringify(payloadDict);
      const messageUint8 = new TextEncoder().encode(serialized);
      return nacl.sign.detached.verify(messageUint8, signature, publicKey);
    } catch (e) {
      return false;
    }
  }

  public static verifyBytes(publicKeyStr: string, signatureStr: string, data: Uint8Array): boolean {
    try {
      const publicKey = base64ToBytes(publicKeyStr);
      const signature = base64ToBytes(signatureStr);
      return nacl.sign.detached.verify(data, signature, publicKey);
    } catch (e) {
      return false;
    }
  }
}
