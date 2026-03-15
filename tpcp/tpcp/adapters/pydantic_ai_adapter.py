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
    import pydantic_ai  # noqa: F401
    PYDANTIC_AI_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class PydanticAIAdapter(BaseFrameworkAdapter):
    """
    Adapter for PydanticAI agent outputs into TPCP envelopes.

    Usage example::

        from tpcp.adapters.pydantic_ai_adapter import PydanticAIAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-pydantic-agent")
        adapter = PydanticAIAdapter(agent_identity=identity, model="openai:gpt-4o")

        # PydanticAI RunResult or dict with "output" key
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output={"output": "The answer is 42."},
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to pydantic_ai Agent.run() format
        native = adapter.unpack_request(envelope)
        # native == {"prompt": "The answer is 42."}
    """

    def __init__(
        self,
        agent_identity,
        model: str = "openai:gpt-4o",
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not PYDANTIC_AI_AVAILABLE:
            raise ImportError(
                "PydanticAI is not installed. Install it with: pip install pydantic-ai>=0.0.14"
            )
        super().__init__(agent_identity, identity_manager)
        self.model = model

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Any,
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages a PydanticAI RunResult or output dict into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: PydanticAI RunResult object or dict with an "output" key, or a string.
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the result content.
        """
        self._tick()

        # Handle PydanticAI RunResult (has .output or .data attribute)
        if hasattr(raw_output, "output"):
            content = str(raw_output.output)
        elif hasattr(raw_output, "data"):
            content = str(raw_output.data)
        elif isinstance(raw_output, dict):
            content = str(raw_output.get("output", raw_output))
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
        Converts a TPCP envelope into the format for pydantic_ai Agent.run().

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"prompt": text} suitable for Agent.run(**result).
        """
        if isinstance(envelope.payload, TextPayload):
            return {"prompt": envelope.payload.content}
        return {}
