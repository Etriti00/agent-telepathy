import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from tpcp.security.crypto import AgentIdentityManager


# ── WEBHOOK AUTH TESTS ──────────────────────────────────────────────

def test_webhook_auth_rejects_without_token():
    os.environ["TPCP_WEBHOOK_SECRET"] = "test-secret-123"
    try:
        from tpcp.relay.webhook import app
        client = TestClient(app)
        resp = client.post("/webhook/intent", json={"text": "hello"})
        assert resp.status_code == 401
    finally:
        del os.environ["TPCP_WEBHOOK_SECRET"]


def test_webhook_auth_allows_with_valid_token():
    os.environ["TPCP_WEBHOOK_SECRET"] = "test-secret-123"
    try:
        from tpcp.relay.webhook import app
        client = TestClient(app)
        resp = client.post(
            "/webhook/intent",
            json={"text": "hello"},
            headers={"Authorization": "Bearer test-secret-123"}
        )
        # Will be 500 because gateway not configured, but NOT 401
        assert resp.status_code != 401
    finally:
        del os.environ["TPCP_WEBHOOK_SECRET"]


def test_webhook_no_secret_allows_unauthenticated():
    # Ensure TPCP_WEBHOOK_SECRET is not set
    os.environ.pop("TPCP_WEBHOOK_SECRET", None)
    from tpcp.relay.webhook import app
    client = TestClient(app)
    resp = client.post("/webhook/intent", json={"text": "hello"})
    # Should not be 401 (no auth required)
    assert resp.status_code != 401


# ── CRYPTO HARDENING TESTS ──────────────────────────────────────────

def test_key_validation_roundtrip():
    mgr = AgentIdentityManager(auto_save=False)
    # Should not raise — roundtrip succeeds
    assert mgr.get_public_key_string() is not None


def test_corrupted_key_raises_error():
    with pytest.raises(Exception):
        AgentIdentityManager(private_key_bytes=b"not-32-bytes")


def test_signature_verification_rejects_tampered_payload():
    mgr = AgentIdentityManager(auto_save=False)
    payload = {"content": "hello", "payload_type": "text"}
    sig = mgr.sign_payload(payload)
    tampered = {"content": "tampered", "payload_type": "text"}
    assert not AgentIdentityManager.verify_signature(mgr.get_public_key_string(), sig, tampered)
