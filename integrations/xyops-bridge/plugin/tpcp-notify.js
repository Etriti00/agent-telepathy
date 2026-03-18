#!/usr/bin/env node
/**
 * xyops plugin: tpcp-notify
 *
 * An xyops event plugin that sends a TPCP message when a job completes.
 * Register this as an xyops plugin to get TPCP notifications for any job.
 *
 * xyops plugin protocol:
 *   - Receives JSON on stdin: { xy: 1, type: "event", params: {...}, input: {...} }
 *   - Writes progress to stdout: { xy: 1, progress: 0.5 }
 *   - Writes completion to stdout: { xy: 1, code: 0 } (success) or { xy: 1, code: N, description: "..." }
 *
 * Required params (set in xyops plugin config):
 *   tpcp_relay_url  - WebSocket URL of the TPCP relay (default: ws://localhost:8765)
 *   tpcp_sender_id  - Agent ID of this notifier (default: "xyops-agent")
 *   tpcp_target_id  - Target agent ID to notify (required, or use BROADCAST_ID)
 *   tpcp_key_file   - Path to Ed25519 seed file (optional)
 *
 * Optional params:
 *   message         - Custom message body (default: job summary JSON)
 *   intent          - TPCP intent (default: STATE_SYNC)
 */

"use strict";

const WebSocket = require("ws");
const crypto = require("crypto");
const fs = require("fs");

const BROADCAST_ID = "00000000-0000-0000-0000-000000000000";

// Read stdin job context
let rawInput = "";
process.stdin.on("data", (chunk) => { rawInput += chunk; });
process.stdin.on("end", () => {
  let job;
  try {
    job = JSON.parse(rawInput);
  } catch (e) {
    writeOut({ xy: 1, code: 1, description: "Invalid stdin JSON: " + e.message });
    process.exit(1);
  }

  run(job).catch((err) => {
    writeOut({ xy: 1, code: 1, description: "tpcp-notify error: " + err.message });
    process.exit(1);
  });
});

async function run(job) {
  const params = job.params || {};
  const relayUrl = params.tpcp_relay_url || process.env.TPCP_RELAY_URL || "ws://localhost:8765";
  const senderId = params.tpcp_sender_id || "xyops-agent";
  const targetId = params.tpcp_target_id || BROADCAST_ID;
  const intent = params.intent || "STATE_SYNC";
  const jobId = params.tpcp_job_id || job.id || crypto.randomUUID();

  // Build message payload
  const payload = {
    type: "job_status_update",
    job_id: jobId,
    xyops_job_id: job.id || jobId,
    status: "success",
    progress_pct: 100,
    description: params.message || `xyops job ${job.id || jobId} completed`,
    updated_at: new Date().toISOString(),
  };

  writeOut({ xy: 1, progress: 0.5 });

  // Load optional signing key
  let privateKeyBytes = null;
  if (params.tpcp_key_file && fs.existsSync(params.tpcp_key_file)) {
    const seed = fs.readFileSync(params.tpcp_key_file);
    // seed is 32 bytes (raw) or base64
    privateKeyBytes = seed.length === 32 ? seed : Buffer.from(seed.toString().trim(), "base64");
  }

  await sendViaTpcp({ relayUrl, senderId, targetId, intent, payload, privateKeyBytes });

  writeOut({ xy: 1, code: 0 });
}

async function sendViaTpcp({ relayUrl, senderId, targetId, intent, payload, privateKeyBytes }) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(relayUrl);
    const timeout = setTimeout(() => {
      ws.terminate();
      reject(new Error("Relay connection timeout (10s)"));
    }, 10_000);

    ws.on("open", () => {
      // HANDSHAKE first
      const handshake = {
        header: {
          message_id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          sender_id: senderId,
          receiver_id: "relay",
          intent: "HANDSHAKE",
          ttl: 30,
          protocol_version: "0.4",
        },
        payload: {
          agent_id: senderId,
          framework: "xyops",
          public_key: "",
          capabilities: ["notify"],
          modality: ["text"],
        },
        signature: "",
      };
      ws.send(JSON.stringify(handshake));

      // Send actual message after brief delay for handshake processing
      setTimeout(() => {
        let signature = "";
        if (privateKeyBytes) {
          try {
            const keyObj = crypto.createPrivateKey({ key: privateKeyBytes, format: "der", type: "pkcs8" });
            signature = crypto.sign(null, Buffer.from(JSON.stringify(payload)), keyObj).toString("base64");
          } catch { /* signing optional */ }
        }

        const envelope = {
          header: {
            message_id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            sender_id: senderId,
            receiver_id: targetId,
            intent,
            ttl: 30,
            protocol_version: "0.4",
          },
          payload,
          signature,
        };
        ws.send(JSON.stringify(envelope));

        // Give relay 1s to forward the message, then close
        setTimeout(() => {
          clearTimeout(timeout);
          ws.close();
          resolve();
        }, 1_000);
      }, 300);
    });

    ws.on("error", (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}

function writeOut(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}
