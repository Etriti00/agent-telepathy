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
    from openai import OpenAI  # noqa: F401
    OPENAI_AGENTS_AVAILABLE = True
except ImportError:
    OPENAI_AGENTS_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class OpenAIAgentsAdapter(BaseFrameworkAdapter):
    """
    Adapter for the OpenAI Agents SDK (openai.chat.completions) outputs into TPCP envelopes.

    Usage example::

        from tpcp.adapters.openai_agents_adapter import OpenAIAgentsAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-openai-agent")
        adapter = OpenAIAgentsAdapter(agent_identity=identity, model="gpt-4o")

        # OpenAI chat completion response dict
        raw = {"choices": [{"message": {"role": "assistant", "content": "Hello!"}}]}
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output=raw,
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to openai.chat.completions.create() format
        native = adapter.unpack_request(envelope)
        # native == {"messages": [{"role": "user", "content": "Hello!"}], "model": "gpt-4o"}
    """

    def __init__(
        self,
        agent_identity,
        model: str = "gpt-4o",
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not OPENAI_AGENTS_AVAILABLE:
            raise ImportError(
                "OpenAI SDK is not installed. Install it with: pip install openai>=1.0.0"
            )
        super().__init__(agent_identity, identity_manager)
        self.model = model

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Union[str, Dict[str, Any]],
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages an OpenAI chat completion response into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: OpenAI response object or dict. Supports:
                - dict with "content" key
                - dict with "choices[0].message.content" structure
                - object with .choices attribute (ChatCompletion)
                - plain string
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the message content.
        """
        self._tick()

        # Handle OpenAI ChatCompletion object
        if hasattr(raw_output, "choices"):
            try:
                content = raw_output.choices[0].message.content
            except (IndexError, AttributeError):
                content = str(raw_output)
        elif isinstance(raw_output, dict):
            if "content" in raw_output:
                content = raw_output["content"]
            elif "choices" in raw_output:
                try:
                    content = raw_output["choices"][0]["message"]["content"]
                except (IndexError, KeyError):
                    content = str(raw_output)
            else:
                content = str(raw_output)
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
        Converts a TPCP envelope into the format for openai.chat.completions.create().

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"messages": [...], "model": self.model} compatible with
            openai.chat.completions.create(**result).
        """
        if isinstance(envelope.payload, TextPayload):
            return {
                "messages": [{"role": "user", "content": envelope.payload.content}],
                "model": self.model,
            }
        return {}
