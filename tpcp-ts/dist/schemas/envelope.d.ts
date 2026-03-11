import { z } from "zod";
export declare enum Intent {
    HANDSHAKE = "Handshake",
    TASK_REQUEST = "Task_Request",
    STATE_SYNC = "State_Sync",
    STATE_SYNC_VECTOR = "State_Sync_Vector",
    CRITIQUE = "Critique",
    TERMINATE = "Terminate"
}
export declare const AgentIdentitySchema: z.ZodObject<{
    agent_id: z.ZodString;
    framework: z.ZodString;
    capabilities: z.ZodArray<z.ZodString>;
    public_key: z.ZodString;
}, z.core.$strip>;
export type AgentIdentity = z.infer<typeof AgentIdentitySchema>;
export declare const MessageHeaderSchema: z.ZodObject<{
    message_id: z.ZodString;
    timestamp: z.ZodString;
    sender_id: z.ZodString;
    receiver_id: z.ZodString;
    intent: z.ZodEnum<typeof Intent>;
    ttl: z.ZodDefault<z.ZodNumber>;
}, z.core.$strip>;
export type MessageHeader = z.infer<typeof MessageHeaderSchema>;
export declare const TextPayloadSchema: z.ZodObject<{
    content: z.ZodString;
    language: z.ZodDefault<z.ZodString>;
}, z.core.$strip>;
export type TextPayload = z.infer<typeof TextPayloadSchema>;
export declare const VectorEmbeddingPayloadSchema: z.ZodObject<{
    model_id: z.ZodString;
    dimensions: z.ZodNumber;
    vector: z.ZodArray<z.ZodNumber>;
    raw_text_fallback: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.core.$strip>;
export type VectorEmbeddingPayload = z.infer<typeof VectorEmbeddingPayloadSchema>;
export declare const CRDTSyncPayloadSchema: z.ZodObject<{
    crdt_type: z.ZodString;
    state: z.ZodRecord<z.ZodString, z.ZodAny>;
    vector_clock: z.ZodRecord<z.ZodString, z.ZodNumber>;
}, z.core.$strip>;
export type CRDTSyncPayload = z.infer<typeof CRDTSyncPayloadSchema>;
export declare const PayloadSchema: z.ZodUnion<readonly [z.ZodObject<{
    model_id: z.ZodString;
    dimensions: z.ZodNumber;
    vector: z.ZodArray<z.ZodNumber>;
    raw_text_fallback: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.core.$strip>, z.ZodObject<{
    crdt_type: z.ZodString;
    state: z.ZodRecord<z.ZodString, z.ZodAny>;
    vector_clock: z.ZodRecord<z.ZodString, z.ZodNumber>;
}, z.core.$strip>, z.ZodObject<{
    content: z.ZodString;
    language: z.ZodDefault<z.ZodString>;
}, z.core.$strip>, z.ZodRecord<z.ZodString, z.ZodAny>]>;
export type PayloadType = z.infer<typeof PayloadSchema>;
export declare const TPCPEnvelopeSchema: z.ZodObject<{
    header: z.ZodObject<{
        message_id: z.ZodString;
        timestamp: z.ZodString;
        sender_id: z.ZodString;
        receiver_id: z.ZodString;
        intent: z.ZodEnum<typeof Intent>;
        ttl: z.ZodDefault<z.ZodNumber>;
    }, z.core.$strip>;
    payload: z.ZodUnion<readonly [z.ZodObject<{
        model_id: z.ZodString;
        dimensions: z.ZodNumber;
        vector: z.ZodArray<z.ZodNumber>;
        raw_text_fallback: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    }, z.core.$strip>, z.ZodObject<{
        crdt_type: z.ZodString;
        state: z.ZodRecord<z.ZodString, z.ZodAny>;
        vector_clock: z.ZodRecord<z.ZodString, z.ZodNumber>;
    }, z.core.$strip>, z.ZodObject<{
        content: z.ZodString;
        language: z.ZodDefault<z.ZodString>;
    }, z.core.$strip>, z.ZodRecord<z.ZodString, z.ZodAny>]>;
    signature: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.core.$strip>;
export type TPCPEnvelope = z.infer<typeof TPCPEnvelopeSchema>;
