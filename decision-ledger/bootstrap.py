"""Import this before `cognee` anywhere in the project.

Two things have to happen in order, and getting them backwards fails confusingly:

1. `.env` is loaded — cognee reads its config at import time, so a late load_dotenv
   leaves you with defaults and no warning.
2. The Qdrant adapter registers itself. Qdrant support ships as a separate
   community package; without the register import cognee reports
   "Unsupported vector database provider: qdrant" even though the package is installed.
"""

from __future__ import annotations

import atexit
import logging
import os

from dotenv import load_dotenv

load_dotenv()

# cognee logs ~30 INFO lines at import — enough to push the demo panels off a
# projector. ERROR keeps genuine failures visible (a Qdrant 400 still prints).
# Override with LOG_LEVEL=INFO in .env when debugging.
os.environ.setdefault("LOG_LEVEL", "ERROR")


@atexit.register
def _quiet_shutdown() -> None:
    """Stop teardown-time log records from reaching the console.

    Async HTTP clients somewhere under cognee (litellm's aiohttp among them) get
    collected after the event loop is gone, and their __del__ logs "Unclosed client
    session". cognee routes logging through rich, rich can no longer import during
    interpreter shutdown, and the result is a screen of ImportError tracebacks printed
    after the demo output — alarming and completely meaningless.

    atexit runs before that final GC pass, so disabling logging here means those
    records are never emitted. raiseExceptions=False additionally suppresses the
    "--- Logging error ---" report if anything still slips through.
    """
    logging.raiseExceptions = False
    logging.disable(logging.CRITICAL)

if os.getenv("VECTOR_DB_PROVIDER", "").lower() == "qdrant":
    try:
        import cognee_community_vector_adapter_qdrant.register  # noqa: F401
    except ImportError as exc:  # pragma: no cover - surfaced to the user immediately
        raise SystemExit(
            "VECTOR_DB_PROVIDER=qdrant but the adapter isn't installed. Run:\n"
            "  pip install --no-deps cognee-community-vector-adapter-qdrant==0.4.0"
        ) from exc
