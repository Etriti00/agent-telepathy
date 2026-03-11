# Copyright (c) 2026 Principal Systems Architect
# This file is part of TPCP.
# 
# TPCP is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# TPCP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with TPCP. If not, see <https://www.gnu.org/licenses/>.
# 
# For commercial licensing inquiries, see COMMERCIAL_LICENSE.md

import base64
import json
from typing import Any, Dict, Tuple, Optional
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

class AgentIdentityManager:
    """Manages cryptographic identity using Ed25519 keypairs."""
    
    def __init__(self, private_key_bytes: Optional[bytes] = None):
        """
        Initializes the manager. If no private key is provided, a new keypair is generated.
        """
        if private_key_bytes is None:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
        else:
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            
        self._public_key = self._private_key.public_key()

    def get_public_key_string(self) -> str:
        """Returns the public key encoded as a base64 string."""
        public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(public_bytes).decode('utf-8')

    def sign_payload(self, payload_dict: Dict[str, Any]) -> str:
        """
        Signs the deterministic JSON representation of a payload dictionary.
        Returns a base64 encoded signature string.
        """
        # Ensure deterministic serialization
        serialized_payload = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True).encode('utf-8')
        signature = self._private_key.sign(serialized_payload)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def verify_signature(public_key_str: str, signature_str: str, payload_dict: Dict[str, Any]) -> bool:
        """
        Verifies a base64 signature against a base64 public key for a given payload dictionary.
        Raises InvalidSignature if it fails, or returns True on success.
        """
        try:
            public_bytes = base64.b64decode(public_key_str)
            signature_bytes = base64.b64decode(signature_str)
            
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            serialized_payload = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True).encode('utf-8')
            
            public_key.verify(signature_bytes, serialized_payload)
            return True
        except (ValueError, InvalidSignature, TypeError):
            return False
