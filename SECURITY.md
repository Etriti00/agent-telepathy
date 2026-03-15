# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✅ Active  |
| 0.3.x   | ⚠️ Security fixes only |
| < 0.3.0 | ❌ End of life |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

To report a security vulnerability, please email: **tpcp-security@protonmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

You will receive a response within 48 hours. If the issue is confirmed, we will:
1. Work with you on a fix
2. Coordinate a disclosure timeline (typically 90 days)
3. Credit you in the release notes

## Cryptographic Model

TPCP's security relies on:
- **Ed25519** signatures for message authenticity (via `cryptography` library in Python, `tweetnacl` in TypeScript)
- **Challenge-response authentication** at the A-DNS relay to prevent UUID spoofing
- **TTL enforcement** to prevent message loops
- **Replay protection** via per-message deduplication cache (5-minute TTL window)

If you discover weaknesses in any of these mechanisms, please report privately.
