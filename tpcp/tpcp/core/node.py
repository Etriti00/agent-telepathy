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
Handles peer discovery, inbound/outbound WebSocket connections, message dispatch,
cryptographic verification, TTL enforcement, and A-DNS challenge-response authentication.
"""

import asyncio
import json
import logging
from pathlib import Path
import ssl
import time
from typing import Dict, Optional, Callable, Awaitable, Tuple, Type
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
    VectorEmbeddingPayload,
    PROTOCOL_VERSION
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
    
    Supports async context manager usage:
        async with TPCPNode(identity) as node:
            await node.send_message(...)
    """

    def __init__(
        self, 
        identity: AgentIdentity, 
        host: str = "127.0.0.1", 
        port: int = 8000, 
        adns_url: Optional[str] = None,
        identity_manager: Optional[AgentIdentityManager] = None,
        key_path: Optional[Path] = None,
        auto_save_key: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None
    ):
        self.identity = identity
        self.host = host
        self.port = port
        self.adns_url = adns_url
        self.ssl_context = ssl_context
        self._adns_ws: Optional[websockets.client.WebSocketClientProtocol] = None
        self._adns_registered = False
        
        # Initialize or reuse cryptographic trust layer
        if identity_manager:
            self.identity_manager = identity_manager
        else:
            self.identity_manager = AgentIdentityManager(
                key_path=key_path,
                auto_save=auto_save_key
            )
        self.identity.public_key = self.identity_manager.get_public_key_string()
        
        # Peer registry: maps agent_id (UUID) to (AgentIdentity, websocket_url)
        self.peer_registry: Dict[UUID, Tuple[AgentIdentity, str]] = {}
        
        # Connection pool: cached WebSocket connections to peers
        self._peer_connections: Dict[UUID, websockets.client.WebSocketClientProtocol] = {}
        
        # Shared Semantic Memory — CRDT LWW-Map
        self.shared_memory = LWWMap(node_id=str(self.identity.agent_id))
        
        # Vector Bank for semantic reception
        self.vector_bank = VectorBank(node_id=str(self.identity.agent_id))
        
        # Dead-Letter Queue (max 500 messages per peer)
        self.message_queue = MessageQueue(max_size_per_peer=500)

        # Deduplication Cache (Replay protection)
        self._seen_messages: Dict[UUID, float] = {}

        # Intent routing table
        self.handlers: Dict[Intent, IntentHandler] = {}
        
        # Register internal default handlers
        self.register_handler(Intent.HANDSHAKE, self._handle_handshake)
        self.register_handler(Intent.STATE_SYNC, self._handle_state_sync)
        self.register_handler(Intent.STATE_SYNC_VECTOR, self._handle_vector_sync)
        
        self._server: Optional[websockets.server.WebSocketServer] = None
        self._running = False

    # ── ASYNC CONTEXT MANAGER ────────────────────────────────────────────
    async def __aenter__(self) -> 'TPCPNode':
        await self.start_listening()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop_listening()
    # ─────────────────────────────────────────────────────────────────────

    def register_handler(self, intent: Intent, handler: IntentHandler) -> None:
        """Register a callback for a specific intent."""
        self.handlers[intent] = handler

    def register_peer(self, identity: AgentIdentity, address: str) -> None:
        """Add or update a peer in the registry."""
        self.peer_registry[identity.agent_id] = (identity, address)
        logger.info(f"Registered peer {identity.agent_id} at {address}")

    def remove_peer(self, agent_id: UUID) -> None:
        """Remove a peer from the registry and close any cached connection."""
        if agent_id in self.peer_registry:
            del self.peer_registry[agent_id]
            logger.info(f"Removed peer {agent_id}")
        if agent_id in self._peer_connections:
            asyncio.ensure_future(self._peer_connections[agent_id].close())
            del self._peer_connections[agent_id]

    def create_adapter(self, adapter_class: Type) -> object:
        """
        Factory method: create a framework adapter pre-wired with this node's identity manager.
        Usage: adapter = node.create_adapter(CrewAIAdapter)
        """
        return adapter_class(self.identity, identity_manager=self.identity_manager)

    async def start_listening(self) -> None:
        """Start the WebSocket server to listen for inbound TPCP messages."""
        logger.info(f"Node {self.identity.agent_id} starting on ws://{self.host}:{self.port}")
        logger.info(f"Protocol version: {PROTOCOL_VERSION}")
        
        await self.shared_memory.connect()
        
        self._server = await websockets.serve(
            self._handle_connection, 
            self.host, 
            self.port,
            ssl=self.ssl_context
        )
        self._running = True
        
        if self.adns_url:
            asyncio.create_task(self._connect_to_adns())

    async def _connect_to_adns(self) -> None:
        """
        Connects to the global A-DNS Relay Server with exponential backoff.
        Handles challenge-response authentication before routing begins.
        """
        backoff = 1.0
        max_backoff = 60.0

        while self._running:
            try:
                async with websockets.client.connect(self.adns_url, ssl=self.ssl_context) as ws:
                    self._adns_ws = ws
                    self._adns_registered = False
                    logger.info(f"Connected to Global A-DNS Relay at {self.adns_url}")
                    backoff = 1.0
                    
                    # Send initial handshake (will trigger challenge)
                    await self.broadcast_discovery()
                    
                    # Listen for messages (including challenges)
                    async for message in ws:
                        await self._process_adns_message(message, ws)
            except Exception as e:
                self._adns_ws = None
                self._adns_registered = False
                if self._running:
                    logger.warning(f"A-DNS connection lost: {e}. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)

    async def _process_adns_message(self, raw_message: str, ws) -> None:
        """Handle A-DNS relay messages, including challenge-response flow."""
        try:
            data = json.loads(raw_message)
            
            # Handle A-DNS challenge
            if data.get("type") == "ADNS_CHALLENGE":
                nonce = data.get("nonce", "")
                logger.info(f"Received A-DNS challenge. Signing nonce...")
                
                # Sign the nonce with our private key
                nonce_bytes = nonce.encode('utf-8')
                signed_nonce = self.identity_manager.sign_bytes(nonce_bytes)
                
                # Build challenge response envelope
                response = json.dumps({
                    "header": {
                        "sender_id": str(self.identity.agent_id),
                        "intent": "Challenge_Response"
                    },
                    "payload": {
                        "content": signed_nonce
                    }
                })
                await ws.send(response)
                logger.info("Sent signed challenge response to A-DNS.")
                return
            
            # Handle registration confirmation
            if data.get("type") == "ADNS_REGISTERED":
                self._adns_registered = True
                logger.info("✓ Successfully verified and registered with A-DNS relay.")
                return
            
            # Standard TPCP envelope — process normally
            await self._process_inbound(raw_message, ws)
            
        except json.JSONDecodeError:
            logger.error("Non-JSON message from A-DNS relay.")
        except Exception as e:
            logger.error(f"Error processing A-DNS message: {e}")

    async def stop_listening(self) -> None:
        """Stop the WebSocket server gracefully and close all connections."""
        self._running = False
        
        # Close all cached peer connections
        for uid, ws in list(self._peer_connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self._peer_connections.clear()
        
        await self.shared_memory.close()
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info(f"Node {self.identity.agent_id} stopped listening.")
        if self._adns_ws:
            try:
                await self._adns_ws.close()
            except Exception:
                pass

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
        Deserialize, enforce TTL, cryptographically verify, and route incoming messages.
        """
        try:
            if isinstance(raw_message, bytes):
                raw_message = raw_message.decode('utf-8')

            data = json.loads(raw_message)
            envelope = TPCPEnvelope.model_validate(data)
            
            logger.debug(f"Received {envelope.header.intent.value} from {envelope.header.sender_id}")
            
            # ── TTL ENFORCEMENT ──────────────────────────────────────────────
            if envelope.header.ttl <= 0:
                logger.warning(f"TTL expired for packet from {envelope.header.sender_id}. Dropping.")
                return
            # ────────────────────────────────────────────────────────────────
            
            # ── DEDUPLICATION (REPLAY PROTECTION) ────────────────────────────
            current_time = time.monotonic()
            if envelope.header.message_id in self._seen_messages:
                logger.warning(f"Duplicate message {envelope.header.message_id} detected. Dropping.")
                return
            self._seen_messages[envelope.header.message_id] = current_time
            
            # Clean up old seen messages periodically (e.g., older than 5 minutes)
            if len(self._seen_messages) > 1000:
                expired = current_time - 300  # 5 minutes
                self._seen_messages = {k: v for k, v in self._seen_messages.items() if v > expired}
            # ────────────────────────────────────────────────────────────────
            
            # ── SECURITY MIDDLEWARE ──────────────────────────────────────────
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
            
            # Dispatch to handler
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
        """Auto-register handshake senders in the peer registry with signature verification."""
        logger.info(f"Handshake received from {envelope.header.sender_id}")
        
        if isinstance(envelope.payload, TextPayload):
            try:
                sender_data = json.loads(envelope.payload.content)
                sender_identity = AgentIdentity.model_validate(sender_data)
                
                if not envelope.signature:
                    logger.warning(f"Handshake dropped: Unsigned packet from {envelope.header.sender_id}")
                    return
                
                payload_dict = envelope.payload.model_dump()
                if not AgentIdentityManager.verify_signature(sender_identity.public_key, envelope.signature, payload_dict):
                    logger.warning(f"Handshake dropped: INVALID SIGNATURE from {envelope.header.sender_id}")
                    return
                
                peer_host = websocket.remote_address[0] if websocket.remote_address else "unknown"
                self.peer_registry[sender_identity.agent_id] = (sender_identity, f"ws://{peer_host}")
                logger.info(f"Auto-registered peer: {sender_identity.framework} ({sender_identity.agent_id})")
            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"Could not auto-register peer from handshake: {e}")
        
    async def _handle_state_sync(self, envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        """Merge CRDTSyncPayloads into local shared memory."""
        if not isinstance(envelope.payload, CRDTSyncPayload):
            logger.error("STATE_SYNC envelope did not contain a CRDTSyncPayload.")
            return

        payload = envelope.payload
        if payload.crdt_type == "LWW-Map":
            logger.info(f"Merging incoming LWW-Map from {envelope.header.sender_id}...")
            await self.shared_memory.merge(payload.state)
            logger.info(f"[Semantic State Updated] Memory: {self.shared_memory.to_dict()}")
        else:
            logger.warning(f"Unsupported CRDT type: {payload.crdt_type}")

    async def _handle_vector_sync(self, envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        """Ingest dense contextual vectors into the local VectorBank."""
        if not isinstance(envelope.payload, VectorEmbeddingPayload):
            logger.error(f"STATE_SYNC_VECTOR envelope lacked VectorEmbeddingPayload.")
            return

        payload = envelope.payload
        logger.info(f"Ingesting vector [{payload.model_id} | {payload.dimensions}d] from {envelope.header.sender_id}")
        
        self.vector_bank.store_vector(
            payload_id=envelope.header.message_id,
            vector=payload.vector,
            model_id=payload.model_id,
            raw_text=payload.raw_text_fallback
        )
        logger.info(f"[Vector Bank] Size: {self.vector_bank.total_vectors}")

    async def send_message(self, target_id: UUID, intent: Intent, payload: Payload) -> None:
        """Sign and dispatch a TPCP message to a specific peer in the registry."""
        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=intent,
            protocol_version=PROTOCOL_VERSION
        )
        
        payload_dict = payload.model_dump()
        signature_str = self.identity_manager.sign_payload(payload_dict)
        
        envelope = TPCPEnvelope(header=header, payload=payload, signature=signature_str)
        await self._dispatch_envelope(target_id, envelope)

    async def _get_peer_connection(self, target_id: UUID) -> Optional[websockets.client.WebSocketClientProtocol]:
        """Get or create a pooled WebSocket connection to a peer."""
        if target_id in self._peer_connections:
            ws = self._peer_connections[target_id]
            if not ws.closed:
                return ws
            # Stale, remove
            del self._peer_connections[target_id]
        
        if target_id not in self.peer_registry:
            return None
        
        _, endpoint = self.peer_registry[target_id]
        try:
            ws = await websockets.client.connect(endpoint, ssl=self.ssl_context)
            self._peer_connections[target_id] = ws
            return ws
        except Exception:
            return None

    async def _dispatch_envelope(self, target_id: UUID, envelope: TPCPEnvelope) -> None:
        """Send an envelope using connection pooling. Falls back to DLQ on failure."""
        if target_id not in self.peer_registry:
            logger.error(f"Peer {target_id} not in registry. Pushing to DLQ.")
            await self.message_queue.enqueue(target_id, envelope)
            return
        
        ws = await self._get_peer_connection(target_id)
        if ws:
            try:
                await ws.send(envelope.model_dump_json())
                logger.debug(f"Sent message {envelope.header.message_id} to {target_id}.")
                return
            except Exception as e:
                logger.warning(f"Connection to {target_id} dropped: {e}.")
                if target_id in self._peer_connections:
                    del self._peer_connections[target_id]
        
        logger.warning(f"Pushing to DLQ for {target_id}.")
        await self.message_queue.enqueue(target_id, envelope)
        asyncio.create_task(self._reconnect_and_drain(target_id))

    async def _reconnect_and_drain(self, target_id: UUID) -> None:
        """Exponential backoff reconnection. Drains DLQ one-at-a-time safely."""
        if target_id not in self.peer_registry:
            return
            
        _, endpoint = self.peer_registry[target_id]
        backoff = 1.0
        max_backoff = 60.0
        
        while self._running and await self.message_queue.has_messages(target_id):
            try:
                ws = await websockets.client.connect(endpoint, ssl=self.ssl_context)
                self._peer_connections[target_id] = ws
                logger.info(f"[Network Restored] Draining DLQ for {target_id}...")
                    
                while await self.message_queue.has_messages(target_id):
                    msg = await self.message_queue.dequeue_one(target_id)
                    if msg is None:
                        break
                    try:
                        await ws.send(msg.model_dump_json())
                        logger.debug(f"Drained {msg.header.message_id} to {target_id}.")
                    except Exception:
                        await self.message_queue.enqueue_front(target_id, msg)
                        raise
                break
            except Exception as e:
                logger.debug(f"Reconnection to {target_id} failed: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def broadcast_discovery(self, seed_nodes: Optional[list[str]] = None) -> None:
        """Announce this node's identity to seed peers or via the A-DNS relay."""
        seed_nodes = seed_nodes or []
        target_id = UUID(int=0)
        
        header = MessageHeader(
            sender_id=self.identity.agent_id,
            receiver_id=target_id,
            intent=Intent.HANDSHAKE,
            protocol_version=PROTOCOL_VERSION
        )
        
        payload = TextPayload(content=self.identity.model_dump_json())
        signature_str = self.identity_manager.sign_payload(payload.model_dump())
        
        envelope = TPCPEnvelope(header=header, payload=payload, signature=signature_str)
        serialized = envelope.model_dump_json()
        
        if self._adns_ws:
            try:
                await self._adns_ws.send(serialized)
            except Exception as e:
                logger.error(f"A-DNS broadcast failed: {e}")
                
        if seed_nodes:
            logger.info(f"Broadcasting discovery to {len(seed_nodes)} seed nodes.")
            for address in seed_nodes:
                try:
                    async with connect(address, ssl=self.ssl_context) as websocket:
                        await websocket.send(serialized)
                        logger.debug(f"Sent discovery to {address}")
                except Exception as e:
                    logger.debug(f"Discovery failed for {address}: {e}")
