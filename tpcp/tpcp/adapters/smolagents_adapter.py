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

from typing import Any, Dict, Optional, Union
from uuid import UUID

try:
    import smolagents  # noqa: F401
    SMOLAGENTS_AVAILABLE = True
except ImportError:
    SMOLAGENTS_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class SmolagentsAdapter(BaseFrameworkAdapter):
    """
    Adapter for HuggingFace smolagents agent outputs into TPCP envelopes.

    Usage example::

        from tpcp.adapters.smolagents_adapter import SmolagentsAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-smolagent")
        adapter = SmolagentsAdapter(agent_identity=identity)

        # smolagents agent.run() returns a string or dict
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output="The final answer is: Paris",
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to smolagents Agent.run() format
        native = adapter.unpack_request(envelope)
        # native == {"task": "The final answer is: Paris"}
    """

    def __init__(
        self,
        agent_identity,
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not SMOLAGENTS_AVAILABLE:
            raise ImportError(
                "smolagents is not installed. Install it with: pip install smolagents>=1.0.0"
            )
        super().__init__(agent_identity, identity_manager)

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Union[str, Dict[str, Any]],
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages a smolagents agent.run() result into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: smolagents agent.run() result — a string, or dict with "final_answer" key.
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the final answer or string result.
        """
        self._logical_clock += 1

        if isinstance(raw_output, dict):
            content = str(raw_output.get("final_answer", raw_output))
        elif hasattr(raw_output, "final_answer"):
            content = str(raw_output.final_answer)
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
        Converts a TPCP envelope into the format for smolagents Agent.run().

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"task": text} suitable for agent.run(**result).
        """
        if isinstance(envelope.payload, TextPayload):
            return {"task": envelope.payload.content}
        return {}
