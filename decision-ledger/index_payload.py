"""Create the Qdrant payload index the NodeSet filter needs.

cognee stores each point's NodeSet tags in a `belongs_to_set` payload field, but it
doesn't index that field. Qdrant refuses to filter on an unindexed payload key —
it answers 400 "Index required but not found" — so every clearance-scoped search
silently returns nothing, and the whole ACL layer degrades to a fallback.

One keyword index per collection fixes it. Idempotent: safe to re-run.

    python index_payload.py
"""

from __future__ import annotations

import os

import bootstrap  # noqa: F401  (loads .env, registers the Qdrant adapter)

from qdrant_client import QdrantClient
from qdrant_client.http.models import PayloadSchemaType

FIELD = "belongs_to_set"


def main() -> None:
    client = QdrantClient(
        url=os.getenv("VECTOR_DB_URL"), api_key=os.getenv("VECTOR_DB_KEY") or None, timeout=30
    )
    collections = [c.name for c in client.get_collections().collections]
    if not collections:
        raise SystemExit("No Qdrant collections found — run `make ingest` first.")

    for name in collections:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=FIELD,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )
            print(f"  indexed {FIELD} on {name}")
        except Exception as exc:  # noqa: BLE001 - already-exists is the common case
            print(f"  {name}: {type(exc).__name__} (likely already indexed)")

    print(f"\nDone. Clearance-scoped search can now filter on {FIELD}.")


if __name__ == "__main__":
    main()
