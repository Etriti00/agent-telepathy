package io.tpcp.core;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import io.tpcp.schema.AgentIdentity;
import org.bouncycastle.crypto.AsymmetricCipherKeyPair;
import org.bouncycastle.crypto.generators.Ed25519KeyPairGenerator;
import org.bouncycastle.crypto.params.Ed25519KeyGenerationParameters;
import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters;
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters;
import org.bouncycastle.crypto.signers.Ed25519Signer;

import java.security.SecureRandom;
import java.util.Base64;
import java.util.TreeMap;
import java.util.UUID;

/**
 * Manages Ed25519 identity for TPCP agents.
 *
 * <p>Uses BouncyCastle for Ed25519 signing/verification.
 * Canonical JSON uses sorted keys to match Python's
 * {@code json.dumps(sort_keys=True, separators=(',',':'))}.
 */
public class IdentityManager {
    private final Ed25519PrivateKeyParameters privateKey;
    private final Ed25519PublicKeyParameters publicKey;
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true)
            .configure(JsonGenerator.Feature.ESCAPE_NON_ASCII, true);

    /** Generates a fresh Ed25519 keypair. */
    public IdentityManager() {
        Ed25519KeyPairGenerator gen = new Ed25519KeyPairGenerator();
        gen.init(new Ed25519KeyGenerationParameters(new SecureRandom()));
        AsymmetricCipherKeyPair pair = gen.generateKeyPair();
        this.privateKey = (Ed25519PrivateKeyParameters) pair.getPrivate();
        this.publicKey = (Ed25519PublicKeyParameters) pair.getPublic();
    }

    /** Creates an AgentIdentity for this manager's public key. */
    public AgentIdentity createIdentity(String framework) {
        String pubB64 = Base64.getEncoder().encodeToString(publicKey.getEncoded());
        return new AgentIdentity(UUID.randomUUID().toString(), framework, pubB64);
    }

    /**
     * Signs a JSON payload.
     * Returns standard base64-encoded signature (matches Python's base64.b64encode()).
     */
    public String sign(JsonNode payload) {
        try {
            byte[] canonical = toCanonicalJson(payload);
            Ed25519Signer signer = new Ed25519Signer();
            signer.init(true, privateKey);
            signer.update(canonical, 0, canonical.length);
            byte[] sig = signer.generateSignature();
            return Base64.getEncoder().encodeToString(sig);
        } catch (Exception e) {
            throw new RuntimeException("Sign failed", e);
        }
    }

    /** Verifies a standard base64-encoded Ed25519 signature against a JSON payload. */
    public static boolean verify(String pubKeyB64, JsonNode payload, String sigB64) {
        try {
            byte[] pubBytes = Base64.getDecoder().decode(pubKeyB64);
            byte[] sigBytes = Base64.getDecoder().decode(sigB64);
            byte[] canonical = toCanonicalJson(payload);
            Ed25519PublicKeyParameters pk = new Ed25519PublicKeyParameters(pubBytes, 0);
            Ed25519Signer verifier = new Ed25519Signer();
            verifier.init(false, pk);
            verifier.update(canonical, 0, canonical.length);
            return verifier.verifySignature(sigBytes);
        } catch (Exception e) {
            return false;
        }
    }

    /** Serializes a JsonNode to canonical JSON (sorted keys, compact). */
    public static byte[] toCanonicalJson(JsonNode node) throws Exception {
        // Convert to TreeMap-backed structure via generic deserialization + sorted re-serialization
        Object generic = MAPPER.treeToValue(node, Object.class);
        String sorted = MAPPER.writeValueAsString(sortedCopy(generic));
        return sorted.getBytes(java.nio.charset.StandardCharsets.UTF_8);
    }

    @SuppressWarnings("unchecked")
    private static Object sortedCopy(Object obj) {
        if (obj instanceof java.util.Map) {
            TreeMap<String, Object> sorted = new TreeMap<>();
            ((java.util.Map<String, Object>) obj).forEach((k, v) -> sorted.put(k, sortedCopy(v)));
            return sorted;
        } else if (obj instanceof java.util.List) {
            java.util.List<Object> list = new java.util.ArrayList<>();
            ((java.util.List<Object>) obj).forEach(item -> list.add(sortedCopy(item)));
            return list;
        }
        return obj;
    }

    public String getPublicKeyB64() {
        return Base64.getEncoder().encodeToString(publicKey.getEncoded());
    }
}
