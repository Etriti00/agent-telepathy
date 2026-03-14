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

from typing import Any, Dict, Optional
from uuid import UUID

try:
    import autogen  # noqa: F401
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class AutoGenAdapter(BaseFrameworkAdapter):
    """
    Adapter for Microsoft AutoGen (autogen-agentchat) agent outputs into TPCP envelopes.

    Usage example::

        from tpcp.adapters.autogen_adapter import AutoGenAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-autogen-agent")
        adapter = AutoGenAdapter(agent_identity=identity)

        # AutoGen message format: {"role": "assistant", "content": "Hello!"}
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output={"role": "assistant", "content": "Hello!"},
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to AutoGen receive() format
        native = adapter.unpack_request(envelope)
        # native == {"role": "user", "content": "Hello!"}
    """

    def __init__(
        self,
        agent_identity,
        agent_config: Optional[Dict[str, Any]] = None,
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not AUTOGEN_AVAILABLE:
            raise ImportError(
                "AutoGen is not installed. Install it with: pip install autogen-agentchat>=0.4.0"
            )
        super().__init__(agent_identity, identity_manager)
        self.agent_config = agent_config or {}

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Dict[str, Any],
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages an AutoGen message dict into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: AutoGen message dict, e.g. {"role": "assistant", "content": "..."}.
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the message content.
        """
        self._logical_clock += 1

        if isinstance(raw_output, dict):
            content = raw_output.get("content", str(raw_output))
        else:
            content = str(raw_output)

        payload = TextPayload(content=content, language="en")
        header = self._create_header(receiver_id=target_id, intent=intent)

        signature = None
        if self.identity_manager:
            signature = self.identity_manager.sign_payload(payload.model_dump())

        return TPCPEnvelope(header=header, payload=payload, signature=signature)

    def unpack_request(self, envelope: TPCPEnvelope) -> Dict[str, Any]:
        """
        Converts a TPCP TASK_REQUEST envelope into AutoGen's ConversableAgent.receive() format.

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"role": "user", "content": text} suitable for AutoGen.
        """
        if isinstance(envelope.payload, TextPayload):
            return {"role": "user", "content": envelope.payload.content}
        return {}
