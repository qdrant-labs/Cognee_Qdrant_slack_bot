"""The typed graph cognee extracts Slack history into.

A generic knowledge graph gives you `Postgres --mentioned_in--> message`. That is
not enough to answer "is this still true?". You need to know that a *decision* was
made, that a later decision *supersedes* it, and which *constraints* outlived both.

This model is handed to `cognee.cognify(graph_model=DecisionGraph)`, so the
extractor is forced to fill these node types and relationship names instead of
inventing its own vocabulary each run. Everything downstream — the supersession
walk in ledger.py, the skill compiler — reads these names.
"""

from typing import Literal

from pydantic import BaseModel, Field

NodeType = Literal[
    "Decision",  # a choice the team committed to
    "Constraint",  # a rule that outlives individual decisions (budget, latency SLO)
    "Alternative",  # an option that was considered and rejected
    "Person",  # who decided / who objected
    "Artifact",  # PR, doc, dashboard the decision points at
    "Metric",  # the measurement that triggered a decision (p99 800ms)
]

RelationshipType = Literal[
    "supersedes",  # THE relationship: decision -> the older decision it replaces
    "refines",  # narrows an existing decision without replacing it
    "constrained_by",  # decision -> constraint it must respect
    "decided_by",  # decision -> person
    "rejected_alternative",  # decision -> option that lost
    "evidenced_by",  # decision -> artifact / metric that justifies it
    "motivated_by",  # decision -> the driver behind it
]


class DecisionNode(BaseModel):
    """A node in the decision graph."""

    id: str
    name: str = ""
    type: NodeType
    description: str
    decided_on: str = Field(
        default="",
        description="ISO date (YYYY-MM-DD) the decision was made, if the source says so.",
    )
    decided_by: str = Field(
        default="", description="Full name of the person who made the call, if stated."
    )
    status: Literal["active", "superseded", "proposed", "unknown"] = Field(
        default="unknown",
        description=(
            "Only set this when the source text states it outright. Leave it 'unknown' "
            "otherwise — status is recomputed from the supersedes edges, not trusted from here."
        ),
    )

    def __init__(self, **data):
        if not data.get("name"):
            data["name"] = data.get("id", "")
        super().__init__(**data)


class DecisionEdge(BaseModel):
    """A typed edge in the decision graph."""

    source_node_id: str
    target_node_id: str
    relationship_name: RelationshipType
    description: str | None = Field(
        None, description="One concrete sentence stating the fact this edge encodes."
    )


class DecisionGraph(BaseModel):
    """Root model passed to cognee.cognify(graph_model=...)."""

    summary: str
    description: str
    nodes: list[DecisionNode] = Field(default_factory=list)
    edges: list[DecisionEdge] = Field(default_factory=list)


EXTRACTION_PROMPT = """\
You are reading messages from a company's Slack workspace and extracting the \
team's decision history.

Extract a graph of what the team DECIDED, not a graph of what was mentioned.

Rules:
- A Decision node is a choice the team committed to. Its name should read as the \
choice itself ("Use Qdrant as the embedding store"), not as a topic.
- When a message revisits an earlier decision and changes it, emit a `supersedes` \
edge from the NEW decision to the OLD one. Phrases like "supersedes", "following up \
on the X decision", "we're migrating from X to Y" signal this. This edge is the most \
important thing you extract — do not miss it.
- When a message narrows an existing decision without replacing it ("this refines \
the March 3rd decision, it does not replace it"), use `refines`, not `supersedes`.
- A Constraint is a rule that outlives decisions: budgets, latency SLOs, compliance \
limits. Attach it with `constrained_by` to every decision that must respect it.
- A question asking whether something is the case is NOT a decision. Do not create \
a Decision node from someone asking "we're on X right?".
- Record `decided_on` from the message date and `decided_by` from the author \
whenever the message states a decision.
- Leave `status` as "unknown". It is recomputed from the supersedes edges.
"""
