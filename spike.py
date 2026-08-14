"""Spike script to validate Groq + Cognee + Qdrant + FastEmbed."""

import asyncio
import os
import src.cvlizer.config  # initializes Qdrant adapter & loads .env
import cognee

SAMPLE_CV = """# Alice Smith
Senior Backend Engineer with 8 years of experience building distributed systems in Python, Go, and Rust.
Expert in PostgreSQL, Redis, Kubernetes, Kafka, and FastAPI.
Led migration of monolithic payment services to event-driven microservices handling 50k req/s.
"""

async def run_spike():
    print("=== 1. Checking Environment ===")
    print(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
    print(f"LLM_MODEL: {os.getenv('LLM_MODEL')}")
    print(f"LLM_EXTRACTION_MODEL: {os.getenv('LLM_EXTRACTION_MODEL')}")
    print(f"LLM_API_KEY set: {bool(os.getenv('LLM_API_KEY')) and not os.getenv('LLM_API_KEY').startswith('gsk_your')}")
    print(f"VECTOR_DB_URL: {os.getenv('VECTOR_DB_URL')}")

    if not os.getenv("LLM_API_KEY") or os.getenv("LLM_API_KEY").startswith("gsk_your"):
        print("\n⚠️ LLM_API_KEY is not configured with a valid key in .env. Please set your Groq API key in .env.")
        return

    print("\n=== 2. Pruning previous Cognee data ===")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system()
    print("Pruned successfully.")

    print("\n=== 3. Adding sample CV to Cognee ===")
    await cognee.add(
        SAMPLE_CV,
        dataset_name="cvs",
        node_set=["cv", "candidate:alice-smith"],
    )
    print("Sample CV added.")

    print("\n=== 4. Running cognify() ===")
    await cognee.cognify(datasets=["cvs"])
    print("Cognify completed successfully.")

    print("\n=== 5. Testing SearchType.CHUNKS ===")
    query = "Experienced Python backend engineer with FastAPI and microservices"
    chunks_results = await cognee.search(
        query_text=query,
        query_type=cognee.SearchType.CHUNKS,
        datasets=["cvs"],
    )
    print(f"Returned {len(chunks_results)} chunk results:")
    for i, r in enumerate(chunks_results):
        print(f"--- Chunk Result {i} ---")
        print(f"Type: {type(r)}")
        print(f"Attributes / dict: {getattr(r, '__dict__', r)}")
        if hasattr(r, "score"):
            print(f"Score: {r.score}")
        if hasattr(r, "payload"):
            print(f"Payload: {r.payload}")

    print("\n=== 6. Testing SearchType.GRAPH_COMPLETION ===")
    graph_query = (
        f"Based on the CVs in the graph, evaluate fit for: '{query}'. "
        "Return a JSON object with: name, fit_score (0-100), quotes (list of strings), reason."
    )
    graph_results = await cognee.search(
        query_text=graph_query,
        query_type=cognee.SearchType.GRAPH_COMPLETION,
        datasets=["cvs"],
    )
    print(f"Graph Completion Result:\n{graph_results}")

if __name__ == "__main__":
    asyncio.run(run_spike())
