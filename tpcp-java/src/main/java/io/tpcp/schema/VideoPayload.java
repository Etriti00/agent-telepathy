package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries base64-encoded video data. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class VideoPayload {
    @JsonProperty("payload_type")
    public String payloadType = "video";

    @JsonProperty("data_base64")
    public String dataBase64;

    @JsonProperty("mime_type")
    public String mimeType = "video/mp4";

    public Integer width;
    public Integer height;

    @JsonProperty("duration_seconds")
    public Double durationSeconds;

    public Double fps;

    @JsonProperty("source_model")
    public String sourceModel;

    public String description;

    public VideoPayload() {}

    public VideoPayload(String dataBase64, String mimeType) {
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
