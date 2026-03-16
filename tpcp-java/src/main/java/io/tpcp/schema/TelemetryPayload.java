package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/** Industrial IoT sensor data payload. */
public class TelemetryPayload {
    @JsonProperty("payload_type")
    public String payloadType = "telemetry";

    @JsonProperty("sensor_id")
    public String sensorId;

    @JsonProperty("unit")
    public String unit;

    @JsonProperty("readings")
    public List<TelemetryReading> readings;

    @JsonProperty("source_protocol")
    public String sourceProtocol;

    public TelemetryPayload() {}

    public TelemetryPayload(String sensorId, String unit,
                            List<TelemetryReading> readings, String sourceProtocol) {
        if (sensorId == null || sensorId.isEmpty()) throw new IllegalArgumentException("sensorId must not be null or empty");
        if (unit == null || unit.isEmpty()) throw new IllegalArgumentException("unit must not be null or empty");
        if (sourceProtocol == null || sourceProtocol.isEmpty()) throw new IllegalArgumentException("sourceProtocol must not be null or empty");
        this.sensorId = sensorId;
        this.unit = unit;
        this.readings = readings;
        this.sourceProtocol = sourceProtocol;
    }
}
