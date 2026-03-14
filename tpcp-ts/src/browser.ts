/**
 * Browser entry point for tpcp-ts.
 *
 * Use this import in browser/bundler environments:
 *   import { TPCPNode, ... } from 'tpcp-ts/browser';
 *
 * It re-exports everything from the main SDK but forces the native
 * WebSocket factory, ensuring no Node.js-only dependencies are loaded.
 */
export * from './index.js';
export { defaultWebSocketFactory } from './transport/websocket-factory.js';
