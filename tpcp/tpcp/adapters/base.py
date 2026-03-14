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

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from tpcp.schemas.envelope import TPCPEnvelope, Intent, AgentIdentity, MessageHeader, PROTOCOL_VERSION


class BaseFrameworkAdapter(ABC):
    """
    Abstract base class for wrapping framework-specific agents (e.g., CrewAI, LangGraph)
    and translating their native outputs into standardised TPCP envelopes.
    """

    def __init__(self, agent_identity: AgentIdentity, identity_manager=None):
        self.identity = agent_identity
        self.identity_manager = identity_manager
        self._logical_clock: int = 0

    @abstractmethod
    def pack_thought(self, target_id: UUID, raw_output: Any, intent: Intent) -> TPCPEnvelope:
        """
        Translates a framework-specific native string or state dictionary into a TPCPEnvelope.
        """
        pass

    @abstractmethod
    def unpack_request(self, envelope: TPCPEnvelope) -> Any:
        """
        Translates a received TPCPEnvelope payload back into a format the native framework understands.
        """
        pass

    def _create_header(self, receiver_id: UUID, intent: Intent) -> MessageHeader:
        """Helper to construct standard message headers."""
        return MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=receiver_id,
            intent=intent,
            protocol_version=PROTOCOL_VERSION
        )
