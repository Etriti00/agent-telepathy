package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Base64;

/** Carries generic base64-encoded binary data. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class BinaryPayload {
    @JsonProperty("payload_type")
    public String payloadType = "binary";

    @JsonProperty("data_base64")
    public String dataBase64;

    @JsonProperty("mime_type")
    public String mimeType = "application/octet-stream";

    @JsonProperty("filename")
    public String filename;

    @JsonProperty("description")
    public String description;

    public BinaryPayload() {}

    public BinaryPayload(String dataBase64, String mimeType) {
        if (dataBase64 == null) throw new IllegalArgumentException("dataBase64 must not be null");
        if (mimeType == null) throw new IllegalArgumentException("mimeType must not be null");
        try { Base64.getDecoder().decode(dataBase64); } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("dataBase64 is not valid base64", e);
        }
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
