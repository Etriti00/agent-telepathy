package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries base64-encoded image data. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ImagePayload {
    @JsonProperty("payload_type")
    public String payloadType = "image";

    @JsonProperty("data_base64")
    public String dataBase64;

    @JsonProperty("mime_type")
    public String mimeType = "image/png";

    @JsonProperty("width")
    public Integer width;

    @JsonProperty("height")
    public Integer height;

    @JsonProperty("source_model")
    public String sourceModel;

    @JsonProperty("caption")
    public String caption;

    public ImagePayload() {}

    public ImagePayload(String dataBase64, String mimeType) {
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
