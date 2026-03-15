package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * TPCP message intent — identifies the purpose of a message.
 * Wire-format values match the canonical Python/TS SDK exactly.
 */
public enum Intent {
    HANDSHAKE("Handshake"),
    TASK_REQUEST("Task_Request"),
    STATE_SYNC("State_Sync"),
    STATE_SYNC_VECTOR("State_Sync_Vector"),
    MEDIA_SHARE("Media_Share"),
    CRITIQUE("Critique"),
    TERMINATE("Terminate"),
    ACK("ACK"),
    NACK("NACK"),
    BROADCAST("Broadcast");

    private final String value;

    Intent(String value) { this.value = value; }

    @JsonValue
    public String getValue() { return value; }
}
