import json
import sys
import os

# Ensure tpcp is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../tpcp')))

from tpcp.security.crypto import AgentIdentityManager

def generate():
    m = AgentIdentityManager()
    pub = m.get_public_key_string()
    payload = {"cross_lang": True, "test": 123}
    sig = m.sign_payload(payload)
    print(json.dumps({"pub": pub, "sig": sig, "payload": payload}))

if __name__ == "__main__":
    generate()
