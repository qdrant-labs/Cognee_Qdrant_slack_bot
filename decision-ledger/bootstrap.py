"""Import this before `cognee` anywhere in the project.

Two things have to happen in order, and getting them backwards fails confusingly:

1. `.env` is loaded — cognee reads its config at import time, so a late load_dotenv
   leaves you with defaults and no warning.
2. The Qdrant adapter registers itself. Qdrant support ships as a separate
   community package; without the register import cognee reports
   "Unsupported vector database provider: qdrant" even though the package is installed.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

if os.getenv("VECTOR_DB_PROVIDER", "").lower() == "qdrant":
    try:
        import cognee_community_vector_adapter_qdrant.register  # noqa: F401
    except ImportError as exc:  # pragma: no cover - surfaced to the user immediately
        raise SystemExit(
            "VECTOR_DB_PROVIDER=qdrant but the adapter isn't installed. Run:\n"
            "  pip install --no-deps cognee-community-vector-adapter-qdrant==0.4.0"
        ) from exc
