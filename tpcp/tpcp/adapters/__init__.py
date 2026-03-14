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

from .base import BaseFrameworkAdapter
from .crewai_adapter import CrewAIAdapter
from .langgraph_adapter import LangGraphAdapter

__all__ = ["BaseFrameworkAdapter", "CrewAIAdapter", "LangGraphAdapter"]

# Industrial IoT adapters — guarded by library availability
try:
    from .opcua_adapter import OPCUAAdapter  # noqa: F401
    __all__.append("OPCUAAdapter")
except ImportError:
    pass

try:
    from .modbus_adapter import ModbusAdapter  # noqa: F401
    __all__.append("ModbusAdapter")
except ImportError:
    pass

try:
    from .canbus_adapter import CANbusAdapter  # noqa: F401
    __all__.append("CANbusAdapter")
except ImportError:
    pass

# AI framework adapters — guarded by library availability
try:
    from .autogen_adapter import AutoGenAdapter  # noqa: F401
    __all__.append("AutoGenAdapter")
except ImportError:
    pass

try:
    from .pydantic_ai_adapter import PydanticAIAdapter  # noqa: F401
    __all__.append("PydanticAIAdapter")
except ImportError:
    pass

try:
    from .smolagents_adapter import SmolagentsAdapter  # noqa: F401
    __all__.append("SmolagentsAdapter")
except ImportError:
    pass

try:
    from .openai_agents_adapter import OpenAIAgentsAdapter  # noqa: F401
    __all__.append("OpenAIAgentsAdapter")
except ImportError:
    pass

try:
    from .llamaindex_adapter import LlamaIndexAdapter  # noqa: F401
    __all__.append("LlamaIndexAdapter")
except ImportError:
    pass

try:
    from .haystack_adapter import HaystackAdapter  # noqa: F401
    __all__.append("HaystackAdapter")
except ImportError:
    pass

try:
    from .semantic_kernel_adapter import SemanticKernelAdapter  # noqa: F401
    __all__.append("SemanticKernelAdapter")
except ImportError:
    pass
