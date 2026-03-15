package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Carries base64-encoded audio data. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class AudioPayload {
    @JsonProperty("payload_type")
    public String payloadType = "audio";

    @JsonProperty("data_base64")
    public String dataBase64;

    @JsonProperty("mime_type")
    public String mimeType = "audio/wav";

    @JsonProperty("sample_rate")
    public Integer sampleRate;

    @JsonProperty("duration_seconds")
    public Double durationSeconds;

    @JsonProperty("source_model")
    public String sourceModel;

    @JsonProperty("transcript")
    public String transcript;

    public AudioPayload() {}

    public AudioPayload(String dataBase64, String mimeType) {
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
