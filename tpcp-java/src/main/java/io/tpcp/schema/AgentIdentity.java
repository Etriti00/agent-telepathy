package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.ArrayList;

/**
 * Describes a TPCP agent.
 * Field names match the canonical Python SDK (public_key, framework, capabilities, modality).
 */
public class AgentIdentity {
    @JsonProperty("agent_id")
    public String agentId;

    @JsonProperty("framework")
    public String framework;

    @JsonProperty("capabilities")
    public List<String> capabilities = new ArrayList<>();

    @JsonProperty("public_key")
    public String publicKey;

    @JsonProperty("modality")
    public List<String> modality = new ArrayList<>(List.of("text"));

    public AgentIdentity() {}

    public AgentIdentity(String agentId, String framework, String publicKey) {
        this.agentId = agentId;
        this.framework = framework;
        this.publicKey = publicKey;
    }
}
