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
from typing import Any, Dict, Union
from uuid import UUID

from tpcp.adapters.base import BaseFrameworkAdapter
from tpcp.schemas.envelope import TPCPEnvelope, Intent, TextPayload


class CrewAIAdapter(BaseFrameworkAdapter):
    """
    Adapter for translating CrewAI agent outputs (typically strings or dicts)
    into standard TPCP envelopes.
    """

    async def pack_thought(self, native_output: Union[str, Dict[str, Any]], receiver_id: UUID, intent: Intent) -> TPCPEnvelope:
        """
        Wraps a CrewAI text or dict output into a TPCP TextPayload.
        """
        if isinstance(native_output, dict):
            content_str = json.dumps(native_output)
        else:
            content_str = str(native_output)

        payload = TextPayload(content=content_str, language="en")
        header = self._create_header(receiver_id, intent)
        
        return TPCPEnvelope(header=header, payload=payload)

    async def unpack_payload(self, envelope: TPCPEnvelope) -> Union[str, Dict[str, Any]]:
        """
        Extracts a TPCP envelope payload back into a format CrewAI agents can parse.
        Usually returns the raw text content format.
        """
        if isinstance(envelope.payload, TextPayload):
            try:
                # Attempt to parse json back into dict if it was a packed dict
                return json.loads(envelope.payload.content)
            except json.JSONDecodeError:
                return envelope.payload.content
        
        # Fallback to string representation for other payload types
        return str(envelope.payload)
