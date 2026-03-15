/**
 * WebSocket factory abstraction — lets the same TPCPNode code run in Node.js
 * (using the 'ws' package) and in browsers (using native WebSocket).
 */

export type WebSocketFactory = (url: string) => WebSocket | import('ws').WebSocket;

/** Auto-detects the environment and returns the right factory. */
export function defaultWebSocketFactory(): WebSocketFactory {
  if (typeof globalThis.WebSocket !== 'undefined') {
    // Browser or Deno environment — use native WebSocket
    return (url: string) => new globalThis.WebSocket(url);
  }
  // Node.js environment — use 'ws' package
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { WebSocket: NodeWebSocket } = require('ws');
  return (url: string) => new NodeWebSocket(url);
}
