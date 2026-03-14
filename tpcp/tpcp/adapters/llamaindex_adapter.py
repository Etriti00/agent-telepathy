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
    import llama_index  # noqa: F401
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class LlamaIndexAdapter(BaseFrameworkAdapter):
    """
    Adapter for LlamaIndex query engine or agent outputs into TPCP envelopes.

    Usage example::

        from tpcp.adapters.llamaindex_adapter import LlamaIndexAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-llamaindex-agent")
        adapter = LlamaIndexAdapter(agent_identity=identity)

        # LlamaIndex Response object or dict with "response" key
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output={"response": "The capital of France is Paris."},
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to LlamaIndex query_engine.query() format
        native = adapter.unpack_request(envelope)
        # native == {"query": "The capital of France is Paris."}
    """

    def __init__(
        self,
        agent_identity,
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not installed. Install it with: pip install llama-index>=0.10.0"
            )
        super().__init__(agent_identity, identity_manager)

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Any,
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages a LlamaIndex Response object or dict into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: LlamaIndex Response object (with .response attribute),
                        dict with "response" key, or plain string.
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the response text.
        """
        self._tick()

        # Handle LlamaIndex Response object
        if hasattr(raw_output, "response"):
            content = str(raw_output.response)
        elif isinstance(raw_output, dict):
            content = str(raw_output.get("response", raw_output))
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
        Converts a TPCP envelope into the format for LlamaIndex query_engine.query().

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"query": text} suitable for query_engine.query(**result).
        """
        if isinstance(envelope.payload, TextPayload):
            return {"query": envelope.payload.content}
        return {}
