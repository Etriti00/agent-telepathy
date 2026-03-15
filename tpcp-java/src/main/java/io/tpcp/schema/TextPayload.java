package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries plain text content. */
public class TextPayload {
    @JsonProperty("payload_type")
    public String payloadType = "text";

    public String content;

    public String language = "en";

    public TextPayload() {}

    public TextPayload(String content) {
        this.content = content;
    }

    public TextPayload(String content, String language) {
        this.content = content;
        this.language = language;
    }
}
