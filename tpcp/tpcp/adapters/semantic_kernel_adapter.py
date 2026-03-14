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
    import semantic_kernel
    SEMANTIC_KERNEL_AVAILABLE = True
except ImportError:
    SEMANTIC_KERNEL_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class SemanticKernelAdapter(BaseFrameworkAdapter):
    """
    Adapter for Microsoft Semantic Kernel function results into TPCP envelopes.

    Usage example::

        from tpcp.adapters.semantic_kernel_adapter import SemanticKernelAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-sk-agent")
        adapter = SemanticKernelAdapter(agent_identity=identity)

        # Semantic Kernel FunctionResult or dict with "result" key
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output={"result": "The answer is 42."},
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to kernel.invoke() format
        native = adapter.unpack_request(envelope)
        # native == {"input": "The answer is 42."}
    """

    def __init__(
        self,
        agent_identity,
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not SEMANTIC_KERNEL_AVAILABLE:
            raise ImportError(
                "Semantic Kernel is not installed. Install it with: pip install semantic-kernel>=1.0.0"
            )
        super().__init__(agent_identity, identity_manager)

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Any,
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages a Semantic Kernel FunctionResult or value into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: SK FunctionResult object (with .value attribute), dict with "result" key,
                        or plain string.
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the function result.
        """
        self._logical_clock += 1

        # Handle SK FunctionResult object
        if hasattr(raw_output, "value"):
            content = str(raw_output.value)
        elif isinstance(raw_output, dict):
            content = str(raw_output.get("result", raw_output))
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
        Converts a TPCP envelope into the format for kernel.invoke().

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"input": text} suitable for kernel.invoke(**result).
        """
        if isinstance(envelope.payload, TextPayload):
            return {"input": envelope.payload.content}
        return {}
