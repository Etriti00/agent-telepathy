package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries plain text content. */
public class TextPayload {
    @JsonProperty("payload_type")
    public String payloadType = "text";

    public String content;

    public TextPayload() {}

    public TextPayload(String content) { this.content = content; }
}
