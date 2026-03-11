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

"""
Cryptographic identity management for TPCP agents using Ed25519 elliptic-curve signatures.
Supports persistent key storage for stable agent identity across restarts.
"""

import base64
import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger(__name__)

# Default path for key storage
DEFAULT_KEY_DIR = Path.home() / ".tpcp"
DEFAULT_KEY_FILE = DEFAULT_KEY_DIR / "identity.key"
ENV_VAR_PRIVATE_KEY = "TPCP_PRIVATE_KEY"


class AgentIdentityManager:
    """
    Manages cryptographic identity using Ed25519 keypairs.
    
    Key resolution order:
    1. Explicit `private_key_bytes` passed to constructor
    2. `TPCP_PRIVATE_KEY` environment variable (base64 encoded raw 32 bytes)
    3. Key file at `key_path` (or default ~/.tpcp/identity.key)
    4. Generate a new keypair (auto-save if `auto_save=True`)
    """
    
    def __init__(
        self, 
        private_key_bytes: Optional[bytes] = None, 
        key_path: Optional[Path] = None,
        auto_save: bool = False
    ):
        self._key_path = key_path or DEFAULT_KEY_FILE
        self._was_loaded = False  # Track whether key was loaded vs generated
        
        if private_key_bytes is not None:
            # Explicit key provided
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            self._was_loaded = True
        elif os.environ.get(ENV_VAR_PRIVATE_KEY):
            # Load from environment variable
            raw_bytes = base64.b64decode(os.environ[ENV_VAR_PRIVATE_KEY])
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
            self._was_loaded = True
            logger.info("Loaded Ed25519 identity from TPCP_PRIVATE_KEY env var.")
        elif self._key_path.exists():
            # Load from file
            self._private_key = self._load_key_from_file(self._key_path)
            self._was_loaded = True
            logger.info(f"Loaded Ed25519 identity from {self._key_path}")
        else:
            # Generate new keypair
            self._private_key = ed25519.Ed25519PrivateKey.generate()
            logger.info("Generated new Ed25519 keypair.")
            if auto_save:
                self.save_key(self._key_path)
            
        self._public_key = self._private_key.public_key()

    @property
    def was_loaded(self) -> bool:
        """True if the key was loaded from persistent storage, False if freshly generated."""
        return self._was_loaded

    def get_public_key_string(self) -> str:
        """Returns the public key encoded as a base64 string."""
        public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(public_bytes).decode('utf-8')

    def get_private_key_bytes(self) -> bytes:
        """Returns the raw 32-byte private key seed for serialization."""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    def save_key(self, path: Optional[Path] = None) -> Path:
        """
        Persists the private key to disk as base64-encoded raw bytes.
        Creates parent directories if they don't exist. Sets file permissions to owner-only.
        Returns the path where the key was saved.
        """
        target = path or self._key_path
        target.parent.mkdir(parents=True, exist_ok=True)
        
        raw_bytes = self.get_private_key_bytes()
        encoded = base64.b64encode(raw_bytes).decode('utf-8')
        
        target.write_text(encoded)
        
        # Set restrictive permissions (owner read/write only) on Unix-like systems
        try:
            os.chmod(target, 0o600)
        except (OSError, AttributeError):
            pass  # Windows doesn't support Unix permissions natively
        
        logger.info(f"Saved Ed25519 identity to {target}")
        return target

    @staticmethod
    def _load_key_from_file(path: Path) -> ed25519.Ed25519PrivateKey:
        """Loads a private key from a base64-encoded file."""
        encoded = path.read_text().strip()
        raw_bytes = base64.b64decode(encoded)
        return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)

    @classmethod
    def from_file(cls, path: Path) -> 'AgentIdentityManager':
        """Factory: create an identity manager from a key file."""
        if not path.exists():
            raise FileNotFoundError(f"Key file not found: {path}")
        return cls(key_path=path)

    @classmethod
    def from_env(cls) -> 'AgentIdentityManager':
        """Factory: create an identity manager from the TPCP_PRIVATE_KEY env var."""
        key_b64 = os.environ.get(ENV_VAR_PRIVATE_KEY)
        if not key_b64:
            raise EnvironmentError(f"Environment variable {ENV_VAR_PRIVATE_KEY} is not set.")
        raw_bytes = base64.b64decode(key_b64)
        return cls(private_key_bytes=raw_bytes)

    def sign_payload(self, payload_dict: Dict[str, Any]) -> str:
        """
        Signs the deterministic JSON representation of a payload dictionary.
        Returns a base64 encoded signature string.
        """
        serialized_payload = json.dumps(payload_dict, separators=(',', ':'), sort_keys=True).encode('utf-8')
        signature = self._private_key.sign(serialized_payload)
        return base64.b64encode(signature).decode('utf-8')

    def sign_bytes(self, data: bytes) -> str:
        """Signs raw bytes directly. Returns a base64 encoded signature."""
        signature = self._private_key.sign(data)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def verify_signature(public_key_str: str, signature_str: str, payload_dict: Dict[str, Any]) -> bool:
        """
        Verifies a base64 signature against a base64 public key for a given payload dictionary.
        Returns True on success, False on failure.
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

    @staticmethod
    def verify_bytes(public_key_str: str, signature_str: str, data: bytes) -> bool:
        """Verifies a signature against raw bytes. Returns True/False."""
        try:
            public_bytes = base64.b64decode(public_key_str)
            signature_bytes = base64.b64decode(signature_str)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            public_key.verify(signature_bytes, data)
            return True
        except (ValueError, InvalidSignature, TypeError):
            return False
