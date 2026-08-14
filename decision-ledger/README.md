# Decision Ledger

**Slack memory that knows when it's out of date.**

Built for the Cognee × Qdrant HackNight.

---

## The problem

Ask a RAG bot "why aren't we using Postgres for the vector store?" and it will find
the message where someone said *"Decision: we're going with Postgres + pgvector"* —
high cosine similarity, confident tone, correctly retrieved.

That decision was reversed two months ago.

The failure isn't retrieval. The right chunk came back. The failure is that a pile
of vectors has no way to represent *"this was true, and then it wasn't"*. Every
Slack workspace is full of decisions that quietly killed earlier decisions, and a
flat embedding index will hand you the corpse with the same confidence as the
living thing.

## The approach

Cognee extracts a **typed** decision graph from Slack history — not generic
entities, but `Decision`, `Constraint`, `Alternative`, joined by `supersedes`,
`refines`, `constrained_by`. Qdrant carries the retrieval on every turn. Then:

**The lineage is walked, not inferred.** Asking an LLM to work out which decision
is current from a handful of retrieved chunks is the step that fails silently.
Instead `ledger.py` follows `supersedes` edges to the tail of the chain. The tail
is live; everything behind it is dead, with a date and an author for when it died.

**Clearance is enforced at retrieval, not by prompting.** Every document is tagged
with its channel as a cognee NodeSet. A persona's query is filtered to the NodeSets
they're cleared for, and the answer reports **how many sources were withheld** —
proving the material was found and excluded, not merely missed.

**The graph compiles into a skill.** Retrieval only helps an agent that thinks to
ask, and usually it doesn't — it just writes the code and reintroduces the option
the team rejected in March. `compile_skill.py` walks the graph for live decisions
and surviving constraints and emits a Claude Code skill, so the next agent loads
the decision history as a precondition instead of having to query for it.

## Setup

Needs Python 3.12, a Qdrant instance, and an LLM key. Embeddings run locally via
fastembed — no key, no network.

```bash
make setup
cp .env.example .env    # fill in LLM_API_KEY and VECTOR_DB_URL / VECTOR_DB_KEY
make check              # preflight: Qdrant, embeddings, structured output
make ingest             # Slack export -> typed graph (one LLM pass, ~1-2 min)
```

For Qdrant, either run it locally with `docker run -p 6333:6333 qdrant/qdrant`, or
point `VECTOR_DB_URL` at a free cluster from https://cloud.qdrant.io.

`.env.example` carries a working config for Anthropic and a commented one for any
OpenAI-compatible endpoint. The model must support structured output — cognify
extracts a JSON schema, so a chat-only model fails deep in the pipeline. `make check`
tests exactly that.

## The demo

```bash
make demo
```

One question, two retrieval paths, same corpus and same embeddings and same LLM —
the only variable is how much structure the retrieval layer may use.

```
┌─ 1. NAIVE VECTOR SEARCH ────────────┐  ┌─ 2. DECISION LEDGER ──────────────────┐
│ "We're using Postgres + pgvector    │  │ Current: Qdrant, since 2026-03-03.    │
│  for the embedding store."          │  │                                       │
│                                     │  │ Decision lineage                      │
│                                     │  │  [SUPERSEDED] Use Postgres + pgvector │
│                                     │  │   ↳ [LIVE] Migrate to Qdrant          │
│                                     │  │                                       │
│                                     │  │ Constraints still in force            │
│                                     │  │  • vector infra under $200/month      │
│                                     │  │  • p99 latency under 200ms            │
└─────────────────────────────────────┘  └───────────────────────────────────────┘
```

Then the same question at a narrower clearance:

```bash
make contractor
```

The contractor's answer drops the NDA'd commercial driver and reports
`1 source withheld`. The naive column, having no notion of clearance, does not.

Then compile what the graph knows into a reusable skill:

```bash
make skill        # -> .claude/skills/team-decision-history/SKILL.md
```

Ask a coding agent in this repo to add a vector store and it now answers with the
team's history attached: pgvector was rejected on 2026-03-03 for p99 latency, and
the $200/month budget still applies.

## Layout

| file | what it does |
|---|---|
| `models.py` | the typed graph — node types, relationship vocabulary, extraction prompt |
| `ingest.py` | Slack export → threads → `cognee.add` with NodeSet tags → `cognify` |
| `ledger.py` | deterministic supersession walk over the extracted graph |
| `retrieve.py` | three retrieval paths: naive RAG, clearance-scoped graph, ledger |
| `compile_skill.py` | graph → `.claude/skills/…/SKILL.md` |
| `demo.py` | the side-by-side comparison |
| `check_env.py` | preflight |
| `fixtures/` | a small Slack export with a real supersession chain, and the ACL map |

## Pointing it at your own data

`ingest.py:load_export` is the only Slack-shaped code — it turns an export into
`{channel, is_private, date, text}` documents. Swap it for a Jira, Notion, or
GitHub-issues reader and everything downstream is unchanged: the same typed graph,
the same lineage walk, the same skill compiler. Decisions supersede each other in
every one of those systems too.
