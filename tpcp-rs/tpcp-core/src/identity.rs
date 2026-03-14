use alloc::{string::String, vec::Vec};
use base64::{Engine as _, engine::general_purpose};
use ed25519_dalek::{Signer, Verifier, SigningKey, VerifyingKey, Signature};
use serde_json::Value;

/// Signs a JSON payload with an Ed25519 private key.
/// Returns base64url-encoded signature.
pub fn sign(key: &SigningKey, payload: &[u8]) -> String {
    let sig: Signature = key.sign(payload);
    general_purpose::URL_SAFE_NO_PAD.encode(sig.to_bytes())
}

/// Verifies a base64url-encoded Ed25519 signature.
pub fn verify(pub_key_b64: &str, payload: &[u8], sig_b64: &str) -> bool {
    let pub_bytes = match general_purpose::STANDARD.decode(pub_key_b64) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sig_bytes = match general_purpose::URL_SAFE_NO_PAD.decode(sig_b64) {
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
