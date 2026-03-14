import asyncio
import json
import logging
from uuid import uuid4
from websockets.server import WebSocketServerProtocol

from tpcp.core.node import TPCPNode
from tpcp.schemas.envelope import AgentIdentity, Intent, TPCPEnvelope
from tpcp.adapters.langgraph_adapter import LangGraphAdapter
from tpcp.adapters.crewai_adapter import CrewAIAdapter

# Configure logging to show clean terminal output
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def main():
    print("\n" + "="*60)
    print("🚀 TPCP Live Handshake Demonstration")
    print("="*60 + "\n")

    # 1. Initialize Identities & Adapters
    # Node A: The initiator (e.g., a web scraping agent powered by LangGraph)
    # The identity tracks the agent's framework and capabilities for node discovery routing.
    identity_a = AgentIdentity(
        agent_id=uuid4(),
        framework="LangGraph",
        capabilities=["web_search", "data_extraction"],
        public_key="pub_key_hunter_A"
    )
    adapter_a = LangGraphAdapter(identity_a)
    node_a = TPCPNode(identity=identity_a, host="127.0.0.1", port=8000)

    # Node B: The receiver (e.g., a data analyzing agent powered by CrewAI)
    # Notice we declare discrete capabilities. If we were using an A-DNS relay,
    # nodes could dynamically query the network for agents that provide 'data_scoring'.
    identity_b = AgentIdentity(
        agent_id=uuid4(),
        framework="CrewAI",
        capabilities=["data_scoring", "report_generation"],
        public_key="pub_key_scorer_B"
    )
    adapter_b = CrewAIAdapter(identity_b)
    node_b = TPCPNode(identity=identity_b, host="127.0.0.1", port=8001)

    # We augment Node B's handshake handler to actively respond and print validation
    async def custom_handshake_responder(envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        print(f"\n[Node B (CrewAI)] 📥 Received DISCOVER_SYN from {envelope.header.sender_id}")
        print("-" * 40)
        print("Raw Envelope Payload JSON Exchange:")
        print(json.dumps(json.loads(envelope.model_dump_json()), indent=2))
        print("-" * 40)

        # Node B intercepts the global broadcast and reads the payload text.
        # It parses the JSON representation of Node A's AgentIdentity.
        sender_identity_dict = json.loads(envelope.payload.content)
        sender_identity = AgentIdentity.model_validate(sender_identity_dict)
        
        # We explicitly map the UUID to the socket connection in memory.
        # This allows all future `send_message` commands to route instantly without discovery.
        node_b.register_peer(sender_identity, "ws://127.0.0.1:8000")
        print(f"[Node B (CrewAI)] ✅ Registered new peer '{sender_identity.framework}' in memory.")

        # In TPCP, handshakes act as two-way TCP syn-acks.
        # Node B confirms receipt by returning a native framework thought using an adapter.
        print("[Node B (CrewAI)] 📤 Sending CAPABILITY_ACK response back to Node A...")
        
        # This dictionary mimics CrewAI's arbitrary internal dictionary structures.
        native_ack_thought = {
            "status": "CAPABILITY_ACK",
            "message": "Acknowledged. Scorer Agent is ready.",
            "supported_intents": ["Task_Request", "Critique"]
        }
        
        ack_envelope = await adapter_b.pack_thought(native_ack_thought, sender_identity.agent_id, Intent.HANDSHAKE)
        
        # Send physical response back to Node A's listening server via the node manager
        asyncio.create_task(node_b.send_message(
            target_id=sender_identity.agent_id,
            intent=Intent.HANDSHAKE,
            payload=ack_envelope.payload
        ))

    # We augment Node A's handshake handler to receive the CAPABILITY_ACK
    async def custom_ack_receiver(envelope: TPCPEnvelope, websocket: WebSocketServerProtocol) -> None:
        print(f"\n[Node A (LangGraph)] 📥 Received CAPABILITY_ACK from {envelope.header.sender_id}")
        
        # Unpack the response using the LangGraph adapter to format the native structure
        native_state_update = await adapter_a.unpack_payload(envelope)
        
        print("-" * 40)
        print("Unpacked payload translated to LangGraph State Dict:")
        print(json.dumps(native_state_update, indent=2))
        print("-" * 40)
        print("[Node A (LangGraph)] 🤝 Handshake successful. Frameworks are bridged.")
        
        # Signal the event loop to finish
        execution_complete.set()

    node_b.register_handler(Intent.HANDSHAKE, custom_handshake_responder)
    node_a.register_handler(Intent.HANDSHAKE, custom_ack_receiver)

    # 2. Start Both Nodes
    await node_a.start_listening()
    await node_b.start_listening()
    
    # 3. Execution Waiter
    execution_complete = asyncio.Event()

    await asyncio.sleep(0.5) # ensure servers are up
    
    print("\n[Node A (LangGraph)] 📡 Broadcasting DISCOVER_SYN to seed peer (ws://127.0.0.1:8001)...")
    # Broadcast Discovery automatically generates an Intent.HANDSHAKE envelope, 
    # signs it with Ed25519 cryptography, and loops it outward to seed servers.
    await node_a.broadcast_discovery(["ws://127.0.0.1:8001"])

    # Wait for the async events (Handshake -> Ack -> Validation) to finish
    await asyncio.wait_for(execution_complete.wait(), timeout=5.0)
    
    print("\n" + "="*60)
    print("🏁 Execution Complete. Shutting down nodes.")
    print("="*60 + "\n")
    
    await node_a.stop_listening()
    await node_b.stop_listening()

if __name__ == "__main__":
    asyncio.run(main())
