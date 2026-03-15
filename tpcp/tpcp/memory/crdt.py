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
Last-Writer-Wins Map (LWW-Map) CRDT implementation.
Supports in-memory operation and optional SQLite persistence for durable state across restarts.
"""

import aiosqlite
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class LWWMap:
    """
    A Last-Writer-Wins Map using Lamport logical clocks for deterministic conflict resolution.
    
    Properties:
    - Commutativity: merge(A, B) == merge(B, A)
    - Associativity: merge(merge(A, B), C) == merge(A, merge(B, C))
    - Idempotence: merge(A, A) == A
    
    Optional SQLite persistence using aiosqlite:
        crdt = LWWMap(node_id="agent-1", db_path=Path(".tpcp/memory.db"))
        await crdt.connect()
    """
    
    def __init__(self, node_id: str, db_path: Optional[Path] = None):
        self.node_id = node_id
        self._state: Dict[str, Tuple[Any, int, str]] = {}
        self.logical_clock = 0
        
        # Optional SQLite persistence
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize SQLite database for persistent CRDT state and hydrate."""
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(self._db_path))
            async with self._lock:
                await self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS lww_map (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        writer_id TEXT NOT NULL
                    )
                """)
                await self._conn.commit()
            await self._hydrate_from_db()

    async def _hydrate_from_db(self) -> None:
        """Load existing state from SQLite on startup."""
        if not self._conn:
            return
        async with self._lock:
            async with self._conn.execute("SELECT key, value, timestamp, writer_id FROM lww_map") as cursor:
                async for row in cursor:
                    key, value_json, ts, writer = row
                    value = json.loads(value_json)
                    self._state[key] = (value, ts, writer)
                    self.logical_clock = max(self.logical_clock, ts)

    async def _persist(self, key: str, value: Any, timestamp: int, writer_id: str) -> None:
        """Write-through to SQLite on mutation."""
        if not self._conn:
            return
        value_json = json.dumps(value, default=str, sort_keys=True)
        async with self._lock:
            await self._conn.execute(
                "INSERT OR REPLACE INTO lww_map (key, value, timestamp, writer_id) VALUES (?, ?, ?, ?)",
                (key, value_json, timestamp, writer_id)
            )
            await self._conn.commit()

    async def set(self, key: str, value: Any, timestamp: Optional[int] = None, writer_id: Optional[str] = None) -> None:
        """
        Sets a key to a value in the map.
        If a timestamp is not provided, increments the logical clock.
        """
        if timestamp is None:
            self.logical_clock += 1
            timestamp = self.logical_clock
            writer_id = self.node_id
        else:
            self.logical_clock = max(self.logical_clock, timestamp)
            if writer_id is None:
                writer_id = self.node_id

        updated = False

        if key in self._state:
            existing_value, existing_ts, existing_writer = self._state[key]
            
            if timestamp > existing_ts:
                self._state[key] = (value, timestamp, writer_id)
                updated = True
            elif timestamp == existing_ts:
                if writer_id > existing_writer:
                    self._state[key] = (value, timestamp, writer_id)
                    updated = True
                elif writer_id == existing_writer:
                    if json.dumps(value, sort_keys=True, default=str) > json.dumps(existing_value, sort_keys=True, default=str):
                        self._state[key] = (value, timestamp, writer_id)
                        updated = True
        else:
            self._state[key] = (value, timestamp, writer_id)
            updated = True

        if updated:
            await self._persist(key, value, timestamp, writer_id)

    def get(self, key: str) -> Any:
        """Returns the mapped value for the given key, or None if absent."""
        if key in self._state:
            return self._state[key][0]
        return None

    async def merge(self, other_state: Dict[str, Dict[str, Any]]) -> None:
        """
        Merges a serialized CRDT state from another node.
        Format: { key: { "value": Any, "timestamp": int, "writer_id": str } }
        """
        for key, record in other_state.items():
            await self.set(
                key=key,
                value=record["value"],
                timestamp=record["timestamp"],
                writer_id=record["writer_id"]
            )

    def to_dict(self) -> Dict[str, Any]:
        """Returns a clean dictionary of just the resolved values."""
        return {k: v[0] for k, v in self._state.items()}

    def serialize_state(self) -> Dict[str, Dict[str, Any]]:
        """Serializes the internal state for TPCP transport."""
        return {
            key: {"value": val, "timestamp": ts, "writer_id": writer}
            for key, (val, ts, writer) in self._state.items()
        }

    async def close(self) -> None:
        """Close the SQLite connection if open."""
        if self._conn:
            await self._conn.close()
            self._conn = None
