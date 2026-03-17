import threading
from uuid import uuid4

from tpcp.memory.vector import VectorBank


def test_vector_bank_store_and_get():
    bank = VectorBank("test-node")
    pid = uuid4()
    bank.store_vector(pid, [1.0, 2.0, 3.0], "model-a", "hello")
    result = bank.get_vector(pid)
    assert result is not None
    assert result["model_id"] == "model-a"
    assert result["raw_text_fallback"] == "hello"
    assert result["vector"] == [1.0, 2.0, 3.0]


def test_get_vector_returns_defensive_copy():
    """Mutating the returned vector must not corrupt the stored embedding."""
    bank = VectorBank("test-node")
    pid = uuid4()
    bank.store_vector(pid, [1.0, 2.0, 3.0], "test-model")

    result = bank.get_vector(pid)
    assert result is not None
    # Mutate the returned list
    result["vector"].append(999.0)
    result["vector"][0] = -1.0

    # Re-fetch — must be the original, unmodified vector
    fresh = bank.get_vector(pid)
    assert fresh["vector"] == [1.0, 2.0, 3.0], "Stored vector was mutated by caller"


def test_vector_bank_get_missing():
    bank = VectorBank("test-node")
    assert bank.get_vector(uuid4()) is None


def test_vector_bank_list_vectors():
    bank = VectorBank("test-node")
    bank.store_vector(uuid4(), [1.0, 2.0], "model-a")
    bank.store_vector(uuid4(), [3.0, 4.0], "model-b", "text")
    listing = bank.list_vectors()
    assert len(listing) == 2
    assert any(v["model_id"] == "model-a" for v in listing)
    assert any(v["model_id"] == "model-b" for v in listing)


def test_vector_bank_search():
    bank = VectorBank("test-node")
    pid1 = uuid4()
    pid2 = uuid4()
    bank.store_vector(pid1, [1.0, 0.0], "model-a", "parallel")
    bank.store_vector(pid2, [0.0, 1.0], "model-a", "orthogonal")
    results = bank.search([1.0, 0.0], top_k=2)
    assert len(results) == 2
    # First result should be the parallel vector (similarity ~1.0)
    assert results[0][0] == pid1
    assert results[0][1] > 0.99


def test_vector_bank_concurrent_access():
    """Verify thread safety: concurrent store and read operations don't crash."""
    bank = VectorBank("test-node")
    errors = []

    def store_many():
        for i in range(100):
            try:
                bank.store_vector(uuid4(), [float(i)] * 16, f"model-{i}")
            except Exception as e:
                errors.append(e)

    def read_many():
        for _ in range(100):
            try:
                bank.list_vectors()
                bank.search([1.0] * 16, top_k=3)
            except Exception as e:
                errors.append(e)

    threads = [
        threading.Thread(target=store_many),
        threading.Thread(target=read_many),
        threading.Thread(target=store_many),
        threading.Thread(target=read_many),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"Concurrent access errors: {errors}"
