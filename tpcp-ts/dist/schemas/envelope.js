"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.TPCPEnvelopeSchema = exports.PayloadSchema = exports.CRDTSyncPayloadSchema = exports.VectorEmbeddingPayloadSchema = exports.TextPayloadSchema = exports.MessageHeaderSchema = exports.AgentIdentitySchema = exports.Intent = void 0;
const zod_1 = require("zod");
var Intent;
(function (Intent) {
    Intent["HANDSHAKE"] = "Handshake";
    Intent["TASK_REQUEST"] = "Task_Request";
    Intent["STATE_SYNC"] = "State_Sync";
    Intent["STATE_SYNC_VECTOR"] = "State_Sync_Vector";
    Intent["CRITIQUE"] = "Critique";
    Intent["TERMINATE"] = "Terminate";
})(Intent || (exports.Intent = Intent = {}));
exports.AgentIdentitySchema = zod_1.z.object({
    agent_id: zod_1.z.string().uuid(),
    framework: zod_1.z.string(),
    capabilities: zod_1.z.array(zod_1.z.string()),
    public_key: zod_1.z.string()
});
exports.MessageHeaderSchema = zod_1.z.object({
    message_id: zod_1.z.string().uuid(),
    timestamp: zod_1.z.string().datetime(),
    sender_id: zod_1.z.string().uuid(),
    receiver_id: zod_1.z.string().uuid(),
    intent: zod_1.z.nativeEnum(Intent),
    ttl: zod_1.z.number().int().min(0).default(30)
});
exports.TextPayloadSchema = zod_1.z.object({
    content: zod_1.z.string(),
    language: zod_1.z.string().default("en")
});
exports.VectorEmbeddingPayloadSchema = zod_1.z.object({
    model_id: zod_1.z.string(),
    dimensions: zod_1.z.number().int().positive(),
    vector: zod_1.z.array(zod_1.z.number()),
    raw_text_fallback: zod_1.z.string().nullable().optional()
}).refine(data => {
    if (data.vector.length !== data.dimensions)
        return false;
    const KNOWN_MODELS = {
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
exports.CRDTSyncPayloadSchema = zod_1.z.object({
    crdt_type: zod_1.z.string(),
    state: zod_1.z.record(zod_1.z.string(), zod_1.z.any()),
    vector_clock: zod_1.z.record(zod_1.z.string(), zod_1.z.number().int())
});
exports.PayloadSchema = zod_1.z.union([
    exports.VectorEmbeddingPayloadSchema,
    exports.CRDTSyncPayloadSchema,
    exports.TextPayloadSchema,
    zod_1.z.record(zod_1.z.string(), zod_1.z.any())
]);
exports.TPCPEnvelopeSchema = zod_1.z.object({
    header: exports.MessageHeaderSchema,
    payload: exports.PayloadSchema,
    signature: zod_1.z.string().nullable().optional()
});
