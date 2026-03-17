#!/usr/bin/env node
/**
 * TPCP Agent CLI for OpenClaw
 *
 * Usage:
 *   node lib/agent.js init                          — generate & save identity
 *   node lib/agent.js info                          — show agent ID and public key
 *   node lib/agent.js send <peer_id> <message>      — send message to a peer via relay
 *   node lib/agent.js broadcast <message>           — broadcast to all relay peers
 *   node lib/agent.js listen [--timeout <ms>]       — listen for incoming messages
 */

'use strict';

const { RelayTPCPNode, AgentIdentityManager, Intent } = require('tpcp-sdk');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// ── Config ───────────────────────────────────────────────────────────────────

const TPCP_DIR = path.join(os.homedir(), '.openclaw', 'tpcp');
const KEY_FILE = path.join(TPCP_DIR, 'identity.key');     // base64 32-byte seed
const META_FILE = path.join(TPCP_DIR, 'identity.json');   // agent_id etc.
const RELAY_URL = process.env.TPCP_RELAY_URL || 'wss://relay.agent-telepathy.io';
const BROADCAST_ID = '00000000-0000-0000-0000-000000000000';

// ── Helpers ───────────────────────────────────────────────────────────────────

function loadMeta() {
  if (!fs.existsSync(META_FILE)) {
    console.error('No TPCP identity found. Run: node lib/agent.js init');
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(META_FILE, 'utf8'));
}

function buildIdentity(meta, manager) {
  return {
    agent_id: meta.agent_id,
    framework: 'openclaw',
    public_key: manager.getPublicKeyString(),
    capabilities: ['chat', 'task', 'broadcast'],
    modality: ['text'],
  };
}

async function makeNode(meta, manager) {
  const identity = buildIdentity(meta, manager);
  const node = new RelayTPCPNode(identity, RELAY_URL);

  // Patch identity manager reference (public field)
  node.identityManager = manager;
  node.identity.public_key = manager.getPublicKeyString();

  await node.startListening();

  // Wait up to 8s for relay registration (ADNS_REGISTERED sets _adnsRegistered)
  const deadline = Date.now() + 8000;
  while (!node['_adnsRegistered'] && Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 100));
  }
  if (!node['_adnsRegistered']) {
    throw new Error(`Could not register with relay at ${RELAY_URL} within 8s`);
  }

  return node;
}

function sendViaRelay(node, targetId, intent, payload) {
  const ws = node['_adnsWs'];
  if (!ws || ws.readyState !== 1 /* OPEN */) {
    throw new Error('Relay connection is not open');
  }

  const envelope = {
    header: {
      message_id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      sender_id: node.identity.agent_id,
      receiver_id: targetId,
      intent,
      ttl: 30,
      protocol_version: '0.4',
    },
    payload,
    signature: node.identityManager.signPayload(payload),
  };

  ws.send(JSON.stringify(envelope));
}

// ── Commands ──────────────────────────────────────────────────────────────────

async function cmdInit() {
  if (fs.existsSync(KEY_FILE)) {
    const meta = JSON.parse(fs.readFileSync(META_FILE, 'utf8'));
    console.log('Identity already exists:');
    console.log('  Agent ID:', meta.agent_id);
    console.log('  Key file:', KEY_FILE);
    console.log('Delete', KEY_FILE, 'and re-run to regenerate.');
    return;
  }

  fs.mkdirSync(TPCP_DIR, { recursive: true });

  // autoSave writes the 32-byte seed to KEY_FILE
  const manager = new AgentIdentityManager({ keyPath: KEY_FILE, autoSave: true });
  const pubKey = manager.getPublicKeyString();
  const agentId = 'openclaw-' + pubKey.slice(0, 12).replace(/[^a-zA-Z0-9]/g, '');

  const meta = {
    agent_id: agentId,
    framework: 'openclaw',
    public_key: pubKey,
    capabilities: ['chat', 'task', 'broadcast'],
    modality: ['text'],
  };
  fs.writeFileSync(META_FILE, JSON.stringify(meta, null, 2));

  console.log('TPCP identity created:');
  console.log('  Agent ID:', agentId);
  console.log('  Key file:', KEY_FILE);
  console.log('  Relay:   ', RELAY_URL);
}

