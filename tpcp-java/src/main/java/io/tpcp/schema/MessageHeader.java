package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Present on every TPCP message. */
public class MessageHeader {
    @JsonProperty("message_id")
    public String messageId;

    @JsonProperty("sender_id")
    public String senderId;

    @JsonProperty("receiver_id")
    public String receiverId;

    public Intent intent;

    @JsonProperty("timestamp_ms")
    public long timestampMs;

    @JsonProperty("protocol_version")
    public String protocolVersion;

    public MessageHeader() {}

    public MessageHeader(String messageId, String senderId, String receiverId,
                         Intent intent, long timestampMs, String protocolVersion) {
        this.messageId = messageId;
        this.senderId = senderId;
        this.receiverId = receiverId;
        this.intent = intent;
        this.timestampMs = timestampMs;
        this.protocolVersion = protocolVersion;
    }
}
