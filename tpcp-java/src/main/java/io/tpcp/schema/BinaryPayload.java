package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries generic base64-encoded binary data. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class BinaryPayload {
    @JsonProperty("payload_type")
    public String payloadType = "binary";

    @JsonProperty("data_base64")
    public String dataBase64;

    @JsonProperty("mime_type")
    public String mimeType = "application/octet-stream";

    public String filename;

    public String description;

    public BinaryPayload() {}

    public BinaryPayload(String dataBase64, String mimeType) {
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
