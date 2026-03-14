package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonValue;

/** TPCP message intent — identifies the purpose of a message. */
public enum Intent {
    CONNECT("Connect"),
    DISCONNECT("Disconnect"),
    HANDSHAKE("Handshake"),
    TASK_REQUEST("TaskRequest"),
    TASK_RESPONSE("TaskResponse"),
    STATE_SYNC("StateSync"),
    MEMORY_SYNC("MemorySync"),
    MEDIA_SHARE("MediaShare"),
    ACK("ACK"),
    NACK("NACK"),
    BROADCAST("Broadcast");

    private final String value;

    Intent(String value) { this.value = value; }

    @JsonValue
    public String getValue() { return value; }
}
