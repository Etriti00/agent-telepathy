package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries plain text content. */
public class TextPayload {
    @JsonProperty("payload_type")
    public String payloadType = "text";

    @JsonProperty("content")
    public String content;

    @JsonProperty("language")
    public String language = "en";

    public TextPayload() {}

    public TextPayload(String content) {
        if (content == null || content.isEmpty()) throw new IllegalArgumentException("content must not be null or empty");
        this.content = content;
    }

    public TextPayload(String content, String language) {
        if (content == null || content.isEmpty()) throw new IllegalArgumentException("content must not be null or empty");
        this.content = content;
        this.language = language;
    }
}
