package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Present on every TPCP message.
 * Timestamp is an ISO 8601 UTC string to match Python's datetime serialization.
 */
public class MessageHeader {
    @JsonProperty("message_id")
    public String messageId;

    /** ISO 8601 UTC timestamp, e.g. "2026-03-14T10:30:00.000000Z" */
    @JsonProperty("timestamp")
    public String timestamp;

    @JsonProperty("sender_id")
    public String senderId;

    @JsonProperty("receiver_id")
    public String receiverId;

    public Intent intent;

    /** Time-to-live in hops to prevent routing loops. */
    @JsonProperty("ttl")
    public int ttl = 30;

    @JsonProperty("protocol_version")
    public String protocolVersion;

    public MessageHeader() {}

    public MessageHeader(String messageId, String timestamp, String senderId, String receiverId,
                         Intent intent, int ttl, String protocolVersion) {
        this.messageId = messageId;
        this.timestamp = timestamp;
        this.senderId = senderId;
        this.receiverId = receiverId;
        this.intent = intent;
        this.ttl = ttl;
        this.protocolVersion = protocolVersion;
    }
}
