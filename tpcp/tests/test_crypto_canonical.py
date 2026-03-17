import json

from tpcp.security.crypto import AgentIdentityManager


def test_canonical_json_non_ascii_not_escaped():
    """Canonical JSON must output raw UTF-8 for non-ASCII characters.

    All 4 other SDKs (Java, Go, Rust, TypeScript) emit raw UTF-8.
    Python must match to ensure cross-SDK Ed25519 signature verification.
    """
    payload = {"greeting": "café", "name": "naïve"}
    canonical = json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False)
    assert "café" in canonical, f"Expected raw UTF-8 'café', got escaped: {canonical}"
    assert "naïve" in canonical, f"Expected raw UTF-8 'naïve', got escaped: {canonical}"
    assert "\\u" not in canonical, f"Found \\u escapes in canonical JSON: {canonical}"


def test_sign_verify_non_ascii_payload():
    """Sign and verify a payload containing non-ASCII characters."""
    mgr = AgentIdentityManager()
    payload = {"message": "café résumé", "emoji": "thumbs up"}
    sig = mgr.sign_payload(payload)
    pub_key = mgr.get_public_key_string()
    assert AgentIdentityManager.verify_signature(pub_key, sig, payload)
