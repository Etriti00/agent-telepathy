import asyncio
import json
import logging
from uuid import uuid4

from tpcp.core.node import TPCPNode
from tpcp.schemas.envelope import AgentIdentity, Intent, CRDTSyncPayload

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def run_state_sync_demo():
    print("\n" + "="*70)
    print("🧠 TPCP Shared Memory Validation (LWW-Map CRDT)")
    print("="*70 + "\n")

    # Node A: Hunter Agent (LangGraph)
    identity_a = AgentIdentity(
        agent_id=uuid4(),
        framework="LangGraph",
        capabilities=["web_search", "data_extraction"],
        public_key="pub_key_hunter_A"
    )
    node_a = TPCPNode(identity=identity_a, host="127.0.0.1", port=8000)

    # Node B: Scorer Agent (CrewAI)
    identity_b = AgentIdentity(
        agent_id=uuid4(),
        framework="CrewAI",
        capabilities=["data_scoring", "report_generation"],
        public_key="pub_key_scorer_B"
    )
    node_b = TPCPNode(identity=identity_b, host="127.0.0.1", port=8001)

    # Pre-register each other to bypass discovery for this memory demo
    node_a.register_peer(identity_b, "ws://127.0.0.1:8001")
    node_b.register_peer(identity_a, "ws://127.0.0.1:8000")

    await node_a.start_listening()
    await node_b.start_listening()
    await asyncio.sleep(0.5)

    print("\n[Time T=1] Both nodes independently mutate local state...")
    
    # 1. We mock simultaneous local mutations. Notice we mock timestamp logic.
    # In a live environment, the LWWMap automatically handles tracking Lamport timestamps.
    node_a.shared_memory.set(key="company", value="TechCorp", timestamp=1)
    node_a.shared_memory.set(key="title", value="CTO", timestamp=1)
    print(f"Node A local memory: {node_a.shared_memory.to_dict()}")

    # 2. Node B creates entirely different state keys simultaneously
    node_b.shared_memory.set(key="lead_score", value=95, timestamp=2)
    node_b.shared_memory.set(key="intent", value="high", timestamp=2)
    print(f"Node B local memory: {node_b.shared_memory.to_dict()}")

    print("\n[Time T=3] Concurrent State_Sync broadcasts...")
    
    # In a naive REST API backend, two nodes pushing at the same time might overwrite each other.
    # We serialize the full local graph and attach the strict CRDT type signature.
    payload_a = CRDTSyncPayload(
        crdt_type="LWW-Map",
        state=node_a.shared_memory.serialize_state(),
        vector_clock={"timestamp": node_a.shared_memory.logical_clock}
    )
    
    payload_b = CRDTSyncPayload(
        crdt_type="LWW-Map",
        state=node_b.shared_memory.serialize_state(),
        vector_clock={"timestamp": node_b.shared_memory.logical_clock}
    )

    # Broadcast concurrently
    async def send_a():
        await node_a.send_message(identity_b.agent_id, Intent.STATE_SYNC, payload_a)

    async def send_b():
        await node_b.send_message(identity_a.agent_id, Intent.STATE_SYNC, payload_b)

    # `asyncio.gather` guarantees perfect concurrency to simulate a network race condition.
    await asyncio.gather(send_a(), send_b())
    
    # Allow local Event loop traversal 
    await asyncio.sleep(1.0)

    print("\n" + "-"*70)
    print("🔍 Final State Resolution Validation")
    print("-"*70)
    
    final_a = node_a.shared_memory.to_dict()
    final_b = node_b.shared_memory.to_dict()
    
    print(f"Node A converged memory: {json.dumps(final_a, indent=2)}")
    print(f"Node B converged memory: {json.dumps(final_b, indent=2)}")
    
    if final_a == final_b:
        print("\n✅ SUCCESS: Mathematical merge achieved. Race conditions resolved successfully.")
    else:
        print("\n❌ FAILURE: Divergent memory states detected.")

    await node_a.stop_listening()
    await node_b.stop_listening()

if __name__ == "__main__":
    asyncio.run(run_state_sync_demo())
