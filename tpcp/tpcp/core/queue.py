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
from collections import deque
from typing import Dict, List, Optional
from uuid import UUID
from tpcp.schemas.envelope import TPCPEnvelope


class MessageQueue:
    """
    In-memory Dead-Letter Queue (DLQ) for network-partitioned message delivery.
    
    Caches TPCPEnvelopes locally keyed by target peer UUID. Messages are returned
    in FIFO order once connections are restored. Supports:
    - Bounded size per peer (prevents unbounded memory growth on dead peers)
    - Atomic front-queuing for safe mid-drain re-queueing on failure
    """

    def __init__(self, max_size_per_peer: int = 500):
        self._max_size = max_size_per_peer
        # Use deque for O(1) appendleft (enqueue_front) and pop (drain)
        self._dlq: Dict[UUID, deque] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, target_id: UUID, envelope: TPCPEnvelope) -> None:
        """Push an undelivered message to the back of the queue."""
        async with self._lock:
            if target_id not in self._dlq:
                self._dlq[target_id] = deque()
            
            q = self._dlq[target_id]
            if len(q) >= self._max_size:
                # Evict oldest message when full (LRU-style)
                q.popleft()
            q.append(envelope)

    async def enqueue_front(self, target_id: UUID, envelope: TPCPEnvelope) -> None:
        """Re-insert a failed message at the front of the queue (for safe mid-drain failure)."""
        async with self._lock:
            if target_id not in self._dlq:
                self._dlq[target_id] = deque()
            q = self._dlq[target_id]
            if len(q) >= self._max_size:
                # Evict newest message from back to make room for retry at front
                q.pop()
            q.appendleft(envelope)

    async def dequeue_one(self, target_id: UUID) -> Optional[TPCPEnvelope]:
        """Pop and return a single message from the front of the queue."""
        async with self._lock:
            if target_id in self._dlq and self._dlq[target_id]:
                msg = self._dlq[target_id].popleft()
                if not self._dlq[target_id]:
                    del self._dlq[target_id]
                return msg
            return None

    async def drain(self, target_id: UUID) -> List[TPCPEnvelope]:
        """Atomically extract ALL messages for a given target (for bulk drain use cases)."""
        async with self._lock:
            if target_id in self._dlq:
                msgs = list(self._dlq.pop(target_id))
                return msgs
            return []

    async def has_messages(self, target_id: UUID) -> bool:
        """Check if there are pending messages for a given target."""
        async with self._lock:
            return target_id in self._dlq and len(self._dlq[target_id]) > 0

    @property
    def queue_stats(self) -> Dict[str, int]:
        """Returns a snapshot of queue depths per peer (for monitoring)."""
        return {str(k): len(v) for k, v in self._dlq.items()}
