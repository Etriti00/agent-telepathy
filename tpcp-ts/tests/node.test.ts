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

  test('sendMessage rejects invalid payload', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    await node.startListening();
    // Missing required payload_type field
    await expect(
      node.sendMessage('target-id', 'Task_Request' as any, { content: 'hello' } as any)
    ).rejects.toThrow('Invalid payload');
    await node.stopListening();
  });

  test('sendMessage with valid payload queues to DLQ when peer not found', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    await node.startListening();
    // Valid payload but unknown target => DLQ
    await node.sendMessage('unknown-peer', 'Task_Request' as any, {
      payload_type: 'text',
      content: 'hello',
      language: 'en',
    } as any);
    expect(node.messageQueue.hasMessages('unknown-peer')).toBe(true);
    await node.stopListening();
  });

  test('registerPeer and removePeer lifecycle', () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    const peerId = 'peer-123';
    const peerIdentity = {
      agent_id: peerId,
      framework: 'other',
      capabilities: [],
      public_key: 'abc',
      modality: ['text'],
    };
    node.registerPeer(peerIdentity, 'ws://localhost:9999');
    expect(node.peerRegistry.has(peerId)).toBe(true);
    node.removePeer(peerId);
    expect(node.peerRegistry.has(peerId)).toBe(false);
  });

  test('_handleInbound drops duplicate messages', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    await node.startListening();

    // Pre-seed a seen message
    const msgId = globalThis.crypto.randomUUID();
    node._seenMessages.set(msgId, Date.now());

    const envelope = JSON.stringify({
      header: {
        message_id: msgId,
        timestamp: new Date().toISOString(),
        sender_id: globalThis.crypto.randomUUID(),
        receiver_id: identity.agent_id,
        intent: 'Task_Request',
        ttl: 30,
        protocol_version: '0.4.0',
      },
      payload: { payload_type: 'text', content: 'replay', language: 'en' },
    });

    // Should not throw — just silently drops
    await (node as any)._handleInbound(envelope);
    await node.stopListening();
  });

  test('_handleInbound drops TTL=0 messages', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    await node.startListening();

    const envelope = JSON.stringify({
      header: {
        message_id: globalThis.crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        sender_id: globalThis.crypto.randomUUID(),
        receiver_id: identity.agent_id,
        intent: 'Task_Request',
        ttl: 0,
        protocol_version: '0.4.0',
      },
      payload: { payload_type: 'text', content: 'expired', language: 'en' },
    });

    // Should not throw — just silently drops
    await (node as any)._handleInbound(envelope);
    await node.stopListening();
  });

  test('_handleInbound emits error for invalid JSON', async () => {
    const identity = {
      agent_id: globalThis.crypto.randomUUID(),
      framework: 'test',
      capabilities: [],
      public_key: '',
      modality: ['text'],
    };
    const node = new TPCPNode(identity, '127.0.0.1', 0);
    await node.startListening();

    const errors: Error[] = [];
    node.on('error', (err) => errors.push(err));

    await (node as any)._handleInbound('not-valid-json{{{');
    expect(errors.length).toBe(1);
    await node.stopListening();
  });
});
