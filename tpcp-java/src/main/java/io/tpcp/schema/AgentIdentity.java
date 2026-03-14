package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Describes a TPCP agent. */
public class AgentIdentity {
    @JsonProperty("agent_id")
    public String agentId;

    @JsonProperty("agent_type")
    public String agentType;

    @JsonProperty("public_key_b64")
    public String publicKeyB64;

    public AgentIdentity() {}

    public AgentIdentity(String agentId, String agentType, String publicKeyB64) {
        this.agentId = agentId;
        this.agentType = agentType;
        this.publicKeyB64 = publicKeyB64;
    }
}
