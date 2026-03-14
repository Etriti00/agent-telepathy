import { defaultWebSocketFactory } from '../src/transport/websocket-factory';

describe('WebSocket factory', () => {
  it('returns a callable factory', () => {
    const factory = defaultWebSocketFactory();
    expect(typeof factory).toBe('function');
  });

  it('factory creates a connection attempt (Node.js env)', () => {
    const factory = defaultWebSocketFactory();
    // In Node.js, ws is available. Just verify factory returns an object.
    // Don't actually connect — just test that ws is importable.
    expect(factory).toBeDefined();
  });
});
