package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

/** Carries conflict-free replicated data type state. */
public class CRDTSyncPayload {
    @JsonProperty("payload_type")
    public String payloadType = "crdt_sync";

    @JsonProperty("crdt_type")
    public String crdtType;

    public Map<String, Object> state;

    @JsonProperty("vector_clock")
    public Map<String, Integer> vectorClock;

    public CRDTSyncPayload() {}

    public CRDTSyncPayload(String crdtType, Map<String, Object> state, Map<String, Integer> vectorClock) {
        this.crdtType = crdtType;
        this.state = state;
        this.vectorClock = vectorClock;
    }
}
