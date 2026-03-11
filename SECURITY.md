# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Active  |

## Reporting a Vulnerability

**Please do not open a public GitHub Issue for security vulnerabilities.**

If you discover a security vulnerability — particularly relating to the Ed25519 cryptographic trust layer, signature verification bypass, or the A-DNS relay — please disclose it responsibly by emailing the maintainer directly.

We aim to acknowledge all reports within **48 hours** and release a patch within **7 days** for critical issues.

## Security Model

TPCP uses **Ed25519 elliptic-curve signatures** to authenticate every message:
- Each node generates a keypair at startup.
- All outbound `TPCPEnvelope`s are signed with the sender's private key.
- Inbound envelopes are rejected if the signature fails verification against the sender's registered public key.

**Current known limitations:**
- The A-DNS Relay does not yet perform challenge-response identity validation (planned for v0.2.0).
- Private keys are ephemeral (in-memory only) — there is no built-in key persistence or rotation mechanism yet.
