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

import asyncio
import json
import logging
from typing import Dict

import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADNS-Relay")

class ADNSRelayServer:
    """Agent Domain Name System (A-DNS) Relay for global peer discovery and routing."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        # Map agent_id string to WebSocket connection
        self.registry: Dict[str, WebSocketServerProtocol] = {}

    async def _handle_connection(self, websocket: WebSocketServerProtocol, *args) -> None:
        agent_id = None
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    header = data.get("header", {})
                    intent = header.get("intent")
                    sender_id = header.get("sender_id")
                    
                    if not sender_id:
                        continue
                        
                    # Register them globally on first contact
                    if sender_id not in self.registry:
                        self.registry[sender_id] = websocket
                        agent_id = sender_id
                        logger.info(f"Registered new node on A-DNS: {agent_id}")
                    
                    target_id = header.get("receiver_id")
                    null_id = "00000000-0000-0000-0000-000000000000"
                    
                    if target_id and target_id in self.registry and target_id != sender_id:
                        # Route message peer-to-peer globally
                        logger.info(f"Routing {intent} from {sender_id} to {target_id}")
                        target_ws = self.registry[target_id]
                        await target_ws.send(message)
                    elif target_id and target_id != null_id:
                        logger.warning(f"Target {target_id} not globally registered. Packet dropped.")
                        
                except Exception as e:
                    logger.error(f"Error parsing A-DNS message: {e}")
        finally:
            if agent_id and agent_id in self.registry:
                del self.registry[agent_id]
                logger.info(f"Deregistered node from A-DNS: {agent_id}")

    async def start(self) -> None:
        logger.info(f"Starting A-DNS Global Relay on ws://{self.host}:{self.port}")
        async with websockets.serve(self._handle_connection, self.host, self.port):
            await asyncio.Future()

if __name__ == "__main__":
    server = ADNSRelayServer("0.0.0.0", 9000)
    asyncio.run(server.start())
