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
In-memory vector database for semantic memory fragments shared between agents.
Supports storage, retrieval, and cosine similarity search.
"""

import math
from typing import Dict, List, Optional, Tuple
from uuid import UUID


class VectorBank:
    """
    A simple in-memory vector database acting as a buffer for semantic memory fragments
    shared transversally between agents. Supports cosine similarity search for semantic
    retrieval across the agent swarm's collective knowledge.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._embeddings: Dict[UUID, dict] = {}

    def store_vector(self, payload_id: UUID, vector: List[float], model_id: str, raw_text: Optional[str] = None) -> None:
        """Saves a semantic chunk with its embedding vector and metadata."""
        # Pre-compute the norm for fast cosine similarity later
        norm = math.sqrt(sum(x * x for x in vector))
        self._embeddings[payload_id] = {
            "vector": vector,
            "norm": norm,
            "model_id": model_id,
            "raw_text_fallback": raw_text
        }

    def get_vector(self, payload_id: UUID) -> Optional[dict]:
        """Retrieves a stored embedding and its metadata by payload ID."""
        entry = self._embeddings.get(payload_id)
        if entry:
            return {
                "vector": entry["vector"],
                "model_id": entry["model_id"],
                "raw_text_fallback": entry["raw_text_fallback"]
            }
        return None

    def list_vectors(self) -> List[dict]:
        """Returns metadata for all stored vectors (without the raw float arrays)."""
        return [
            {
                "payload_id": str(pid),
                "model_id": entry["model_id"],
                "dimensions": len(entry["vector"]),
                "has_raw_text": entry["raw_text_fallback"] is not None
            }
            for pid, entry in self._embeddings.items()
        ]

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[UUID, float, Optional[str]]]:
        """
        Find the top-K most similar vectors by cosine similarity.
        
        Args:
            query_vector: The query embedding to compare against all stored vectors.
            top_k: Number of results to return.
            
        Returns:
            List of (payload_id, similarity_score, raw_text_fallback) sorted by score descending.
            Similarity is in [-1.0, 1.0] where 1.0 = identical direction.
        """
        if not self._embeddings:
            return []
        
        query_norm = math.sqrt(sum(x * x for x in query_vector))
        if query_norm == 0:
            return []
        
        results: List[Tuple[UUID, float, Optional[str]]] = []
        
        for pid, entry in self._embeddings.items():
            stored_vector = entry["vector"]
            stored_norm = entry["norm"]
            
            # Skip if stored vector has zero magnitude
            if stored_norm == 0:
                continue
            
            # Validate dimensions match
            if len(stored_vector) != len(query_vector):
                raise ValueError(f"Dimension mismatch: query is {len(query_vector)}d, stored vector '{pid}' is {len(stored_vector)}d.")
            
            # Dot product
            dot = sum(a * b for a, b in zip(query_vector, stored_vector))
            similarity = dot / (query_norm * stored_norm)
            
            results.append((pid, similarity, entry["raw_text_fallback"]))
        
        # Sort by similarity descending, take top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @property
    def total_vectors(self) -> int:
        return len(self._embeddings)
