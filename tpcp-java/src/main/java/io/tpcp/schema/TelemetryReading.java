package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Single sensor reading. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class TelemetryReading {
    @JsonProperty("value")
    public double value;

    @JsonProperty("timestamp_ms")
    public long timestampMs;

    @JsonProperty("quality")
    public String quality;

    public TelemetryReading() {}

    public TelemetryReading(double value, long timestampMs, String quality) {
        this.value = value;
        this.timestampMs = timestampMs;
        this.quality = quality;
    }
}
