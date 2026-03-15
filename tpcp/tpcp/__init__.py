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
TPCP (Telepathy Communication Protocol) SDK Core
A framework-agnostic, LLM-agnostic communication standard for autonomous agents.
"""

__version__ = "0.4.0"

from tpcp.core.node import TPCPNode
from tpcp.schemas.envelope import (
    AgentIdentity,
    Intent,
    TPCPEnvelope,
    TextPayload,
    VectorEmbeddingPayload,
    CRDTSyncPayload,
    AckInfo,
    ChunkInfo,
    TelemetryReading,
    TelemetryPayload,
)
from tpcp.memory.crdt import LWWMap
from tpcp.memory.vector import VectorBank
from tpcp.security.crypto import AgentIdentityManager
from tpcp.adapters.base import BaseFrameworkAdapter

__all__ = [
    "__version__",
    "TPCPNode",
    "AgentIdentity",
    "Intent",
    "TPCPEnvelope",
    "TextPayload",
    "VectorEmbeddingPayload",
    "CRDTSyncPayload",
    "AckInfo",
    "ChunkInfo",
    "TelemetryReading",
    "TelemetryPayload",
    "LWWMap",
    "VectorBank",
    "AgentIdentityManager",
    "BaseFrameworkAdapter"
]
