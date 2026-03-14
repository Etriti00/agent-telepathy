package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.JsonNode;

/** Top-level TPCP message container. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class TPCPEnvelope {
    public MessageHeader header;
    public JsonNode payload;
    public String signature;

    public TPCPEnvelope() {}

    public TPCPEnvelope(MessageHeader header, JsonNode payload) {
        this.header = header;
        this.payload = payload;
    }
}
