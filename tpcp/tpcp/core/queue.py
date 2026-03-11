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

import asyncio
from typing import Dict, List
from uuid import UUID
from tpcp.schemas.envelope import TPCPEnvelope

class MessageQueue:
    """
    In-memory Dead-Letter Queue (DLQ) for temporally unrestorable network partitions.
    Caches TPCPEnvelopes locally and returns them in sequence once connections are restored.
    """
    def __init__(self):
        # Maps target peer UUID to a list of undelivered TPCPEnvelopes
        self._dlq: Dict[UUID, List[TPCPEnvelope]] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, target_id: UUID, envelope: TPCPEnvelope) -> None:
        """Pushes an undelivered message envelope into the queue."""
        async with self._lock:
            if target_id not in self._dlq:
                self._dlq[target_id] = []
            self._dlq[target_id].append(envelope)

    async def drain(self, target_id: UUID) -> List[TPCPEnvelope]:
        """Atomically extracts all messages for a given target to resync payloads."""
        async with self._lock:
            if target_id in self._dlq:
                return self._dlq.pop(target_id)
            return []

    async def has_messages(self, target_id: UUID) -> bool:
        """Checks if there are currently pending messages for a given target."""
        async with self._lock:
            return target_id in self._dlq and len(self._dlq[target_id]) > 0
