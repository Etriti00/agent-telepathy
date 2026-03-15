package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Acknowledgement metadata referencing the message being acknowledged. */
public class AckInfo {
    @JsonProperty("acked_message_id")
    public String ackedMessageId;

    public AckInfo() {}

    public AckInfo(String ackedMessageId) {
        this.ackedMessageId = ackedMessageId;
    }
}
