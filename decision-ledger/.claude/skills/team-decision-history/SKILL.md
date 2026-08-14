---
name: team-decision-history
description: >-
  The team's live architectural decisions and the constraints they must respect,
  compiled from Slack history. Load before choosing or changing a vector store,
  embedding store, or database, before reopening a settled infrastructure choice,
  or whenever asked why a component was picked. Contains decisions that were already
  rejected — check here before proposing one of them again.
---

# Team decision history

Compiled from the Slack workspace graph on 2026-08-14 by `compile_skill.py`. Do not hand-edit — rerun the compiler.

## Decisions currently in force

- **use qdrant as the embedding store**
  - Earlier decision made on 2026-03-03 to use Qdrant as the embedding store; referenced by Alice Chen as the decision being refined.
- **enable binary quantization on the qdrant collection**
  - Enable binary quantization on the Qdrant collection to cut memory roughly 32x and allow staying on a single node as the corpus grows. Decided on 2026-04-14 by Alice Chen.
- **migrate the embedding store from postgres/pgvector to qdrant**
  - Decision on 2026-03-03 by Bob Marek, confirmed by Alice Chen, to migrate the embedding store from Postgres/pgvector to Qdrant after load testing at 2M vectors showed p99 latency of 800ms, exceeding the 200ms latency budget.
- **run qdrant on a single 4gb node**
  - The Qdrant deployment will initially run on a single 4GB node.

## Already rejected — do not propose these again

- **use postgres/pgvector as the embedding store** — superseded
  - replaced by: migrate the embedding store from postgres/pgvector to qdrant
  - reason: Decision on 2026-03-03 by Bob Marek, confirmed by Alice Chen, to migrate the embedding store from Postgres/pgvector to Qdrant after load testing at 2M vectors showed p99 latency of 800ms, exceeding the 200ms latency budget.

## Constraints that outlive individual decisions

- **stay on a single node as the corpus grows**
  - Operational constraint to keep the embedding store on a single node while the corpus grows.
- **p99 latency budget of 200ms**
  - Latency SLO/constraint that the embedding store must meet: p99 latency must be at most 200ms.
- **keep vector infrastructure under $200 per month**
  - Finance hard constraint stated by Dan Rossi on 2026-02-03: vector infrastructure spend must stay below $200 per month.
- **revisit embedding store once corpus exceeds load-tested range (~500k vectors)**
  - Bob Marek flagged on 2026-02-03 that the choice has not been load tested past 500k vectors, so it may need revisiting as the corpus grows.
- **$200/month budget constraint**
  - Dan set a budget constraint of $200/month for the embedding store infrastructure.
- **northwind contract requires p99 latency under 200ms**
  - The Northwind contract SLA requires p99 latency under 200ms, and legal signs it on the Friday following 2026-03-02. This is described as the real forcing function on the vector store migration.

## How to use this

Before implementing anything that touches these areas, check the rejected list. If the task asks for something on it, say so and cite the decision that replaced it rather than silently complying. Every constraint above applies to new work unless the user explicitly lifts it.

For anything not covered here, query the live graph:

```bash
python demo.py -q "your question"
```
