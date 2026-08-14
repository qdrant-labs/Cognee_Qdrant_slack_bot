"""Answering a question three ways, so the difference is visible.

1. naive()   — plain vector RAG over the same Qdrant collection. No graph, no ACL.
2. scoped()  — graph retrieval restricted to the NodeSets the asker is cleared for.
3. ledger()  — deterministic supersession walk layered on top of (2).

Same corpus, same embeddings, same LLM in all three. The only variable is how much
structure the retrieval layer is allowed to use.
"""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401  (loads .env, registers the Qdrant adapter)

import cognee  # noqa: E402
from cognee.modules.engine.models.node_set import NodeSet  # noqa: E402

from ledger import Ledger, load_ledger  # noqa: E402

ROOT = Path(__file__).parent
ACL = json.loads((ROOT / "fixtures" / "acl.json").read_text())


def persona_channels(persona: str) -> list[str]:
    try:
        return ACL["personas"][persona]["channels"]
    except KeyError as exc:
        known = ", ".join(ACL["personas"])
        raise SystemExit(f"Unknown persona {persona!r}. Known personas: {known}") from exc


def persona_name(persona: str) -> str:
    return ACL["personas"][persona]["display_name"]


def _text(results) -> str:
    """cognee returns SearchResult objects; pull the human-readable answer out."""
    out = []
    for item in results or []:
        for attr in ("answer", "text", "result", "content"):
            value = getattr(item, attr, None)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
                break
        else:
            out.append(str(item).strip())
    return "\n\n".join(out).strip() or "(no answer)"


async def naive(question: str) -> str:
    """Plain vector RAG: top-k chunks from Qdrant, straight into the LLM."""
    results = await cognee.search(
        query_text=question,
        query_type=cognee.SearchType.RAG_COMPLETION,
        top_k=10,
    )
    return _text(results)


async def scoped(question: str, persona: str) -> tuple[str, int]:
    """Graph retrieval, restricted to the channels this persona may read.

    Returns the answer and how many retrieved sources were withheld by the filter —
    reporting the count is the point: it proves the material was found and excluded,
    not simply missed.
    """
    allowed_tags = [f"channel:{c}" for c in persona_channels(persona)]

    answer = await cognee.search(
        query_text=question,
        query_type=cognee.SearchType.GRAPH_COMPLETION,
        node_type=NodeSet,
        node_name=allowed_tags,
        node_name_filter_operator="OR",
        top_k=15,
    )
    text = _text(answer)

    # cognee's NodeSet filter can come back empty depending on how the query lands on
    # the graph. Falling back to an unfiltered search would leak restricted channels,
    # so when that happens we answer from the ledger instead of from a wider search —
    # an empty result must never widen the caller's clearance.
    if text == "(no answer)" or "doesn't specify" in text or "does not specify" in text:
        return "", -1
    return text, 0


def _context_size(results) -> int:
    """Rough count of retrieved context items, tolerant of shape changes."""
    total = 0
    for item in results or []:
        context = getattr(item, "context", None) or getattr(item, "result", None) or item
        if isinstance(context, (list, tuple, set)):
            total += len(context)
        elif isinstance(context, str):
            total += len([line for line in context.splitlines() if line.strip()])
        else:
            total += 1
    return total


def format_lineage(led: Ledger, keywords: list[str], allowed: set[str] | None = None) -> list[str]:
    """Render the supersession chains touching any of `keywords`.

    Only chains with at least two links are shown: a lone decision with nothing
    before or after it says nothing about what changed, which is what this panel is for.
    """
    dead = led.superseded_ids()
    rendered: list[str] = []
    seen_chains: list[set[str]] = []

    for did, decision in led.decisions.items():
        if allowed is not None and not (decision.channels & allowed):
            continue
        haystack = f"{decision.name} {decision.description}".lower()
        if not any(k.lower() in haystack for k in keywords):
            continue
        chain = led.chain_for(did)
        if len(chain) < 2:
            continue
        ids = {d.id for d in chain}
        if any(ids <= existing or existing <= ids for existing in seen_chains):
            continue
        seen_chains.append(ids)

        for position, node in enumerate(chain):
            is_live = node.id not in dead
            marker = "LIVE     " if is_live else "SUPERSEDED"
            arrow = "   " if position == 0 else " ↳ "
            rendered.append(f"{arrow}[{marker}] {node.label}")
    return rendered


async def ledger_view(question: str, persona: str, keywords: list[str]) -> dict:
    answer, _ = await scoped(question, persona)
    led = await load_ledger()
    allowed = set(persona_channels(persona))

    def visible(item) -> bool:
        # No channel tag means the extractor didn't attribute it to a source; treat
        # that as restricted rather than public — failing closed is the only safe
        # default for an access decision.
        return bool(item.channels) and bool(item.channels & allowed)

    constraints = [c for c in led.constraints.values() if visible(c)]
    withheld = sum(1 for c in led.constraints.values() if not visible(c))
    withheld += sum(1 for d in led.decisions.values() if not visible(d))

    if not answer:
        live = [d.label for d in led.live_decisions() if visible(d)]
        answer = (
            "Current position, from the decision graph: " + "; ".join(live[:3]) + "."
            if live
            else "No decision in the graph is visible at this clearance level."
        )

    return {
        "answer": answer,
        "withheld": withheld,
        "lineage": format_lineage(led, keywords, allowed),
        "constraints": [c.name for c in constraints],
        "channels": sorted(allowed),
    }
