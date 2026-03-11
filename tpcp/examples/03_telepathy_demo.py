import asyncio
import logging
from uuid import uuid4
import random

from tpcp.core.node import TPCPNode
from tpcp.schemas.envelope import AgentIdentity, Intent, VectorEmbeddingPayload

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def run_telepathy_demo():
    print("\n" + "="*70)
    print("🧠 TPCP Telepathy (Vector State Synchronization)")
    print("="*70 + "\n")

    # Node A: Hunter Agent
    identity_a = AgentIdentity(
        agent_id=uuid4(),
        framework="LangGraph",
        capabilities=["web_search", "embedding_generation"],
        public_key="pub_key_hunter_A"
    )
    node_a = TPCPNode(identity=identity_a, host="127.0.0.1", port=8000)

    # Node B: Scorer Agent
    identity_b = AgentIdentity(
        agent_id=uuid4(),
        framework="CrewAI",
        capabilities=["data_scoring", "report_generation"],
        public_key="pub_key_scorer_B"
    )
    node_b = TPCPNode(identity=identity_b, host="127.0.0.1", port=8001)

    # Pre-register each other
    node_a.register_peer(identity_b, "ws://127.0.0.1:8001")
    node_b.register_peer(identity_a, "ws://127.0.0.1:8000")

    await node_a.start_listening()
    await node_b.start_listening()
    await asyncio.sleep(0.5)

    print("\n[Node A] Generating massive dense context embedding...")
    
    # Text bottlenecks limit agents to ~100k tokens per request.
    # Telepathy breaks this by directly piping deep-learning float arrays.
    # We mock generation of a 1536-dimensional float vector (OpenAI small standard embedding model)
    raw_context = "Lead Bio: Ex-OpenAI researcher now building decentralized AI orchestration..."
    mock_1536_vector = [random.uniform(-1.0, 1.0) for _ in range(1536)]
    
    # Create the strictly validated Pydantic schema
    # If `mock_1536_vector` did not contain exactly 1536 elements, the model would throw a validation error.
    payload_a = VectorEmbeddingPayload(
        model_id="text-embedding-3-small",
        dimensions=1536,
        vector=mock_1536_vector,
        raw_text_fallback=raw_context
    )
    
    print(f"[Node A] Broadcasting 1536d Tensor to Node B via STATE_SYNC_VECTOR...")
    
    # Node A directly transmits raw vector cognition straight into Node B's memory banks
    await node_a.send_message(identity_b.agent_id, Intent.STATE_SYNC_VECTOR, payload_a)
    
    # Allow network traversal
    await asyncio.sleep(1.0)

    print("\n" + "-"*70)
    print("🔍 Final State Resolution Validation")
    print("-"*70)
    
    # Validate receiver inherited the semantic chunk successfully
    if node_b.vector_bank.total_vectors == 1:
        # Retrieve the key dynamically (since we didn't track the exact message ID generated inside send_message)
        # For demo purposes, we can just fetch the first item in the bank.
        stored_dict = list(node_b.vector_bank._embeddings.values())[0]
        
        print("\n✅ SUCCESS: Dense Vector transmission received and validated by Node B.")
        print(f"   Model: {stored_dict['model_id']}")
        print(f"   Shape: [{len(stored_dict['vector'])}]")
        print(f"   Sample (first 5): {stored_dict['vector'][:5]}")
        
    else:
        print("\n❌ FAILURE: Vector bank did not receive the payload.")

    await node_a.stop_listening()
    await node_b.stop_listening()

if __name__ == "__main__":
    asyncio.run(run_telepathy_demo())
