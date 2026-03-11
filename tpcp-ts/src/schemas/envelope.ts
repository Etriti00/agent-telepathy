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
  CRITIQUE = "Critique",
  TERMINATE = "Terminate"
}

export const AgentIdentitySchema = z.object({
  agent_id: z.string().uuid(),
  framework: z.string(),
  capabilities: z.array(z.string()),
  public_key: z.string()
});
export type AgentIdentity = z.infer<typeof AgentIdentitySchema>;

export const MessageHeaderSchema = z.object({
  message_id: z.string().uuid(),
  timestamp: z.string().datetime(),
  sender_id: z.string().uuid(),
  receiver_id: z.string().uuid(),
  intent: z.nativeEnum(Intent),
  ttl: z.number().int().min(0).default(30)
});
export type MessageHeader = z.infer<typeof MessageHeaderSchema>;

export const TextPayloadSchema = z.object({
  content: z.string(),
  language: z.string().default("en")
});
export type TextPayload = z.infer<typeof TextPayloadSchema>;

export const VectorEmbeddingPayloadSchema = z.object({
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
  crdt_type: z.string(),
  state: z.record(z.string(), z.any()),
  vector_clock: z.record(z.string(), z.number().int())
});
export type CRDTSyncPayload = z.infer<typeof CRDTSyncPayloadSchema>;

export const PayloadSchema = z.union([
  VectorEmbeddingPayloadSchema,
  CRDTSyncPayloadSchema,
  TextPayloadSchema,
  z.record(z.string(), z.any())
]);

export type PayloadType = z.infer<typeof PayloadSchema>;

export const TPCPEnvelopeSchema = z.object({
  header: MessageHeaderSchema,
  payload: PayloadSchema,
  signature: z.string().nullable().optional()
});
export type TPCPEnvelope = z.infer<typeof TPCPEnvelopeSchema>;
