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
TPCP chunk reassembler — collects incoming chunk envelopes and reconstructs the payload.

Usage::

    reassembler = ChunkReassembler(timeout_seconds=60)

    # In your message handler:
    async def handle_media(envelope, websocket):
        result = reassembler.ingest(envelope)
        if result is not None:
            # All chunks received — result is the complete bytes
            process_complete_file(result, envelope.chunk_info.transfer_id)

    node.register_handler(Intent.MEDIA_SHARE, handle_media)
"""
from __future__ import annotations

import base64
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from tpcp.schemas.envelope import TPCPEnvelope

logger = logging.getLogger(__name__)


class ChunkReassembler:
    """
    Collects incoming chunk envelopes and reassembles them when all chunks arrive.

    Thread-safety: not thread-safe; designed for use in a single asyncio event loop.
    """

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        """
        Args:
            timeout_seconds: How long to keep an incomplete transfer before discarding it.
                             Incomplete transfers older than this are purged on the next ingest().
        """
        self.timeout_seconds = timeout_seconds
        # transfer_id -> list of (chunk_index, data_bytes)
        self._chunks: Dict[UUID, List[Tuple[int, bytes]]] = defaultdict(list)
        # transfer_id -> expected total_chunks
        self._total_chunks: Dict[UUID, int] = {}
        # transfer_id -> first-seen timestamp
        self._timestamps: Dict[UUID, float] = {}

    def ingest(self, envelope: TPCPEnvelope) -> Optional[bytes]:
        """
        Ingest a chunk envelope. Returns reassembled bytes when all chunks are received,
        or None if more chunks are still expected.

        Args:
            envelope: A TPCPEnvelope with chunk_info set.

        Returns:
            Complete reassembled bytes if this was the last chunk, else None.
        """
        if envelope.chunk_info is None:
            return None

        self._purge_stale()

        chunk_info = envelope.chunk_info
        transfer_id = chunk_info.transfer_id
        chunk_index = chunk_info.chunk_index
        total_chunks = chunk_info.total_chunks

        # Decode the chunk data
        if not hasattr(envelope.payload, "data_base64"):
            logger.warning(
                f"[Reassembler] Chunk {chunk_index}/{total_chunks} for {transfer_id} "
                f"has no data_base64 — skipping"
            )
            return None

        chunk_bytes = base64.b64decode(envelope.payload.data_base64)

        if transfer_id not in self._timestamps:
            self._timestamps[transfer_id] = time.monotonic()
            self._total_chunks[transfer_id] = total_chunks

        self._chunks[transfer_id].append((chunk_index, chunk_bytes))

        if len(self._chunks[transfer_id]) == total_chunks:
            return self._reassemble(transfer_id)

        return None

    def _reassemble(self, transfer_id: UUID) -> bytes:
        """Sort chunks by index and concatenate."""
        chunks = sorted(self._chunks.pop(transfer_id), key=lambda x: x[0])
        self._total_chunks.pop(transfer_id, None)
        self._timestamps.pop(transfer_id, None)
        return b"".join(data for _, data in chunks)

    def _purge_stale(self) -> None:
        """Remove transfers that have been waiting longer than timeout_seconds."""
        now = time.monotonic()
        stale = [
            tid
            for tid, ts in self._timestamps.items()
            if now - ts > self.timeout_seconds
        ]
        for tid in stale:
            logger.warning(f"[Reassembler] Purging stale transfer {tid} (timeout)")
            self._chunks.pop(tid, None)
            self._total_chunks.pop(tid, None)
            self._timestamps.pop(tid, None)