async function cmdInfo() {
  const meta = loadMeta();
  console.log(JSON.stringify({
    agent_id: meta.agent_id,
    public_key: meta.public_key,
    relay: RELAY_URL,
  }, null, 2));
}

async function cmdSend(peerId, message) {
  if (!peerId || !message) {
    console.error('Usage: node lib/agent.js send <peer_id> <message>');
    process.exit(1);
  }

  const meta = loadMeta();
  const manager = new AgentIdentityManager({ keyPath: KEY_FILE });
  const node = await makeNode(meta, manager);

  const payload = {
    payload_type: 'text',
    content: message,
    language: 'en',
  };

  sendViaRelay(node, peerId, Intent.BROADCAST, payload);
  console.log(JSON.stringify({ status: 'sent', to: peerId, message }));

  await new Promise(r => setTimeout(r, 500)); // flush
  await node.stopListening();
}

async function cmdBroadcast(message) {
  if (!message) {
    console.error('Usage: node lib/agent.js broadcast <message>');
    process.exit(1);
  }

  const meta = loadMeta();
  const manager = new AgentIdentityManager({ keyPath: KEY_FILE });
  const node = await makeNode(meta, manager);

  const payload = {
    payload_type: 'text',
    content: message,
    language: 'en',
  };

  sendViaRelay(node, BROADCAST_ID, Intent.BROADCAST, payload);
  console.log(JSON.stringify({ status: 'broadcast', message }));

  await new Promise(r => setTimeout(r, 500));
  await node.stopListening();
}

async function cmdListen(rawTimeout) {
  const timeout = parseInt(rawTimeout) || 30000;
  const meta = loadMeta();
  const manager = new AgentIdentityManager({ keyPath: KEY_FILE });
  const node = await makeNode(meta, manager);

  process.stderr.write(`Listening for ${timeout / 1000}s on ${RELAY_URL}...\n`);

  node.on('message', (envelope) => {
    process.stdout.write(JSON.stringify({
      from: envelope.header.sender_id,
      intent: envelope.header.intent,
      content: envelope.payload.content || envelope.payload,
      timestamp: envelope.header.timestamp,
    }) + '\n');
  });

  await new Promise(r => setTimeout(r, timeout));
  await node.stopListening();
}

// ── Entry point ───────────────────────────────────────────────────────────────

const [,, cmd, ...args] = process.argv;

if (!cmd || cmd === '--help' || cmd === '-h') {
  console.log([
    'TPCP Agent CLI for OpenClaw',
    '',
    'Commands:',
    '  init                          Generate TPCP identity (run once)',
    '  info                          Show agent ID and public key',
    '  send <peer_id> <message>      Send message to a specific agent',
    '  broadcast <message>           Broadcast to all relay peers',
    '  listen [--timeout <ms>]       Listen for messages (default 30s)',
    '',
    'Environment:',
    '  TPCP_RELAY_URL                Relay WebSocket URL',
    '                                Default: wss://relay.agent-telepathy.io',
  ].join('\n'));
  process.exit(0);
}

const commands = {
  init: () => cmdInit(),
  info: () => cmdInfo(),
  send: () => cmdSend(args[0], args.slice(1).join(' ')),
  broadcast: () => cmdBroadcast(args.join(' ')),
  listen: () => cmdListen(args[0] === '--timeout' ? args[1] : args[0]),
};

if (!commands[cmd]) {
  console.error('Unknown command:', cmd, '\nRun with --help for usage.');
  process.exit(1);
}

commands[cmd]().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
