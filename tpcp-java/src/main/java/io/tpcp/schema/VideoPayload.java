package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Base64;

/** Carries base64-encoded video data. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class VideoPayload {
    @JsonProperty("payload_type")
    public String payloadType = "video";

    @JsonProperty("data_base64")
    public String dataBase64;

    @JsonProperty("mime_type")
    public String mimeType = "video/mp4";

    @JsonProperty("width")
    public Integer width;

    @JsonProperty("height")
    public Integer height;

    @JsonProperty("duration_seconds")
    public Double durationSeconds;

    @JsonProperty("fps")
    public Double fps;

    @JsonProperty("source_model")
    public String sourceModel;

    @JsonProperty("description")
    public String description;

    public VideoPayload() {}

    public VideoPayload(String dataBase64, String mimeType) {
        if (dataBase64 == null) throw new IllegalArgumentException("dataBase64 must not be null");
        try { Base64.getDecoder().decode(dataBase64); } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("dataBase64 is not valid base64", e);
        }
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
