package io.tpcp.core;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.tpcp.schema.*;
import org.junit.jupiter.api.Test;

import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

class TPCPNodeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void handlerRegistrationAndDispatch() throws Exception {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("Java-Test");
        TPCPNode node = new TPCPNode(identity, mgr);

        AtomicReference<TPCPEnvelope> received = new AtomicReference<>();
        node.registerHandler(Intent.TASK_REQUEST, received::set);

        // Simulate dispatch
        MessageHeader header = new MessageHeader(
            "msg-1", "2026-03-17T00:00:00Z", "sender-1", identity.agentId,
            Intent.TASK_REQUEST, 30, "0.4.0"
        );
        TPCPEnvelope env = new TPCPEnvelope(header, MAPPER.valueToTree(new TextPayload("test task")));
        // Access dispatch via reflection since it's private
        var dispatch = TPCPNode.class.getDeclaredMethod("dispatch", TPCPEnvelope.class);
        dispatch.setAccessible(true);
        dispatch.invoke(node, env);

        assertNotNull(received.get(), "Handler should have been called");
        assertEquals("msg-1", received.get().header.messageId);
        node.stop();
    }

    @Test
    void unhandledIntentGoesToDLQ() throws Exception {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("Java-Test");
        TPCPNode node = new TPCPNode(identity, mgr);

        // Don't register any handler for CRITIQUE
        MessageHeader header = new MessageHeader(
            "msg-dlq-1", "2026-03-17T00:00:00Z", "sender-1", identity.agentId,
            Intent.CRITIQUE, 30, "0.4.0"
        );
        TPCPEnvelope env = new TPCPEnvelope(header, MAPPER.valueToTree(new TextPayload("feedback")));

        var dispatch = TPCPNode.class.getDeclaredMethod("dispatch", TPCPEnvelope.class);
        dispatch.setAccessible(true);
        dispatch.invoke(node, env);

        var drained = node.dlq.drain();
        assertEquals(1, drained.size(), "Unhandled message should be in DLQ");
        assertEquals("msg-dlq-1", drained.get(0).header.messageId);
        node.stop();
    }

    @Test
    void sendMessageToUnconnectedPeerThrows() {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("Java-Test");
        TPCPNode node = new TPCPNode(identity, mgr);

        assertThrows(IllegalStateException.class, () ->
            node.sendMessage("ws://localhost:9999", "target-id", Intent.TASK_REQUEST,
                MAPPER.valueToTree(new TextPayload("hello")))
        );
        node.stop();
    }

    @Test
    void connectRejectsNonWsUrl() {
        IdentityManager mgr = new IdentityManager();
        AgentIdentity identity = mgr.createIdentity("Java-Test");
        TPCPNode node = new TPCPNode(identity, mgr);

        assertThrows(IllegalArgumentException.class, () ->
            node.connect("http://example.com")
        );
        node.stop();
    }
}
