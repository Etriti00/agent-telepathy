use alloc::{string::String, vec::Vec};
use base64::{Engine as _, engine::general_purpose};
use ed25519_dalek::{Signer, Verifier, SigningKey, VerifyingKey, Signature};
use serde_json::Value;

/// Signs a JSON payload with an Ed25519 private key.
/// Returns standard base64-encoded signature (matches Python's base64.b64encode()).
pub fn sign(key: &SigningKey, payload: &[u8]) -> String {
    let sig: Signature = key.sign(payload);
    general_purpose::STANDARD.encode(sig.to_bytes())
}

/// Verifies a standard base64-encoded Ed25519 signature.
pub fn verify(pub_key_b64: &str, payload: &[u8], sig_b64: &str) -> bool {
    let pub_bytes = match general_purpose::STANDARD.decode(pub_key_b64) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sig_bytes = match general_purpose::STANDARD.decode(sig_b64) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let pub_arr: [u8; 32] = match pub_bytes.try_into() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let sig_arr: [u8; 64] = match sig_bytes.try_into() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let vk = match VerifyingKey::from_bytes(&pub_arr) {
        Ok(k) => k,
        Err(_) => return false,
    };
    let sig = Signature::from_bytes(&sig_arr);
    vk.verify(payload, &sig).is_ok()
}

/// Serializes a serde_json Value to canonical JSON with sorted keys.
/// Matches Python's json.dumps(sort_keys=True, separators=(',',':')).
pub fn canonical_json(value: &Value) -> Vec<u8> {
    canonical_json_bytes(value)
}

fn canonical_json_bytes(value: &Value) -> Vec<u8> {
    match value {
        Value::Object(map) => {
            let mut keys: Vec<&str> = map.keys().map(|s| s.as_str()).collect();
            keys.sort_unstable();
            let mut out = Vec::from(b"{" as &[u8]);
            for (i, k) in keys.iter().enumerate() {
                let key_json = serde_json::to_vec(&Value::String((*k).into())).unwrap_or_default();
                out.extend_from_slice(&key_json);
                out.push(b':');
                out.extend_from_slice(&canonical_json_bytes(&map[*k]));
                if i + 1 < keys.len() {
                    out.push(b',');
                }
            }
            out.push(b'}');
            out
        }
        Value::Array(arr) => {
            let mut out = Vec::from(b"[" as &[u8]);
            for (i, item) in arr.iter().enumerate() {
                out.extend_from_slice(&canonical_json_bytes(item));
                if i + 1 < arr.len() {
                    out.push(b',');
                }
            }
            out.push(b']');
            out
        }
        other => serde_json::to_vec(other).unwrap_or_default(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a deterministic SigningKey from a fixed 32-byte seed.
    fn test_signing_key() -> SigningKey {
        let seed: [u8; 32] = [
            1, 2, 3, 4, 5, 6, 7, 8,
            9, 10, 11, 12, 13, 14, 15, 16,
            17, 18, 19, 20, 21, 22, 23, 24,
            25, 26, 27, 28, 29, 30, 31, 32,
        ];
        SigningKey::from_bytes(&seed)
    }

    /// Encode the verifying (public) key as standard base64.
    fn pub_key_b64(sk: &SigningKey) -> String {
        general_purpose::STANDARD.encode(sk.verifying_key().to_bytes())
    }

    #[test]
    fn test_sign_verify_roundtrip() {
        let sk = test_signing_key();
        let pk_b64 = pub_key_b64(&sk);
        let payload = b"hello tpcp";

        let sig = sign(&sk, payload);
        assert!(
            verify(&pk_b64, payload, &sig),
            "valid signature should verify successfully"
        );
    }

    #[test]
    fn test_verify_rejects_tampered() {
        let sk = test_signing_key();
        let pk_b64 = pub_key_b64(&sk);
        let payload = b"original payload";
        let tampered = b"tampered payload";

        let sig = sign(&sk, payload);
        assert!(
            !verify(&pk_b64, tampered, &sig),
            "signature over different payload must not verify"
        );
    }

    #[test]
    fn test_verify_rejects_malformed_public_key() {
        // Public key must be exactly 32 bytes when decoded. This is 16 bytes.
        let short_key = general_purpose::STANDARD.encode([0u8; 16]);
        let payload = b"some payload";
        let sk = test_signing_key();
        let sig = sign(&sk, payload);
        assert!(
            !verify(&short_key, payload, &sig),
            "malformed (wrong length) public key must fail verification"
        );
    }

    #[test]
    fn test_verify_rejects_invalid_base64_signature() {
        let sk = test_signing_key();
        let pk_b64 = pub_key_b64(&sk);
        let payload = b"test";
        assert!(
            !verify(&pk_b64, payload, "not!!!valid===base64"),
            "invalid base64 signature must fail verification"
        );
    }

    #[test]
    fn test_verify_rejects_invalid_base64_public_key() {
        let payload = b"test";
        assert!(
            !verify("also-not-base64!!!", payload, "AAAA"),
            "invalid base64 public key must fail verification"
        );
    }

    #[test]
    fn test_canonical_json_empty_object() {
        let empty: serde_json::Value = serde_json::json!({});
        let result = canonical_json(&empty);
        assert_eq!(core::str::from_utf8(&result).unwrap(), "{}");
    }

    #[test]
    fn test_canonical_json_nested_objects() {
        let nested: serde_json::Value = serde_json::json!({
            "outer": {"z": 1, "a": 2},
            "arr": [3, 2, 1]
        });
        let result = canonical_json(&nested);
        let s = core::str::from_utf8(&result).unwrap();
        // "arr" < "outer" alphabetically
        let pos_arr = s.find("\"arr\"").unwrap();
        let pos_outer = s.find("\"outer\"").unwrap();
        assert!(pos_arr < pos_outer, "keys must be sorted: arr before outer");
        // Nested keys should also be sorted: "a" < "z"
        let pos_a = s.find("\"a\"").unwrap();
        let pos_z = s.find("\"z\"").unwrap();
        assert!(pos_a < pos_z, "nested keys must be sorted: a before z");
    }

    #[test]
    fn test_canonical_json_deterministic() {
        // Two JSON objects with the same keys in different insertion order.
        let a: Value = serde_json::json!({"z": 1, "a": 2, "m": 3});
        let b: Value = serde_json::json!({"m": 3, "z": 1, "a": 2});

        let bytes_a = canonical_json(&a);
        let bytes_b = canonical_json(&b);

        assert_eq!(
            bytes_a, bytes_b,
            "canonical_json must produce identical output regardless of key insertion order"
        );
        // Keys must appear sorted: "a" < "m" < "z"
        let s = core::str::from_utf8(&bytes_a).expect("valid UTF-8");
        let pos_a = s.find("\"a\"").unwrap();
        let pos_m = s.find("\"m\"").unwrap();
        let pos_z = s.find("\"z\"").unwrap();
        assert!(pos_a < pos_m && pos_m < pos_z, "keys must be sorted alphabetically");
    }
}
