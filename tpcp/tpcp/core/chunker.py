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
TPCP chunked transfer — sends large binary payloads as a sequence of BinaryPayload envelopes.

Each chunk envelope carries a ChunkInfo with chunk_index, total_chunks, and transfer_id.
The receiver uses ChunkReassembler (in reassembler.py) to reconstruct the original bytes.

Usage::

    transfer_id = await send_chunked(
        node=my_node,
        target_id=peer_uuid,
        payload_bytes=large_image_bytes,
        mime_type="image/png",
        chunk_size_bytes=65536,  # 64KB default
    )
"""
from __future__ import annotations

import base64
import math
import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from tpcp.schemas.envelope import BinaryPayload, ChunkInfo, Intent

if TYPE_CHECKING:
    from tpcp.core.node import TPCPNode


async def send_chunked(
    node: "TPCPNode",
    target_id: UUID,
    payload_bytes: bytes,
    mime_type: str,
    description: str = "",
    chunk_size_bytes: int = 65536,
) -> UUID:
    """
    Split payload_bytes into chunks and send each as a BinaryPayload envelope.

    Args:
        node: The TPCPNode to send from.
        target_id: UUID of the receiving peer.
        payload_bytes: Raw bytes to send.
        mime_type: MIME type of the data (e.g. "image/png", "application/octet-stream").
        description: Optional human-readable description (text fallback).
        chunk_size_bytes: Max bytes per chunk. Default 64 KB.

    Returns:
        transfer_id: UUID identifying this transfer (useful for tracking).
    """
    if not payload_bytes:
        raise ValueError("payload_bytes cannot be empty")
    if chunk_size_bytes < 1024:
        raise ValueError("chunk_size_bytes must be at least 1024 bytes")

    transfer_id = uuid.uuid4()
    total_chunks = math.ceil(len(payload_bytes) / chunk_size_bytes)

    for chunk_index in range(total_chunks):
        start = chunk_index * chunk_size_bytes
        end = min(start + chunk_size_bytes, len(payload_bytes))
        chunk_bytes = payload_bytes[start:end]

        chunk_payload = BinaryPayload(
            data_base64=base64.b64encode(chunk_bytes).decode("ascii"),
            mime_type=mime_type,
            description=description or f"Chunk {chunk_index + 1}/{total_chunks}",
        )
        chunk_info = ChunkInfo(
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            transfer_id=transfer_id,
        )

        await node.send_message(
            target_id=target_id,
            intent=Intent.MEDIA_SHARE,
            payload=chunk_payload,
            chunk_info=chunk_info,
        )

    return transfer_id
