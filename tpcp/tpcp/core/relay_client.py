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

"""
RelayTPCPNode — client-only TPCP node for NAT-heavy, serverless, and browser environments.

Unlike TPCPNode, RelayTPCPNode does NOT open an inbound server port.
All traffic (inbound and outbound) flows through the A-DNS relay.
The relay routes messages to this node via the registered WebSocket connection.

Requirements:
- adns_url MUST be set (raises ValueError otherwise)
- All security features are identical (Ed25519, ACL, ACK/NACK, chunking)
- The relay must be running and the agent must successfully authenticate

Use case examples:
- Browser agents (WASM) that cannot open server ports
- AWS Lambda / serverless functions
- Agents on devices behind NAT
- Mobile app agents
"""
from __future__ import annotations

import logging

from tpcp.core.node import TPCPNode
from tpcp.schemas.envelope import AgentIdentity

logger = logging.getLogger(__name__)


class RelayTPCPNode(TPCPNode):
    """
    A TPCPNode that operates in client-only mode via the A-DNS relay.

    Identical to TPCPNode in all respects except it does not start a
    local WebSocket server. All inbound messages arrive through the relay.
    """

    def __init__(self, identity: AgentIdentity, adns_url: str, **kwargs) -> None:
        """
        Initialize a relay-only TPCP node.

        Args:
            identity: The agent's identity (same as TPCPNode).
            adns_url: REQUIRED — URL of the A-DNS relay (e.g., "ws://relay.tpcp.io:9000").
                      Cannot be None for RelayTPCPNode.
            **kwargs: Passed through to TPCPNode (auto_ack, acl_policy, key_path, etc.)
                      Do NOT pass host or port — they are unused in relay-only mode.
        """
        if not adns_url:
            raise ValueError(
                "RelayTPCPNode requires adns_url — the relay is this node's only transport. "
                "Provide the URL of a running A-DNS relay server."
            )
        # Pass host/port as None — they will be ignored since we override start_listening
        super().__init__(identity, host="127.0.0.1", port=0, adns_url=adns_url, **kwargs)

    async def start_listening(self) -> None:
        """
        Start relay-only mode: connect to the A-DNS relay and begin receiving messages.

        Unlike the base TPCPNode, this method does NOT start a local WebSocket server.
        All inbound messages arrive through the relay connection established here.
        """
        logger.info(
            f"[RelayTPCPNode] Starting in relay-only mode via {self.adns_url} "
            f"(no local server port)"
        )
        # Only connect to the relay — skip the server completely
        await self._connect_to_adns()
