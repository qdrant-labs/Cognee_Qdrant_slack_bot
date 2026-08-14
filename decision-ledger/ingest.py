"""Slack export -> cognee typed decision graph (backed by Qdrant).

One document per thread, not per message: a decision and the constraints raised in
its replies belong in the same chunk, otherwise the extractor never sees that they
are related.

Visibility is carried into the graph as a NodeSet tag on every document
(`channel:eng-private`). retrieve.py filters on those tags, so a persona's clearance
is enforced at retrieval time rather than by hoping the LLM keeps a secret.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import bootstrap  # noqa: F401  (loads .env, registers the Qdrant adapter)

import cognee  # noqa: E402  (must import after load_dotenv so config picks up .env)

from models import EXTRACTION_PROMPT, DecisionGraph  # noqa: E402

ROOT = Path(__file__).parent
EXPORT_DIR = ROOT / "fixtures" / "slack_export"
DATASET = "slack_workspace"
WORKSPACE = "acme"


def _permalink(channel_id: str, ts: str) -> str:
    return f"https://{WORKSPACE}.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"


def _fmt_date(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d")


def load_export() -> list[dict]:
    """Return one document per thread, tagged with its channel."""
    users = {u["id"]: u for u in json.loads((EXPORT_DIR / "users.json").read_text())}
    channels = json.loads((EXPORT_DIR / "channels.json").read_text())

    documents: list[dict] = []
    for channel in channels:
        name, cid = channel["name"], channel["id"]
        messages: list[dict] = []
        for day_file in sorted((EXPORT_DIR / name).glob("*.json")):
            messages.extend(json.loads(day_file.read_text()))
        messages.sort(key=lambda m: float(m["ts"]))

        # Group into threads: a message with thread_ts belongs to that root,
        # a message without one is its own single-message thread.
        threads: dict[str, list[dict]] = {}
        for msg in messages:
            threads.setdefault(msg.get("thread_ts", msg["ts"]), []).append(msg)

        for root_ts, thread in threads.items():
            lines = [
                f"Slack thread in #{name}"
                + (" (private channel)" if channel["is_private"] else " (public channel)"),
                f"Date: {_fmt_date(root_ts)}",
                "",
            ]
            for msg in thread:
                author = users.get(msg["user"], {})
                lines.append(
                    f"{author.get('real_name', msg['user'])} "
                    f"({author.get('profile', {}).get('title', 'unknown role')}) "
                    f"on {_fmt_date(msg['ts'])} — {_permalink(cid, msg['ts'])}"
                )
                lines.append(msg["text"])
                lines.append("")

            documents.append(
                {
                    "channel": name,
                    "is_private": channel["is_private"],
                    "date": _fmt_date(root_ts),
                    "text": "\n".join(lines).strip(),
                }
            )
    return documents


async def ingest(reset: bool = True) -> None:
    documents = load_export()
    print(f"Loaded {len(documents)} threads from {EXPORT_DIR}")

    if reset:
        print("Pruning previous run...")
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)

    for doc in documents:
        # NodeSet tags travel with the document into the graph. `channel:<name>`
        # is what retrieve.py filters on to enforce a persona's clearance.
        node_set = [f"channel:{doc['channel']}"]
        node_set.append("visibility:private" if doc["is_private"] else "visibility:public")
        await cognee.add(doc["text"], dataset_name=DATASET, node_set=node_set)
        print(f"  + #{doc['channel']} {doc['date']}  tags={node_set}")

    print("\nRunning cognify with the decision-graph vocabulary (this calls the LLM)...")
    # NOTE: passing `graph_model=DecisionGraph` is the natural way to do this, but
    # cognee 1.4.2 fails writing a custom root model back into DocumentChunk.contains
    # (it iterates the model's fields as tuples and pydantic rejects them). So the
    # vocabulary in models.py is imposed through the extraction prompt instead — same
    # node types, same relationship names, onto the default graph shape.
    await cognee.cognify(
        datasets=[DATASET],
        custom_prompt=EXTRACTION_PROMPT,
    )
    print("Done. Graph is in the local graph store, vectors are in Qdrant.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Show the documents that would be ingested and exit (no LLM, no network).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Ingest without pruning the previous run first.",
    )
    args = parser.parse_args()

    if args.print_only:
        for doc in load_export():
            print("=" * 78)
            print(f"#{doc['channel']}  {doc['date']}  private={doc['is_private']}")
            print("-" * 78)
            print(doc["text"])
        return

    asyncio.run(ingest(reset=not args.keep))


if __name__ == "__main__":
    main()
