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
Agent Domain Name System (A-DNS) Relay Server with:
- Challenge-response authentication (prevents UUID spoofing)
- Per-connection token bucket rate limiting
- TTL enforcement on routed messages
"""

import asyncio
import json
import os
import time
import logging
from typing import Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADNS-Relay")


class TokenBucket:
    """Simple token bucket rate limiter per connection."""
    
    def __init__(self, rate: float = 30.0, burst: int = 60):
        """
        Args:
            rate: tokens replenished per second (sustained throughput)
            burst: max tokens (peak burst capacity)
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self._last_refill = time.monotonic()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate-limited."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        
        # Refill tokens based on elapsed time
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class ADNSRelayServer:
    """
    Agent Domain Name System (A-DNS) Relay for global peer discovery and routing.
    
    Security features:
    - Challenge-response: on registration, sends a random nonce which the node must
      sign with its Ed25519 private key. Only verified nodes are registered.
    - Rate limiting: per-connection token bucket (default 30 msg/sec, 60 burst).
    - TTL enforcement: decrements TTL on forwarded packets, drops if TTL <= 0.
    """
    
    def __init__(self, host: str, port: int, rate_limit: float = 30.0, burst_limit: int = 60):
        self.host = host
        self.port = port
        self.rate_limit = rate_limit
        self.burst_limit = burst_limit
        
        # Verified registry: agent_id -> { ws, public_key }
        self.registry: Dict[str, dict] = {}
        
        # Pending challenges: agent_id -> { ws, nonce, public_key }
        self._pending_challenges: Dict[str, dict] = {}
        
        # Rate limiters per connection
        self._rate_limiters: Dict[int, TokenBucket] = {}

    async def _handle_connection(self, websocket: WebSocketServerProtocol, *args) -> None:
        agent_id = None
        ws_id = id(websocket)
        self._rate_limiters[ws_id] = TokenBucket(self.rate_limit, self.burst_limit)
        
        try:
            async for message in websocket:
                # Rate limit check
                if not self._rate_limiters[ws_id].consume():
                    logger.warning(f"Rate limit exceeded for connection {ws_id}. Disconnecting.")
                    await websocket.close(1008, "Rate limit exceeded")
                    break
                
                try:
                    data = json.loads(message)
                    header = data.get("header", {})
                    intent = header.get("intent")
                    sender_id = header.get("sender_id")
                    
                    if not sender_id:
                        continue
                    
                    # ── CHALLENGE-RESPONSE FLOW ──────────────────────────
                    # Check if this is a challenge response
                    if intent == "Challenge_Response":
                        await self._handle_challenge_response(sender_id, data, websocket)
                        continue
                    
                    # First-contact: initiate challenge
                    if sender_id not in self.registry:
                        if sender_id not in self._pending_challenges:
                            await self._initiate_challenge(sender_id, data, websocket)
                        continue  # Don't route until verified
                    
                    # ── VERIFIED ROUTING ──────────────────────────────────
                    # Update the connection if this node reconnected
                    if self.registry[sender_id]["ws"] != websocket:
                        self.registry[sender_id]["ws"] = websocket
                    
                    target_id = header.get("receiver_id")
                    null_id = "00000000-0000-0000-0000-000000000000"
                    
                    # TTL enforcement
                    ttl = header.get("ttl", 30)
                    if ttl <= 0:
                        logger.warning(f"TTL expired for packet from {sender_id}. Dropping.")
                        continue
                    
                    # Decrement TTL before forwarding
                    header["ttl"] = ttl - 1
                    data["header"] = header
                    forwarded_message = json.dumps(data)
                    
                    if target_id and target_id in self.registry and target_id != sender_id:
                        logger.info(f"Routing {intent} from {sender_id} to {target_id} (TTL={ttl-1})")
                        target_ws = self.registry[target_id]["ws"]
                        try:
                            await target_ws.send(forwarded_message)
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Target {target_id} connection is stale. Deregistering.")
                            del self.registry[target_id]
                    elif target_id and target_id != null_id:
                        logger.warning(f"Target {target_id} not registered. Packet dropped.")
                        
                except json.JSONDecodeError:
                    logger.error("Non-JSON message received. Ignoring.")
                except Exception as e:
                    logger.error(f"Error processing A-DNS message: {e}")
        finally:
            # Cleanup
            if ws_id in self._rate_limiters:
                del self._rate_limiters[ws_id]
            
            # Deregister from verified registry
            agents_to_remove = [aid for aid, info in self.registry.items() if info["ws"] == websocket]
            for aid in agents_to_remove:
                del self.registry[aid]
                logger.info(f"Deregistered node from A-DNS (clean disconnect): {aid}")
            
            # Clean up any pending challenges
            agents_to_clean = [
                aid for aid, info in self._pending_challenges.items() 
                if info["ws"] == websocket
            ]
            for aid in agents_to_clean:
                del self._pending_challenges[aid]

    async def _initiate_challenge(self, sender_id: str, data: dict, websocket: WebSocketServerProtocol) -> None:
        """
        Generate a random nonce and challenge the connecting node to prove identity.
        The node must sign the nonce with their private key and return it.
        """
        # Extract the claimed public key from the handshake payload
        payload = data.get("payload", {})
        content = payload.get("content", "")
        
        public_key = None
        try:
            identity_data = json.loads(content)
            public_key = identity_data.get("public_key")
        except (json.JSONDecodeError, TypeError):
            pass
        
        if not public_key:
            logger.warning(f"No public key found in handshake from {sender_id}. Cannot challenge.")
            return
        
        # Generate nonce
        nonce = os.urandom(32).hex()
        
        # Store pending challenge
        self._pending_challenges[sender_id] = {
            "ws": websocket,
            "nonce": nonce,
            "public_key": public_key
        }
        
        # Send challenge to the node
        challenge_msg = json.dumps({
            "type": "ADNS_CHALLENGE",
            "agent_id": sender_id,
            "nonce": nonce
        })
        
        try:
            await websocket.send(challenge_msg)
            logger.info(f"Sent challenge to {sender_id}")
        except Exception as e:
            logger.error(f"Failed to send challenge to {sender_id}: {e}")
            if sender_id in self._pending_challenges:
                del self._pending_challenges[sender_id]

    async def _handle_challenge_response(self, sender_id: str, data: dict, websocket: WebSocketServerProtocol) -> None:
        """Verify the signed nonce from the node to complete registration."""
        if sender_id not in self._pending_challenges:
            logger.warning(f"Unexpected challenge response from {sender_id}. Ignoring.")
            return
        
        challenge = self._pending_challenges[sender_id]
        nonce = challenge["nonce"]
        public_key_str = challenge["public_key"]
        signed_nonce = data.get("payload", {}).get("content", "")
        
        if not signed_nonce:
            logger.warning(f"Empty challenge response from {sender_id}. Rejecting.")
            del self._pending_challenges[sender_id]
            return
        
        # Verify the signature
        from tpcp.security.crypto import AgentIdentityManager
        
        nonce_bytes = nonce.encode('utf-8')
        if AgentIdentityManager.verify_bytes(public_key_str, signed_nonce, nonce_bytes):
            # Registration successful
            self.registry[sender_id] = {
                "ws": websocket,
                "public_key": public_key_str
            }
            del self._pending_challenges[sender_id]
            
            # Send confirmation
            confirm_msg = json.dumps({
                "type": "ADNS_REGISTERED",
                "agent_id": sender_id
            })
            await websocket.send(confirm_msg)
            logger.info(f"✓ Verified and registered node: {sender_id}")
        else:
            logger.warning(f"✗ Challenge verification FAILED for {sender_id}. Rejecting.")
            del self._pending_challenges[sender_id]
            await websocket.close(1008, "Challenge verification failed")

    async def start(self) -> None:
        logger.info(f"Starting A-DNS Global Relay on ws://{self.host}:{self.port}")
        logger.info(f"  Rate limit: {self.rate_limit} msg/sec, burst: {self.burst_limit}")
        logger.info(f"  Challenge-response authentication: ENABLED")
        async with websockets.serve(self._handle_connection, self.host, self.port):
            await asyncio.Future()

if __name__ == "__main__":
    server = ADNSRelayServer("0.0.0.0", 9000)
    asyncio.run(server.start())
