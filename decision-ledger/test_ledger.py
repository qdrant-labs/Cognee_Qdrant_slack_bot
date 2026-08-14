"""Validate the supersession walk against a hand-built graph.

Runs with no LLM and no ingest: it writes nodes and edges straight into the graph
engine, so `load_ledger()` is exercised against the real backend's data shapes.
That is the part most likely to break silently — everything downstream (the demo
panel, the skill compiler) trusts what load_ledger returns.

    python test_ledger.py
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import bootstrap  # noqa: F401  (loads .env, registers the Qdrant adapter)

from cognee.infrastructure.databases.graph import get_graph_engine  # noqa: E402

from ledger import load_ledger  # noqa: E402

D1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "decision-pgvector"))
D2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "decision-qdrant"))
D3 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "decision-quantization"))
C1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "constraint-budget"))
NS = str(uuid.uuid5(uuid.NAMESPACE_DNS, "nodeset-eng-backend"))

NODES = [
    (D1, {"type": "Decision", "name": "Use Postgres + pgvector as the embedding store",
          "description": "200k vectors, no new infra", "decided_on": "2026-02-03",
          "decided_by": "Alice Chen", "status": "unknown"}),
    (D2, {"type": "Decision", "name": "Migrate the embedding store to Qdrant",
          "description": "p99 hit 800ms at 2M vectors", "decided_on": "2026-03-03",
          "decided_by": "Bob Marek", "status": "unknown"}),
    (D3, {"type": "Decision", "name": "Enable binary quantization on the Qdrant collection",
          "description": "32x memory reduction", "decided_on": "2026-04-14",
          "decided_by": "Alice Chen", "status": "unknown"}),
    (C1, {"type": "Constraint", "name": "Vector infrastructure under $200/month",
          "description": "set by finance"}),
    (NS, {"type": "NodeSet", "name": "channel:eng-backend"}),
]

EDGES = [
    (D2, D1, "supersedes", {}),
    (D3, D2, "refines", {}),
    (D2, C1, "constrained_by", {}),
    (D1, NS, "belongs_to_set", {}),
    (D2, NS, "belongs_to_set", {}),
]


def check(label: str, passed: bool, detail: str = "") -> bool:
    mark = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return passed


async def main() -> int:
    graph = await get_graph_engine()
    # The adapter writes via model_dump()/vars(), so pass objects, not tuples.
    await graph.add_nodes(
        [SimpleNamespace(id=node_id, **props) for node_id, props in NODES]
    )
    await graph.add_edges(EDGES)

    led = await load_ledger()
    results = []

    results.append(
        check("decisions extracted", len(led.decisions) >= 3, f"{len(led.decisions)} found")
    )
    results.append(
        check("constraint extracted", len(led.constraints) >= 1, f"{len(led.constraints)} found")
    )
    results.append(
        check("supersedes edge read", (D2, D1) in led.supersedes, str(led.supersedes))
    )

    dead = led.superseded_ids()
    results.append(check("D1 is marked superseded", D1 in dead))
    results.append(check("D2 is not marked superseded", D2 not in dead))

    chain = led.chain_for(D2)
    chain_names = [d.name for d in chain]
    results.append(
        check("lineage walks oldest-first", len(chain) == 2 and chain[0].id == D1, str(chain_names))
    )

    live = {d.id for d in led.live_decisions()}
    results.append(check("live set excludes D1", D1 not in live and D2 in live))
    results.append(
        check(
            "nodeset channel tag attached",
            "eng-backend" in led.decisions[D2].channels,
            str(led.decisions[D2].channels),
        )
    )

    print()
    if all(results):
        print("ledger.py is sound against the real graph backend.\n")
        return 0
    print("ledger.py does NOT read the backend's shapes correctly — fix before ingest.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
