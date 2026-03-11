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

from typing import Any, Dict, Tuple, Optional

class LWWMap:
    def __init__(self, node_id: str):
        """
        Initializes a Last-Writer-Wins Map (LWW-Map).
        Uses Lamport logical clocks to resolve concurrent updates deterministically.
        """
        self.node_id = node_id
        # Maps key -> (value, logical_timestamp, writer_node_id)
        # Storing writer_node_id allows deterministic tie-breaking.
        self._state: Dict[str, Tuple[Any, int, str]] = {}
        self.logical_clock = 0

    def set(self, key: str, value: Any, timestamp: Optional[int] = None, writer_id: Optional[str] = None) -> None:
        """
        Sets a key to a value in the map.
        If a timestamp is not provided, increments the logical clock.
        If provided, advances the local logical clock to match the incoming time if it's greater.
        """
        if timestamp is None:
            self.logical_clock += 1
            timestamp = self.logical_clock
            writer_id = self.node_id
        else:
            self.logical_clock = max(self.logical_clock, timestamp)
            if writer_id is None:
                writer_id = self.node_id

        if key in self._state:
            existing_value, existing_ts, existing_writer = self._state[key]
            
            # 1. Compare logical timestamps
            if timestamp > existing_ts:
                self._state[key] = (value, timestamp, writer_id)
            # 2. Tie-breaker if perfectly concurrent (same timestamp)
            elif timestamp == existing_ts:
                # Deterministic resolution: lexically compare writer_ids to break the tie
                if writer_id > existing_writer:
                    self._state[key] = (value, timestamp, writer_id)
                elif writer_id == existing_writer:
                    # Same writer, same timestamp. For idempotence, we can just overwrite,
                    # or compare values. We'll compare stringified values to be strictly deterministic.
                    if str(value) > str(existing_value):
                        self._state[key] = (value, timestamp, writer_id)
        else:
            # Key does not exist, safe to insert
            self._state[key] = (value, timestamp, writer_id)

    def get(self, key: str) -> Any:
        """Returns the mapped value for the given key, or None if absent."""
        if key in self._state:
            return self._state[key][0]
        return None

    def merge(self, other_state: Dict[str, Dict[str, Any]]) -> None:
        """
        Receives a serialized CRDT state dictionary from another node.
        Applies mathematical properties of Commutativity, Associativity, and Idempotence to merge.
        Format expected: { key: { "value": Any, "timestamp": int, "writer_id": str } }
        """
        for key, record in other_state.items():
            self.set(
                key=key,
                value=record["value"],
                timestamp=record["timestamp"],
                writer_id=record["writer_id"]
            )

    def to_dict(self) -> Dict[str, Any]:
        """Returns a clean dictionary of just the resolved values."""
        return {k: v[0] for k, v in self._state.items()}

    def serialize_state(self) -> Dict[str, Dict[str, Any]]:
        """
        Serializes the internal state for TPCP transport.
        Returns: { key: {"value": Any, "timestamp": int, "writer_id": str} }
        """
        return {
            key: {"value": val, "timestamp": ts, "writer_id": writer}
            for key, (val, ts, writer) in self._state.items()
        }
