package io.tpcp;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.tpcp.schema.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SchemaTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void envelopeRoundTrip() throws Exception {
        TextPayload text = new TextPayload("hello TPCP");
        MessageHeader header = new MessageHeader(
            "msg-001", "sender-1", "receiver-1",
            Intent.HANDSHAKE, 1700000000000L, "0.4.0"
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
        assertEquals("\"TaskRequest\"", json);
    }
}
