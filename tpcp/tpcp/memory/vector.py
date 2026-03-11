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

from typing import Dict, List, Optional
from uuid import UUID

class VectorBank:
    """
    A simple in-memory vector database acting as a buffer for semantic memory fragments
    shared transversally between agents.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        # Maps an incoming message ID (or custom chunk ID) to a float array and metadata
        self._embeddings: Dict[UUID, dict] = {}

    def store_vector(self, payload_id: UUID, vector: List[float], model_id: str, raw_text: Optional[str] = None) -> None:
        """Saves a semantic chunk."""
        self._embeddings[payload_id] = {
            "vector": vector,
            "model_id": model_id,
            "raw_text_fallback": raw_text
        }

    def get_vector(self, payload_id: UUID) -> Optional[dict]:
        """Retrieves a stored embedding and its metadata."""
        return self._embeddings.get(payload_id)

    @property
    def total_vectors(self) -> int:
        return len(self._embeddings)
