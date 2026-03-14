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

import { z } from "zod";

export enum Intent {
  HANDSHAKE = "Handshake",
  TASK_REQUEST = "Task_Request",
  STATE_SYNC = "State_Sync",
  STATE_SYNC_VECTOR = "State_Sync_Vector",
  MEDIA_SHARE = "Media_Share",
  CRITIQUE = "Critique",
  TERMINATE = "Terminate"
}

export const PROTOCOL_VERSION = "0.3.0";

export const AgentIdentitySchema = z.object({
  agent_id: z.string().uuid(),
  framework: z.string(),
  capabilities: z.array(z.string()),
  public_key: z.string(),
  modality: z.array(z.string()).default(["text"])
});
export type AgentIdentity = z.infer<typeof AgentIdentitySchema>;

export const MessageHeaderSchema = z.object({
  message_id: z.string().uuid(),
  timestamp: z.string(),
  sender_id: z.string().uuid(),
  receiver_id: z.string().uuid(),
  intent: z.nativeEnum(Intent),
  ttl: z.number().int().min(0).default(30),
  protocol_version: z.string().default(PROTOCOL_VERSION)
});
export type MessageHeader = z.infer<typeof MessageHeaderSchema>;

// ── DISCRIMINATED PAYLOAD TYPES ────────────────────────────────────────

export const TextPayloadSchema = z.object({
  payload_type: z.literal("text").default("text"),
  content: z.string(),
  language: z.string().default("en")
});
export type TextPayload = z.infer<typeof TextPayloadSchema>;

export const VectorEmbeddingPayloadSchema = z.object({
  payload_type: z.literal("vector_embedding").default("vector_embedding"),
  model_id: z.string(),
  dimensions: z.number().int().positive(),
  vector: z.array(z.number()),
  raw_text_fallback: z.string().nullable().optional()
}).refine(data => {
  if (data.vector.length !== data.dimensions) return false;
  const KNOWN_MODELS: Record<string, number> = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "all-MiniLM-L6-v2": 384
  };
  if (KNOWN_MODELS[data.model_id]) {
    return data.dimensions === KNOWN_MODELS[data.model_id];
  }
  return true;
}, {
  message: "Invalid vector dimensions or known model strictly violated."
});
export type VectorEmbeddingPayload = z.infer<typeof VectorEmbeddingPayloadSchema>;

export const CRDTSyncPayloadSchema = z.object({
  payload_type: z.literal("crdt_sync").default("crdt_sync"),
  crdt_type: z.string(),
  state: z.record(z.string(), z.any()),
  vector_clock: z.record(z.string(), z.number().int())
});
export type CRDTSyncPayload = z.infer<typeof CRDTSyncPayloadSchema>;

// ── MULTIMODAL PAYLOAD TYPES ──────────────────────────────────────────

export const ImagePayloadSchema = z.object({
  payload_type: z.literal("image").default("image"),
  data_base64: z.string(),
  mime_type: z.string().default("image/png"),
  width: z.number().int().positive().nullable().optional(),
  height: z.number().int().positive().nullable().optional(),
  source_model: z.string().nullable().optional(),
  caption: z.string().nullable().optional()
});
export type ImagePayload = z.infer<typeof ImagePayloadSchema>;

export const AudioPayloadSchema = z.object({
  payload_type: z.literal("audio").default("audio"),
  data_base64: z.string(),
  mime_type: z.string().default("audio/wav"),
  sample_rate: z.number().int().positive().nullable().optional(),
  duration_seconds: z.number().positive().nullable().optional(),
  source_model: z.string().nullable().optional(),
  transcript: z.string().nullable().optional()
});
export type AudioPayload = z.infer<typeof AudioPayloadSchema>;

export const VideoPayloadSchema = z.object({
  payload_type: z.literal("video").default("video"),
  data_base64: z.string(),
  mime_type: z.string().default("video/mp4"),
  width: z.number().int().positive().nullable().optional(),
  height: z.number().int().positive().nullable().optional(),
  duration_seconds: z.number().positive().nullable().optional(),
  fps: z.number().positive().nullable().optional(),
  source_model: z.string().nullable().optional(),
  description: z.string().nullable().optional()
});
export type VideoPayload = z.infer<typeof VideoPayloadSchema>;

export const BinaryPayloadSchema = z.object({
  payload_type: z.literal("binary").default("binary"),
  data_base64: z.string(),
  mime_type: z.string().default("application/octet-stream"),
  filename: z.string().nullable().optional(),
  description: z.string().nullable().optional()
});
export type BinaryPayload = z.infer<typeof BinaryPayloadSchema>;

// ── DISCRIMINATED UNION ───────────────────────────────────────────────

export const PayloadSchema = z.discriminatedUnion("payload_type", [
  TextPayloadSchema,
  VectorEmbeddingPayloadSchema as any,
  CRDTSyncPayloadSchema,
  ImagePayloadSchema,
  AudioPayloadSchema,
  VideoPayloadSchema,
  BinaryPayloadSchema,
]);

export type PayloadType = z.infer<typeof PayloadSchema>;

export const TPCPEnvelopeSchema = z.object({
  header: MessageHeaderSchema,
  payload: PayloadSchema,
  signature: z.string().nullable().optional()
});
export type TPCPEnvelope = z.infer<typeof TPCPEnvelopeSchema>;
