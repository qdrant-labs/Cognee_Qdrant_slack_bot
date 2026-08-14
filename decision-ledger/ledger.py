"""Deterministic reasoning over the decision graph.

The LLM extracts the graph. It does not get to decide what is currently true —
that is a graph walk, and we do it ourselves:

    D1 (pgvector) <--supersedes-- D2 (Qdrant) <--refines-- D3 (binary quantization)

Follow `supersedes` to the tail of the chain and the tail is the live decision;
everything behind it is dead, with a date and an author for when it died. Asking a
language model to infer that from retrieved chunks is exactly the step that fails
silently, and it is the whole reason a graph beats a pile of vectors here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cognee.infrastructure.databases.graph import get_graph_engine

SUPERSEDES = "supersedes"
REFINES = "refines"
NODESET_RELATIONS = {"belongs_to_set", "belongs_to_nodeset"}


@dataclass
class Decision:
    id: str
    name: str
    description: str = ""
    decided_on: str = ""
    decided_by: str = ""
    channels: set[str] = field(default_factory=set)

    @property
    def label(self) -> str:
        who = f" by {self.decided_by}" if self.decided_by else ""
        when = f" on {self.decided_on}" if self.decided_on else ""
        return f"{self.name}{when}{who}"


@dataclass
class Ledger:
    decisions: dict[str, Decision]
    supersedes: list[tuple[str, str]]  # (newer, older)
    refines: list[tuple[str, str]]  # (narrower, broader)
    constraints: dict[str, Decision]
    node_channels: dict[str, set[str]]

    def superseded_ids(self) -> set[str]:
        return {older for _, older in self.supersedes}

    def chain_for(self, decision_id: str) -> list[Decision]:
        """Full lineage containing this decision, oldest first."""
        newer_of = {older: newer for newer, older in self.supersedes}
        older_of = {newer: older for newer, older in self.supersedes}

        oldest = decision_id
        seen = {oldest}
        while older_of.get(oldest) and older_of[oldest] not in seen:
            oldest = older_of[oldest]
            seen.add(oldest)

        chain, cursor, walked = [], oldest, {oldest}
        while cursor:
            if cursor in self.decisions:
                chain.append(self.decisions[cursor])
            nxt = newer_of.get(cursor)
            if not nxt or nxt in walked:
                break
            cursor, _ = nxt, walked.add(nxt)
        return chain

    def live_decisions(self) -> list[Decision]:
        dead = self.superseded_ids()
        return [d for did, d in self.decisions.items() if did not in dead]


def _norm(value) -> str:
    return str(value or "").strip()


_FILLER = {"use", "as", "for", "the", "a", "an", "of", "to", "with", "our", "on"}


def _dedup_key(name: str) -> str:
    """Two extractions of one decision rarely agree on wording — 'use postgres/pgvector
    as the embedding store' and 'use postgres + pgvector for the embedding store' are
    the same choice. Compare the content words only."""
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in name.lower())
    return " ".join(sorted(w for w in cleaned.split() if w not in _FILLER))


def _as_list(value) -> list[str]:
    """belongs_to_set comes back as a real list on some backends and as its repr
    on others ("['channel:eng-backend', ...]"). Accept both."""
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value]
    text = _norm(value).strip("[]")
    return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]


async def load_ledger() -> Ledger:
    """Read the graph cognify produced and index the decision structure in it."""
    graph = await get_graph_engine()
    nodes, edges = await graph.get_graph_data()

    props_by_id: dict[str, dict] = {}
    for node in nodes:
        node_id, props = (node[0], node[1]) if isinstance(node, (tuple, list)) else (node, {})
        props_by_id[str(node_id)] = props or {}

    # cognify labels every extracted node `type: "Entity"`; the semantic type lives
    # on a separate EntityType node reached by an `is_a` edge. Resolve that first,
    # then classify.
    entity_type_names = {
        node_id: _norm(props.get("name")).lower()
        for node_id, props in props_by_id.items()
        if _norm(props.get("type")) == "EntityType"
    }

    supersedes: list[tuple[str, str]] = []
    refines: list[tuple[str, str]] = []
    semantic_type: dict[str, str] = {}

    for edge in edges:
        if len(edge) < 3:
            continue
        source, target, relation = str(edge[0]), str(edge[1]), _norm(edge[2])
        if relation == SUPERSEDES:
            supersedes.append((source, target))
        elif relation == REFINES:
            refines.append((source, target))
        elif target in entity_type_names:
            semantic_type[source] = entity_type_names[target]

    # Anything on either end of a supersedes/refines edge *is* a decision, whatever
    # the extractor called it — that relationship is only meaningful between decisions.
    in_lineage = {node for pair in supersedes + refines for node in pair}

    decisions: dict[str, Decision] = {}
    constraints: dict[str, Decision] = {}
    node_channels: dict[str, set[str]] = {}

    for node_id, props in props_by_id.items():
        if _norm(props.get("type")) != "Entity":
            continue
        name = _norm(props.get("name")) or node_id
        kind = semantic_type.get(node_id, "")

        # ingest.py's NodeSet tags come back as a property, not an edge.
        for tag in _as_list(props.get("belongs_to_set")):
            if tag.startswith("channel:"):
                node_channels.setdefault(node_id, set()).add(tag.split(":", 1)[1])

        if node_id in in_lineage or "decision" in kind:
            decisions[node_id] = Decision(
                id=node_id,
                name=name,
                description=_norm(props.get("description")),
                decided_on=_norm(props.get("decided_on")),
                decided_by=_norm(props.get("decided_by")),
                channels=node_channels.get(node_id, set()),
            )
        elif "constraint" in kind or "budget" in kind or "requirement" in kind:
            constraints[node_id] = Decision(
                id=node_id,
                name=name,
                description=_norm(props.get("description")),
                channels=node_channels.get(node_id, set()),
            )

    # The same decision gets extracted once per chunk that mentions it, so the graph
    # holds several nodes for one real choice. Collapse them by name — otherwise a
    # decision can show up as superseded and live at the same time, which is exactly
    # the confusion this whole thing exists to remove.
    canonical: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for node_id, decision in decisions.items():
        key = _dedup_key(decision.name)
        if key in by_name:
            keeper = decisions[by_name[key]]
            keeper.channels |= decision.channels
            if len(decision.description) > len(keeper.description):
                keeper.description = decision.description
            canonical[node_id] = by_name[key]
        else:
            by_name[key] = node_id
            canonical[node_id] = node_id

    decisions = {nid: d for nid, d in decisions.items() if canonical[nid] == nid}

    def _remap(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        seen, out = set(), []
        for newer, older in pairs:
            pair = (canonical.get(newer, newer), canonical.get(older, older))
            if pair[0] != pair[1] and pair not in seen:
                seen.add(pair)
                out.append(pair)
        return out

    return Ledger(
        decisions=decisions,
        supersedes=_remap(supersedes),
        refines=_remap(refines),
        constraints=constraints,
        node_channels=node_channels,
    )
