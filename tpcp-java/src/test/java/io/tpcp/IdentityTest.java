package io.tpcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.tpcp.core.IdentityManager;
import io.tpcp.schema.AgentIdentity;
import io.tpcp.schema.TextPayload;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class IdentityTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void signAndVerify() throws Exception {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("test-agent");

        JsonNode payload = MAPPER.valueToTree(new TextPayload("sign me"));
        String sig = mgr.sign(payload);

        assertTrue(IdentityManager.verify(identity.publicKeyB64, payload, sig),
            "valid signature should verify");
    }

    @Test
    void tamperedPayloadFailsVerification() throws Exception {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("test-agent");

        JsonNode payload = MAPPER.valueToTree(new TextPayload("original"));
        String sig = mgr.sign(payload);

        JsonNode tampered = MAPPER.valueToTree(new TextPayload("tampered"));
        assertFalse(IdentityManager.verify(identity.publicKeyB64, tampered, sig),
            "tampered payload should fail verification");
    }

    @Test
    void identityHasNonEmptyPublicKey() {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("my-agent");
        assertFalse(identity.publicKeyB64.isEmpty());
        assertEquals("my-agent", identity.agentType);
    }
}
