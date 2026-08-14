"""Preflight. Run this before `make ingest` — it fails in seconds instead of
failing halfway through a cognify run.

Checks, in order: .env is loaded, Qdrant answers, embeddings run locally, and the
LLM can return structured output (which is what cognify actually needs — a model
that chats but can't fill a JSON schema will fail deep inside the pipeline).
"""

from __future__ import annotations

import os
import sys

import bootstrap  # noqa: F401  (loads .env, registers the Qdrant adapter)

OK, BAD = "\033[32m  ok \033[0m", "\033[31m FAIL\033[0m"
failures: list[str] = []


def report(label: str, passed: bool, detail: str = "") -> None:
    print(f"[{OK if passed else BAD}] {label}" + (f" — {detail}" if detail else ""))
    if not passed:
        failures.append(label)


def check_config() -> None:
    provider = os.getenv("LLM_PROVIDER", "")
    model = os.getenv("LLM_MODEL", "")
    key = os.getenv("LLM_API_KEY", "")
    report("LLM_PROVIDER / LLM_MODEL set", bool(provider and model), f"{provider} / {model}")
    report("LLM_API_KEY set", bool(key), f"{len(key)} chars" if key else "empty")
    report(
        "EMBEDDING_PROVIDER is fastembed (local, no key needed)",
        os.getenv("EMBEDDING_PROVIDER") == "fastembed",
        os.getenv("EMBEDDING_PROVIDER", "unset"),
    )
    report(
        "VECTOR_DB_PROVIDER is qdrant",
        os.getenv("VECTOR_DB_PROVIDER") == "qdrant",
        os.getenv("VECTOR_DB_PROVIDER", "unset"),
    )


def check_qdrant() -> None:
    url = os.getenv("VECTOR_DB_URL", "")
    if not url:
        report("Qdrant reachable", False, "VECTOR_DB_URL is empty")
        return
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=url, api_key=os.getenv("VECTOR_DB_KEY") or None, timeout=10)
        collections = client.get_collections().collections
        report("Qdrant reachable", True, f"{url} — {len(collections)} collection(s)")
    except Exception as exc:  # noqa: BLE001 - preflight reports, never raises
        report("Qdrant reachable", False, f"{type(exc).__name__}: {exc}")


def check_embeddings() -> None:
    try:
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
        vector = next(iter(model.embed(["decision ledger preflight"])))
        expected = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
        report(
            "Local embeddings work",
            len(vector) == expected,
            f"{len(vector)} dims (expected {expected})",
        )
    except Exception as exc:  # noqa: BLE001
        report("Local embeddings work", False, f"{type(exc).__name__}: {exc}")


def check_llm() -> None:
    """cognify needs structured output, so test exactly that, not a plain chat call."""
    try:
        import litellm
        from pydantic import BaseModel

        class Probe(BaseModel):
            answer: str

        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        model = os.getenv("LLM_MODEL", "")
        if provider == "anthropic" and not model.startswith("anthropic/"):
            model = f"anthropic/{model}"

        kwargs = {"api_key": os.getenv("LLM_API_KEY")}
        if os.getenv("LLM_ENDPOINT"):
            kwargs["api_base"] = os.getenv("LLM_ENDPOINT")

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            response_format=Probe,
            max_tokens=64,
            **kwargs,
        )
        content = response.choices[0].message.content
        report("LLM structured output works", bool(content), str(content)[:80])
    except Exception as exc:  # noqa: BLE001
        report("LLM structured output works", False, f"{type(exc).__name__}: {str(exc)[:200]}")


def main() -> int:
    print("\nDecision Ledger preflight\n" + "-" * 60)
    check_config()
    check_qdrant()
    check_embeddings()
    check_llm()
    print("-" * 60)
    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        print("Fix these before running `make ingest`.\n")
        return 1
    print("\nAll checks passed. Run: make ingest\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
