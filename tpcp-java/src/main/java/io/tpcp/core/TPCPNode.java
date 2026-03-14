package io.tpcp.core;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.tpcp.Constants;
import io.tpcp.schema.AgentIdentity;
import io.tpcp.schema.Intent;
import io.tpcp.schema.MessageHeader;
import io.tpcp.schema.TPCPEnvelope;
import okhttp3.*;

import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;

/**
 * TPCP agent node backed by OkHttp WebSocket.
 *
 * <p>Usage:
 * <pre>{@code
 *   IdentityManager mgr = new IdentityManager();
 *   AgentIdentity identity = mgr.createIdentity("Java");
 *   TPCPNode node = new TPCPNode(identity, mgr);
 *   node.registerHandler(Intent.TASK_REQUEST, env -> System.out.println("Task: " + env.payload));
 *   node.connect("ws://other-agent:8765").join();
 *   node.sendMessage("ws://other-agent:8765", Intent.HANDSHAKE,
 *       mapper.valueToTree(new TextPayload("hello")));
 * }</pre>
 */
public class TPCPNode {
    public final AgentIdentity identity;
    public final LWWMap memory = new LWWMap();
    public final DLQ dlq = new DLQ();

    private final IdentityManager identityManager;
    private final OkHttpClient httpClient;
    private final ConcurrentHashMap<Intent, Consumer<TPCPEnvelope>> handlers = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, WebSocket> peers = new ConcurrentHashMap<>();
    /** Maps agent_id → base64 public key for inbound signature verification. */
    private final ConcurrentHashMap<String, String> peerKeys = new ConcurrentHashMap<>();
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public TPCPNode(AgentIdentity identity, IdentityManager identityManager) {
        this.identity = identity;
        this.identityManager = identityManager;
        this.httpClient = new OkHttpClient();
    }

    /** Registers a handler for a specific intent. */
    public void registerHandler(Intent intent, Consumer<TPCPEnvelope> handler) {
        handlers.put(intent, handler);
    }

    /** Registers a known peer's public key for inbound signature verification. */
    public void registerPeerKey(String agentId, String pubKeyB64) {
        peerKeys.put(agentId, pubKeyB64);
    }

    /** Connects to a WebSocket URL asynchronously. */
    public CompletableFuture<Void> connect(String url) {
        CompletableFuture<Void> future = new CompletableFuture<>();
        Request request = new Request.Builder().url(url).build();
        httpClient.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket ws, Response response) {
                peers.put(url, ws);
                future.complete(null);
            }

            @Override
            public void onMessage(WebSocket ws, String text) {
                try {
                    TPCPEnvelope env = MAPPER.readValue(text, TPCPEnvelope.class);
                    // Verify inbound signature if we have a registered key for this sender.
                    if (env.signature != null && !env.signature.isEmpty()
                            && env.header != null && env.header.senderId != null) {
                        String pubKey = peerKeys.get(env.header.senderId);
                        if (pubKey != null && !IdentityManager.verify(pubKey, env.payload, env.signature)) {
                            // Drop messages with invalid signatures from known peers.
                            return;
                        }
                    }
                    dispatch(env);
                } catch (Exception e) {
                    // log and ignore malformed envelopes
                }
            }

            @Override
            public void onFailure(WebSocket ws, Throwable t, Response response) {
                future.completeExceptionally(t);
            }
        });
        return future;
    }

    /** Sends a message to a peer by URL. */
    public void sendMessage(String peerUrl, Intent intent, JsonNode payload) {
        WebSocket ws = peers.get(peerUrl);
        if (ws == null) throw new IllegalStateException("Not connected to: " + peerUrl);
        try {
            MessageHeader header = new MessageHeader(
                UUID.randomUUID().toString(),
                Instant.now().toString(),
                identity.agentId,
                peerUrl,
                intent,
                30,
                Constants.PROTOCOL_VERSION
            );
            TPCPEnvelope envelope = new TPCPEnvelope(header, payload);
            if (identityManager != null) {
                envelope.signature = identityManager.sign(payload);
            }
            ws.send(MAPPER.writeValueAsString(envelope));
        } catch (Exception e) {
            throw new RuntimeException("sendMessage failed", e);
        }
    }

    /** Shuts down the HTTP client and closes all peer connections. */
    public void stop() {
        peers.values().forEach(ws -> ws.close(1000, "shutdown"));
        peers.clear();
        httpClient.dispatcher().executorService().shutdown();
    }

    private void dispatch(TPCPEnvelope env) {
        Consumer<TPCPEnvelope> handler = handlers.get(env.header.intent);
        if (handler != null) {
            handler.accept(env);
        } else {
            dlq.enqueue(env);
        }
    }
}
