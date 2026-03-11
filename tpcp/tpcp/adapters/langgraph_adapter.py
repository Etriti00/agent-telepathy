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

import json
from typing import Any, Dict
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload


class LangGraphAdapter(BaseFrameworkAdapter):
    """
    Adapter for parsing LangGraph state dictionaries into standardized TPCP envelopes.
    LangGraph maintains explicit graph states (e.g., {"messages": [...], "status": "running"}).
    """

    async def pack_thought(self, native_output: Dict[str, Any], receiver_id: UUID, intent: Intent) -> TPCPEnvelope:
        """
        Packages a LangGraph state graph dictionary into a TPCP envelope.
        Currently serializes the entire state structure as JSON into a TextPayload.
        """
        if not isinstance(native_output, dict):
            raise ValueError(f"LangGraphAdapter expects a state dictionary, got {type(native_output)}")

        try:
            content_str = json.dumps(native_output, default=str)
        except TypeError as e:
            raise ValueError(f"Failed to serialize LangGraph state: {e}")

        payload = TextPayload(content=content_str, language="en")
        header = self._create_header(receiver_id, intent)

        return TPCPEnvelope(header=header, payload=payload)

    async def unpack_payload(self, envelope: TPCPEnvelope) -> Dict[str, Any]:
        """
        Unpacks an incoming envelope into a dictionary that LangGraph can merge into its state.
        """
        if isinstance(envelope.payload, TextPayload):
            try:
                return {"received_state": json.loads(envelope.payload.content)}
            except json.JSONDecodeError:
                return {"received_message": envelope.payload.content}
        
        # Fallback placeholder for non-text payloads
        return {"received_payload_type": type(envelope.payload).__name__}
