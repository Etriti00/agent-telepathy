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
Core Node Manager for the TPCP protocol.
Handles peer discovery, inbound/outbound WebSocket connections, and message dispatch.
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Callable, Awaitable, Tuple
from uuid import UUID

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.client import connect
from pydantic import ValidationError

from tpcp.schemas.envelope import (
    AgentIdentity,
    TPCPEnvelope,
    MessageHeader,
    Intent,
    Payload,
    TextPayload,
    CRDTSyncPayload,
    VectorEmbeddingPayload
)
from tpcp.memory.crdt import LWWMap
from tpcp.memory.vector import VectorBank
from tpcp.security.crypto import AgentIdentityManager
from tpcp.core.queue import MessageQueue

logger = logging.getLogger(__name__)

# Type alias for intent handlers
IntentHandler = Callable[[TPCPEnvelope, WebSocketServerProtocol], Awaitable[None]]

class TPCPNode:
    """
    The main client that an agent wraps itself in to connect to the TPCP network.
    
    Each node owns a cryptographic Ed25519 identity, CRDT shared memory, a vector bank,
    and a Dead-Letter Queue for resilient routing under network partitions.
    """

    def __init__(self, identity: AgentIdentity, host: str = "127.0.0.1", port: int = 8000, adns_url: Optional[str] = None):
        self.identity = identity
        self.host = host
        self.port = port
        self.adns_url = adns_url
        # A-DNS WebSocket connection — established lazily in start_listening()
        self._adns_ws: Optional[websockets.client.WebSocketClientProtocol] = None
        
        # Initialize cryptographic trust layer and override the identity public key
        # so it always matches the actual keypair this node was born with.
        self.identity_manager = AgentIdentityManager()
        self.identity.public_key = self.identity_manager.get_public_key_string()
        
        # Peer registry: maps agent_id (UUID) to (AgentIdentity, websocket_url)
        self.peer_registry: Dict[UUID, Tuple[AgentIdentity, str]] = {}
        
        # Shared Semantic Memory — CRDT LWW-Map
        self.shared_memory = LWWMap(node_id=str(self.identity.agent_id))
        
        # Vector Bank for high-dimensional semantic reception
        self.vector_bank = VectorBank(node_id=str(self.identity.agent_id))
        
        # Dead-Letter Queue (max 500 messages per peer) for offline routing
        self.message_queue = MessageQueue(max_size_per_peer=500)

        # Intent routing table — maps Intent enum values to async handlers
        self.handlers: Dict[Intent, IntentHandler] = {}
        
        # Register internal default handlers
        self.register_handler(Intent.HANDSHAKE, self._handle_handshake)
        self.register_handler(Intent.STATE_SYNC, self._handle_state_sync)
        self.register_handler(Intent.STATE_SYNC_VECTOR, self._handle_vector_sync)
        
        self._server: Optional[websockets.server.WebSocketServer] = None

    def register_handler(self, intent: Intent, handler: IntentHandler) -> None:
        """Register a callback for a specific intent."""
        self.handlers[intent] = handler

    def register_peer(self, identity: AgentIdentity, address: str) -> None:
        """Add or update a peer in the registry."""
        self.peer_registry[identity.agent_id] = (identity, address)
        logger.info(f"Registered peer {identity.agent_id} at {address}")

    def remove_peer(self, agent_id: UUID) -> None:
        """Remove a peer from the registry."""
        if agent_id in self.peer_registry:
            del self.peer_registry[agent_id]
            logger.info(f"Removed peer {agent_id}")

    async def start_listening(self) -> None:
        """Start the WebSocket server to listen for inbound TPCP messages."""
        logger.info(f"Node {self.identity.agent_id} starting on ws://{self.host}:{self.port}")
        self._server = await websockets.serve(self._handle_connection, self.host, self.port)
        
        if self.adns_url:
            # Use asyncio.get_event_loop() inside an async context — this is safe and correct
            loop = asyncio.get_event_loop()
            loop.create_task(self._connect_to_adns())

    async def _connect_to_adns(self) -> None:
        """
        Connects to the global A-DNS Relay Server with exponential backoff.
        Once connected, registers identity and listens for routed messages.
        """
        backoff = 1.0
        max_backoff = 60.0

        while True:
            try:
                async with websockets.client.connect(self.adns_url) as ws:
                    self._adns_ws = ws
                    logger.info(f"Connected to Global A-DNS Relay at {self.adns_url}")
                    backoff = 1.0  # reset on success
                    
                    # Announce presence
                    await self.broadcast_discovery()
                    
                    # Listen for routed inbound from relay
                    async for message in ws:
                        await self._process_inbound(message, ws)
            except Exception as e:
                self._adns_ws = None
                logger.warning(f"A-DNS connection lost: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def stop_listening(self) -> None:
        """Stop the WebSocket server gracefully."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info(f"Node {self.identity.agent_id} stopped listening.")
        if self._adns_ws:
            await self._adns_ws.close()

    async def _handle_connection(self, websocket: WebSocketServerProtocol, *args) -> None:
        """Handle individual inbound WebSocket connections."""
        try:
            async for raw_message in websocket:
                await self._process_inbound(raw_message, websocket)
        except websockets.exceptions.ConnectionClosed:
            logger.debug("A WebSocket connection was closed.")
        except Exception as e:
            logger.error(f"Error handling connection: {e}")

    async def _process_inbound(self, raw_message: str | bytes, websocket: WebSocketServerProtocol) -> None:
        """
        Deserialize, cryptographically verify, and route incoming messages.
        Unsigned or invalid-signature messages are dropped immediately.
        """
        try:
            if isinstance(raw_message, bytes):
                raw_message = raw_message.decode('utf-8')

            data = json.loads(raw_message)
            envelope = TPCPEnvelope.model_validate(data)
            
            logger.debug(f"Received {envelope.header.intent.value} from {envelope.header.sender_id}")
            
            # ── SECURITY MIDDLEWARE ──────────────────────────────────────────
            # Verify signature if the sender is a known peer (skip for handshakes
            # to allow initial registration, but log a warning for unsigned packets).
            if envelope.header.intent != Intent.HANDSHAKE:
                sender_id = envelope.header.sender_id
                if sender_id not in self.peer_registry:
                    logger.warning(f"Received {envelope.header.intent} from unregistered peer {sender_id}. Dropping.")
                    return
                
                peer_identity, _ = self.peer_registry[sender_id]
                
                if not envelope.signature:
                    logger.warning(f"Unsigned packet from {sender_id}. Dropping.")
                    return
                
                payload_dict = envelope.payload.model_dump()
                if not AgentIdentityManager.verify_signature(peer_identity.public_key, envelope.signature, payload_dict):
                    logger.warning(f"INVALID SIGNATURE from {sender_id}. Dropping packet.")
                    return
            # ────────────────────────────────────────────────────────────────
            
            # Dispatch to appropriate handler
            handler = self.handlers.get(envelope.header.intent)
            if handler:
                await handler(envelope, websocket)
            else:
                logger.warning(f"No handler registered for intent: {envelope.header.intent}")
                
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON message.")
        except ValidationError as e:
            logger.error(f"Validation error on inbound message: {e}")
        except Exception as e:
            logger.error(f"Failed to process inbound message: {e}")

    async def _handle_handshake(self, envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        """
        Default handshake handler. Automatically registers the sender as a peer
        if their identity is embedded in a TextPayload.
        """
        logger.info(f"Handshake received from {envelope.header.sender_id}")
        
        # Auto-register the sender in the peer registry so we can route back to them
        if isinstance(envelope.payload, TextPayload):
            try:
                sender_data = json.loads(envelope.payload.content)
                sender_identity = AgentIdentity.model_validate(sender_data)
                
                # Derive their socket address from the websocket connection
                peer_host = websocket.remote_address[0] if websocket.remote_address else "unknown"
                # We don't know their listening port from the inbound socket, so store what we can
                self.peer_registry[sender_identity.agent_id] = (sender_identity, f"ws://{peer_host}")
                logger.info(f"Auto-registered handshake peer: {sender_identity.framework} ({sender_identity.agent_id})")
            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"Could not auto-register peer from handshake payload: {e}")
        
    async def _handle_state_sync(self, envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        """Internal handler for merging CRDTSyncPayloads into local shared memory."""
        if not isinstance(envelope.payload, CRDTSyncPayload):
            logger.error("STATE_SYNC envelope did not contain a CRDTSyncPayload.")
            return

        payload = envelope.payload
        if payload.crdt_type == "LWW-Map":
            logger.info(f"Merging incoming LWW-Map from {envelope.header.sender_id}...")
            self.shared_memory.merge(payload.state)
            logger.info(f"[Semantic State Updated] Memory: {self.shared_memory.to_dict()}")
        else:
            logger.warning(f"Unsupported CRDT type received: {payload.crdt_type}")

    async def _handle_vector_sync(self, envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        """Internal handler for ingesting dense contextual vectors into the local VectorBank."""
        if not isinstance(envelope.payload, VectorEmbeddingPayload):
            logger.error(f"STATE_SYNC_VECTOR envelope lacked a VectorEmbeddingPayload (found {type(envelope.payload)}).")
            return

        payload = envelope.payload
        logger.info(f"Ingesting vector [{payload.model_id} | {payload.dimensions}d] from {envelope.header.sender_id}")
        
        self.vector_bank.store_vector(
            payload_id=envelope.header.message_id,
            vector=payload.vector,
            model_id=payload.model_id,
            raw_text=payload.raw_text_fallback
        )
        logger.info(f"[Vector Bank] Size is now {self.vector_bank.total_vectors}")

    async def send_message(self, target_id: UUID, intent: Intent, payload: Payload) -> None:
        """
        Sign and dispatch a TPCP message to a specific peer in the registry.
        If delivery fails, the message is queued in the DLQ with exponential backoff retry.
        """
        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=intent
        )
        
        # Sign the outgoing payload using this node's private key
        payload_dict = payload.model_dump()
        signature_str = self.identity_manager.sign_payload(payload_dict)
        
        envelope = TPCPEnvelope(header=header, payload=payload, signature=signature_str)
        await self._dispatch_envelope(target_id, envelope)

    async def _dispatch_envelope(self, target_id: UUID, envelope: TPCPEnvelope) -> None:
        """Attempts to send an envelope. Queues it in DLQ on failure, triggering backoff reconnect."""
        if target_id not in self.peer_registry:
            logger.error(f"Peer {target_id} not in registry. Pushing to DLQ.")
            await self.message_queue.enqueue(target_id, envelope)
            return

        _, endpoint = self.peer_registry[target_id]
        
        try:
            async with websockets.client.connect(endpoint) as websocket:
                await websocket.send(envelope.model_dump_json())
                logger.debug(f"Sent message {envelope.header.message_id} to {target_id}.")
        except Exception as e:
            logger.warning(f"Connection to {target_id} dropped: {e}. Pushing to DLQ.")
            await self.message_queue.enqueue(target_id, envelope)
            loop = asyncio.get_event_loop()
            loop.create_task(self._reconnect_and_drain(target_id))

    async def _reconnect_and_drain(self, target_id: UUID) -> None:
        """
        Exponential backoff reconnection loop. On success, drains DLQ one message at a time
        to prevent silent data loss if the socket drops mid-drain.
        """
        if target_id not in self.peer_registry:
            return
            
        _, endpoint = self.peer_registry[target_id]
        backoff = 1.0
        max_backoff = 60.0
        
        while await self.message_queue.has_messages(target_id):
            try:
                async with websockets.client.connect(endpoint) as websocket:
                    logger.info(f"[Network Restored] Re-established to {target_id}. Draining DLQ...")
                    
                    # Drain and send one-at-a-time, re-queuing on failure to prevent data loss
                    while await self.message_queue.has_messages(target_id):
                        msg = await self.message_queue.dequeue_one(target_id)
                        if msg is None:
                            break
                        try:
                            await websocket.send(msg.model_dump_json())
                            logger.debug(f"Drained message {msg.header.message_id} to {target_id}.")
                        except Exception:
                            # Re-queue the failed message at the front
                            await self.message_queue.enqueue_front(target_id, msg)
                            raise  # Trigger the outer backoff
                    break
            except Exception as e:
                logger.debug(f"Reconnection to {target_id} failed: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def broadcast_discovery(self, seed_nodes: Optional[list[str]] = None) -> None:
        """
        Announce this node's identity to seed peers or via the A-DNS relay.
        Generates a signed HANDSHAKE envelope containing the full AgentIdentity.
        """
        seed_nodes = seed_nodes or []
        target_id = UUID(int=0)
        
        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=Intent.HANDSHAKE
        )
        
        # Embed the full identity JSON in a TextPayload so receivers can register us
        payload = TextPayload(content=self.identity.model_dump_json())
        signature_str = self.identity_manager.sign_payload(payload.model_dump())
        
        envelope = TPCPEnvelope(header=header, payload=payload, signature=signature_str)
        serialized = envelope.model_dump_json()
        
        # Send via A-DNS relay if connected
        if self._adns_ws:
            try:
                await self._adns_ws.send(serialized)
            except Exception as e:
                logger.error(f"A-DNS broadcast failed: {e}")
                
        # Also send directly to any seed nodes
        if seed_nodes:
            logger.info(f"Broadcasting discovery to {len(seed_nodes)} seed nodes.")
            for address in seed_nodes:
                try:
                    async with connect(address) as websocket:
                        await websocket.send(serialized)
                        logger.debug(f"Sent discovery packet to {address}")
                except Exception as e:
                    logger.debug(f"Discovery failed for {address}: {e}")
