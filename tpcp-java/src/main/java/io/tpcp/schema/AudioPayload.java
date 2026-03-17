package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Base64;

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
        if (dataBase64 == null) throw new IllegalArgumentException("dataBase64 must not be null");
        if (mimeType == null) throw new IllegalArgumentException("mimeType must not be null");
        try { Base64.getDecoder().decode(dataBase64); } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("dataBase64 is not valid base64", e);
        }
        this.dataBase64 = dataBase64;
        this.mimeType = mimeType;
    }
}
