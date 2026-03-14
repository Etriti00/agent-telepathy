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
    import haystack  # noqa: F401
    HAYSTACK_AVAILABLE = True
except ImportError:
    HAYSTACK_AVAILABLE = False

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload
from tpcp.security.crypto import AgentIdentityManager


class HaystackAdapter(BaseFrameworkAdapter):
    """
    Adapter for Haystack (deepset) pipeline outputs into TPCP envelopes.

    Usage example::

        from tpcp.adapters.haystack_adapter import HaystackAdapter
        from tpcp.schemas.envelope import AgentIdentity, Intent
        import uuid

        identity = AgentIdentity(agent_id=uuid.uuid4(), name="my-haystack-pipeline")
        adapter = HaystackAdapter(agent_identity=identity)

        # Haystack pipeline.run() result dict
        raw = {"answers": [{"answer": "Paris"}]}
        envelope = adapter.pack_thought(
            target_id=uuid.uuid4(),
            raw_output=raw,
            intent=Intent.TASK_RESPONSE
        )

        # Convert incoming TPCP envelope to Haystack pipeline.run() format
        native = adapter.unpack_request(envelope)
        # native == {"query": "Paris"}
    """

    def __init__(
        self,
        agent_identity,
        identity_manager: Optional[AgentIdentityManager] = None,
    ):
        if not HAYSTACK_AVAILABLE:
            raise ImportError(
                "Haystack is not installed. Install it with: pip install haystack-ai>=2.0.0"
            )
        super().__init__(agent_identity, identity_manager)

    def pack_thought(
        self,
        target_id: UUID,
        raw_output: Union[str, Dict[str, Any]],
        intent: Intent,
    ) -> TPCPEnvelope:
        """
        Packages a Haystack pipeline.run() result dict into a signed TPCP envelope.

        Args:
            target_id: UUID of the receiving agent.
            raw_output: Haystack pipeline result dict, e.g.:
                - {"answers": [{"answer": "..."}]}
                - {"replies": ["..."]}
                - plain string
            intent: TPCP intent for the message (default: TASK_RESPONSE).

        Returns:
            A TPCPEnvelope containing a TextPayload with the first answer or reply.
        """
        self._logical_clock += 1

        if isinstance(raw_output, dict):
            # Try "answers" key (ExtractiveQA / GenerativeQA pipelines)
            if "answers" in raw_output:
                answers = raw_output["answers"]
                if answers:
                    first = answers[0]
                    if isinstance(first, dict):
                        content = str(first.get("answer", first))
                    elif hasattr(first, "answer"):
                        content = str(first.answer)
                    else:
                        content = str(first)
                else:
                    content = str(raw_output)
            # Try "replies" key (chat / LLM pipelines)
            elif "replies" in raw_output:
                replies = raw_output["replies"]
                content = str(replies[0]) if replies else str(raw_output)
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
        Converts a TPCP envelope into the format for Haystack pipeline.run().

        Args:
            envelope: Incoming TPCPEnvelope.

        Returns:
            A dict like {"query": text} suitable for pipeline.run(**result).
        """
        if isinstance(envelope.payload, TextPayload):
            return {"query": envelope.payload.content}
        return {}
