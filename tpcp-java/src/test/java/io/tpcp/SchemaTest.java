package io.tpcp;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.tpcp.schema.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.assertThrows;

class SchemaTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void envelopeRoundTrip() throws Exception {
        TextPayload text = new TextPayload("hello TPCP");
        MessageHeader header = new MessageHeader(
            "msg-001", "2026-03-14T00:00:00Z", "sender-1", "receiver-1",
            Intent.HANDSHAKE, 30, "0.4.0"
        );
        TPCPEnvelope original = new TPCPEnvelope(header, MAPPER.valueToTree(text));

        String json = MAPPER.writeValueAsString(original);
        TPCPEnvelope roundTripped = MAPPER.readValue(json, TPCPEnvelope.class);

        assertEquals(original.header.messageId, roundTripped.header.messageId);
        assertEquals(original.header.intent, roundTripped.header.intent);
        assertEquals("hello TPCP",
            roundTripped.payload.get("content").asText());
    }

    @Test
    void intentSerializesCorrectly() throws Exception {
        String json = MAPPER.writeValueAsString(Intent.TASK_REQUEST);
        assertEquals("\"Task_Request\"", json);
    }

    @Test
    void intentHasExactlyTenValues() {
        Intent[] values = Intent.values();
        assertEquals(10, values.length,
            "Intent enum must contain exactly 10 values after removing TASK_RESPONSE and MEMORY_SYNC");
    }

    @Test
    void textPayloadDefaultLanguageIsEn() {
        TextPayload tp = new TextPayload("hello");
        assertEquals("en", tp.language,
            "TextPayload.language must default to \"en\"");
    }

    @Test
    void textPayloadLanguageOverride() throws Exception {
        TextPayload tp = new TextPayload("bonjour", "fr");
        String json = MAPPER.writeValueAsString(tp);
        assertTrue(json.contains("\"language\":\"fr\""));

        TextPayload deserialized = MAPPER.readValue(json, TextPayload.class);
        assertEquals("fr", deserialized.language);
    }

    @Test
    void ackInfoRoundTrip() throws Exception {
        AckInfo original = new AckInfo("msg-042");
        String json = MAPPER.writeValueAsString(original);

        assertTrue(json.contains("\"acked_message_id\":\"msg-042\""),
            "AckInfo must serialize acked_message_id with snake_case");

        AckInfo deserialized = MAPPER.readValue(json, AckInfo.class);
        assertEquals("msg-042", deserialized.ackedMessageId);
    }

    @Test
    void chunkInfoRoundTrip() throws Exception {
        ChunkInfo original = new ChunkInfo(2, 5, "xfer-99");
        String json = MAPPER.writeValueAsString(original);

        assertTrue(json.contains("\"chunk_index\":2"));
        assertTrue(json.contains("\"total_chunks\":5"));
        assertTrue(json.contains("\"transfer_id\":\"xfer-99\""));

        ChunkInfo deserialized = MAPPER.readValue(json, ChunkInfo.class);
        assertEquals(2, deserialized.chunkIndex);
        assertEquals(5, deserialized.totalChunks);
        assertEquals("xfer-99", deserialized.transferId);
    }

    @Test
    void envelopeWithAckInfoAndChunkInfo() throws Exception {
        MessageHeader header = new MessageHeader(
            "msg-ack-1", "2026-03-15T00:00:00Z", "agent-a", "agent-b",
            Intent.ACK, 30, "0.4.0"
        );
        TPCPEnvelope envelope = new TPCPEnvelope(header, null);
        envelope.ackInfo = new AckInfo("msg-original-1");
        envelope.chunkInfo = new ChunkInfo(0, 3, "xfer-100");

        String json = MAPPER.writeValueAsString(envelope);
        assertTrue(json.contains("\"ack_info\""));
        assertTrue(json.contains("\"chunk_info\""));

        TPCPEnvelope deserialized = MAPPER.readValue(json, TPCPEnvelope.class);
        assertNotNull(deserialized.ackInfo);
        assertEquals("msg-original-1", deserialized.ackInfo.ackedMessageId);
        assertNotNull(deserialized.chunkInfo);
        assertEquals(0, deserialized.chunkInfo.chunkIndex);
        assertEquals(3, deserialized.chunkInfo.totalChunks);
        assertEquals("xfer-100", deserialized.chunkInfo.transferId);
    }

    @Test
    void textPayloadRejectsNullContent() {
        assertThrows(IllegalArgumentException.class,
            () -> new TextPayload(null, "en"));
    }

    @Test
    void vectorEmbeddingRejectsZeroDimensions() {
        assertThrows(IllegalArgumentException.class,
            () -> new VectorEmbeddingPayload("model", 0, java.util.List.of()));
    }

    @Test
    void telemetryRejectsEmptySensorId() {
        assertThrows(IllegalArgumentException.class,
            () -> new TelemetryPayload("", "rpm", java.util.List.of(), "opcua"));
    }

    @Test
    void telemetryPayloadRoundTrip() throws Exception {
        TelemetryReading reading = new TelemetryReading(98.6, 1710000000000L, "good");
        TelemetryPayload original = new TelemetryPayload(
            "sensor-01", "celsius",
            java.util.List.of(reading),
            "opcua"
        );

        String json = MAPPER.writeValueAsString(original);

        assertTrue(json.contains("\"sensor_id\":\"sensor-01\""));
        assertTrue(json.contains("\"unit\":\"celsius\""));
        assertTrue(json.contains("\"source_protocol\":\"opcua\""));
        assertTrue(json.contains("\"payload_type\":\"telemetry\""));

        TelemetryPayload deserialized = MAPPER.readValue(json, TelemetryPayload.class);
        assertEquals("sensor-01", deserialized.sensorId);
        assertEquals("celsius", deserialized.unit);
        assertEquals("opcua", deserialized.sourceProtocol);
        assertEquals("telemetry", deserialized.payloadType);
        assertNotNull(deserialized.readings);
        assertEquals(1, deserialized.readings.size());

        TelemetryReading deserializedReading = deserialized.readings.get(0);
        assertEquals(98.6, deserializedReading.value, 1e-9);
        assertEquals(1710000000000L, deserializedReading.timestampMs);
        assertEquals("good", deserializedReading.quality);
    }

    @Test
    void telemetryPayloadRejectsNullUnit() {
        assertThrows(IllegalArgumentException.class,
            () -> new TelemetryPayload("sensor-01", null, java.util.List.of(), "opcua"));
    }

    @Test
    void telemetryReadingSerializesNullQualityAsAbsent() throws Exception {
        TelemetryReading reading = new TelemetryReading(42.0, 1710000000001L, null);
        String json = MAPPER.writeValueAsString(reading);
        assertFalse(json.contains("\"quality\""),
            "null quality must be omitted from JSON due to @JsonInclude(NON_NULL)");
    }
}
