package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

/** Top-level TPCP message container. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class TPCPEnvelope {
    public MessageHeader header;
    public JsonNode payload;
    public String signature;

    @JsonProperty("ack_info")
    public AckInfo ackInfo;

    @JsonProperty("chunk_info")
    public ChunkInfo chunkInfo;

    public TPCPEnvelope() {}

    public TPCPEnvelope(MessageHeader header, JsonNode payload) {
        this.header = header;
        this.payload = payload;
    }
}
