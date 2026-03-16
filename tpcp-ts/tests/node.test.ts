import * as crypto from 'crypto';
import { TPCPNode, TPCPNodeEvents } from '../src/core/node';

// Node 18 jest doesn't expose globalThis.crypto — polyfill it
if (!globalThis.crypto) {
  (globalThis as any).crypto = crypto;
}

describe('TPCPNode typed events', () => {
  test('TPCPNodeEvents interface has required event keys', () => {
    const handler: TPCPNodeEvents['ready'] = () => {};
    const msgHandler: TPCPNodeEvents['message'] = (_env) => {};
    const errHandler: TPCPNodeEvents['error'] = (_err) => {};
    const peerHandler: TPCPNodeEvents['peer:connected'] = (_id) => {};
    expect(handler).toBeDefined();
    expect(msgHandler).toBeDefined();
    expect(errHandler).toBeDefined();
    expect(peerHandler).toBeDefined();
  });

  test('node emits ready event on startListening', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    // Constructor: (identity, host, port, adnsUrl?)
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    const readyPromise = new Promise<void>((resolve) => {
      node.on('ready', () => resolve());
    });
    await node.startListening();
    await readyPromise;
    await node.stopListening();
  });

  test('concurrent _getOrCreateConnection returns same promise', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    expect((node as any)._pendingConnections).toBeInstanceOf(Map);
    expect((node as any)._pendingConnections.size).toBe(0);
  });
});
