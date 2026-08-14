# CVlizer — implementation plan

## Context

Hackathon project for the Cognee & Qdrant HackNight. We play the HR department of a large
tech company: candidate CVs are ingested into a cognee knowledge graph backed by Qdrant, and a
Slack channel shared by HR, hiring managers and engineers becomes the query surface. A hiring
manager `@`-mentions the bot with a job description; the bot indexes the job, finds the best
candidates, and posts the top 3 with quotes, scores and a reason to hire.

The repo is currently empty apart from `README.md` and `plans/job-matcher.md`, so everything
below is greenfield.

The rubric rewards **depth over breadth**, so the guiding constraint is that cognee genuinely
does the work — it owns the write path into Qdrant and produces the match reasoning — rather
than being a wrapper around code we could have written without it. The other hard constraint
is "runs on Monday": a judge with Docker and a Groq key must be able to start it.

Scope is the MVP in `plans/job-matcher.md`. The Future plans section (email/web-form ingest,
interview minutes, talent pool) is explicitly **not** implemented, only accommodated
architecturally: CV ingestion is a swappable loader, and jobs are persisted rather than
discarded so a future talent-pool matcher has something to match against.

## Decisions taken (from the grilling session)

| Area | Decision |
|---|---|
| Write path | `cognee.add()` + `cognify()` only. Qdrant client is **read-only**, for inspection/demo |
| Matching | Single `SearchType.GRAPH_COMPLETION` over the CV graph for quotes + reason to hire |
| Score | Hybrid: Qdrant cosine (measured) **plus** LLM fit score (reasoned), both displayed |
| Ranking | **Cosine ranks and picks the top 3**; the graph explains why. Reproducible across runs |
| Slack transport | Socket Mode (`slack_bolt` AsyncApp) — no ngrok, no public URL, no signature code |
| Trigger | `app_mention` only. Startup help card + `@CVlizer help` |
| Embeddings | `fastembed` (Qdrant's own library), `BAAI/bge-small-en-v1.5`, 384 dims, fully local |
| LLM | Groq. `llama-3.1-8b-instant` for extraction, `llama-3.3-70b-versatile` for the answer |
| Candidate names | cognee extracts `Person` nodes; fixture CVs are authored with a clean `# Name` H1 |
| Isolation | Datasets `cvs` / `jobs`, plus node_set tags `cv` / `job` / `candidate:<slug>` |
| Packaging | Docker Compose for Qdrant, `uv`, Python **3.12** pinned, `make seed` / `make run` |

### Why the `candidate:<slug>` tag exists

Cosine-ranked results require attributing a scored chunk back to a person. Qdrant chunk
payloads carry only `database_name` and `belongs_to_set`, so the slug is added at load time
purely as a **retrieval handle**. cognee still extracts `Person` nodes and supplies the
display name — the tag does not replace identity extraction.

## Architecture

```
data/cvs/*.md ──► seed.py ──► cognee.add(dataset="cvs", node_set=["cv","candidate:<slug>"])
                                   └─► cognify() ─► fastembed ─► Qdrant collections

Slack @mention ──► ack (<3s) ──► asyncio task
                                   1. add+cognify job   → dataset "jobs", node_set ["job"]
                                   2. SearchType.CHUNKS → scored chunks, group by candidate
                                                          tag, max(score) → TOP 3
                                   3. GRAPH_COMPLETION  → quotes, reason, fit score
                                   4. Block Kit card in the thread
```

Step 1 runs before the search so the job really is "parsed and indexed" as the brief requires,
and so a future talent-pool feature has stored jobs. It does not feed the candidate search.

### The 3-second problem

Slack times out a request after 3s; `cognify()` on a job description takes 10–60s. Every
handler acks immediately, posts a "🔎 Indexing job…" thread reply, then does the work in an
`asyncio.create_task` and edits/posts the result via `chat.postMessage`. This is non-negotiable
and is the most common way this class of demo fails.

## Files

| File | Purpose |
|---|---|
| `.python-version` | `3.12` — pin via `uv python pin 3.12` |
| `pyproject.toml` | `cognee`, `slack-bolt`, `fastembed`, `pydantic`; adapter installed `--no-deps` |
| `docker-compose.yml` | Qdrant on 6333, named volume for persistence |
| `.env.example` | Every var below, with the Groq key as the only required secret |
| `Makefile` | `up`, `seed`, `run`, `test` |
| `src/cvlizer/config.py` | cognee + Qdrant adapter registration, called once at import |
| `src/cvlizer/seed.py` | CV loader — the swap point for future email/web-form ingest |
| `src/cvlizer/matcher.py` | `async def match_job(jd: str) -> MatchResult` — transport-agnostic |
| `src/cvlizer/blocks.py` | Block Kit rendering + help card |
| `src/cvlizer/slack_app.py` | Socket Mode entrypoint, `app_mention` handler |
| `data/cvs/*.md` | ~20 synthetic CVs (no real PII) |
| `tests/test_matcher.py` | cognee mocked — no LLM calls in tests |
| `README.md` | Setup a judge can follow in under 5 minutes |

`matcher.py` must not import anything Slack-specific — it keeps the demo testable and leaves an
HTTP entrypoint as a small second file if ever needed.

## Configuration

```bash
LLM_PROVIDER="custom"                                   # VERIFY — see spike
LLM_MODEL="groq/llama-3.3-70b-versatile"
LLM_ENDPOINT="https://api.groq.com/openai/v1"
LLM_API_KEY="gsk_..."
LLM_EXTRACTION_MODEL="groq/llama-3.1-8b-instant"        # bulk graph extraction
LLM_QUERY_MODEL="groq/llama-3.3-70b-versatile"          # the answer judges read
LLM_RATE_LIMIT_ENABLED="true"
AUTO_RATE_LIMIT="true"

EMBEDDING_PROVIDER="fastembed"
EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS=384

VECTOR_DB_PROVIDER="qdrant"
VECTOR_DB_URL="http://localhost:6333"
VECTOR_DB_KEY=""

SLACK_BOT_TOKEN="xoxb-..."
SLACK_APP_TOKEN="xapp-..."      # Socket Mode requires an app-level token
```

Qdrant adapter install follows the demo repo's pin:
`uv pip install --no-deps cognee-community-vector-adapter-qdrant==0.4.0`, then import its
`register` module in `config.py` before any cognee call.

## Spike first — 45 minutes, before anything else

Three unknowns can each sink the build. Resolve them in a throwaway script before writing
features:

1. **Groq through cognee.** `LLM_PROVIDER` may need to be `custom` or `openai_compatible`;
   litellm routes on the `groq/` model prefix. Confirm one `cognify()` completes end to end.
2. **Structured extraction on Groq.** cognee drives entity extraction through `instructor`.
   If it errors, set `STRUCTURED_OUTPUT_FRAMEWORK="litellm_native"` (or `baml`), and/or adjust
   `LLM_INSTRUCTOR_MODE`. Groq does support strict JSON-Schema structured outputs, so a working
   combination exists.
3. **Does `SearchType.CHUNKS` return cosine scores and `belongs_to_set`?** The whole ranking
   design depends on it. If scores are absent, fall back to ranking by the LLM fit score and
   show cosine only where available — decide this in the spike, not at hour 10.

## Build order

1. Spike (above), then `docker-compose.yml` + `config.py` + one CV seeded and searched by hand.
2. `data/cvs/` — ~20 synthetic CVs spanning backend/frontend/ML/SRE/data, deliberately including
   two near-miss profiles so the ranking has something interesting to do on stage.
3. `seed.py`, then `make seed` end to end.
4. `matcher.py` — CHUNKS → group by `candidate:` tag → top 3 → GRAPH_COMPLETION → parse.
5. `slack_app.py` + `blocks.py`, ack-then-work, help card on startup.
6. README, `.env.example`, rehearse the demo twice.

### Output parsing

The `GRAPH_COMPLETION` query string carries an explicit output contract (a JSON shape with
`name`, `quotes[]`, `fit_score`, `reason`) and a stated rubric for the fit score. The parser is
deliberately tolerant: strip code fences, attempt `json.loads`, and on failure **post cognee's
raw prose into the thread** rather than raising. A degraded card beats a dead bot on stage.

## Known risks

- **cognee issue #1023** — `search(datasets=...)` has been reported to leak results across
  datasets. This is why job/CV separation uses node_set tags as well as datasets. Verify during
  the spike that a `cvs`-scoped search never returns the job document.
- **Groq free-tier 429s** — mitigated by the 8b extraction model and cognee's rate limiter.
  Seed the full CV corpus *before* the demo so only the job is cognified live.
- **Hallucinated quotes** — accepted consequence of the single-call design. Cheap partial
  mitigation, if time allows: assert each returned quote is a substring of some seeded CV and
  mark any that isn't with a ⚠️ rather than dropping it.
- **Embedding dimension changes** require deleting Qdrant collections; the adapter sizes them
  from the embedding engine at creation time. `make reset` should drop the volume.

## Verification

- `make up && make seed` completes; `curl localhost:6333/collections` shows populated cognee
  collections — this is the read-only Qdrant proof for judges.
- `uv run pytest` passes with cognee mocked (no network, no LLM).
- `python -m cvlizer.matcher "<job description>"` prints a ranked top 3 from the CLI, proving
  the core works independently of Slack.
- In Slack: `@CVlizer` a backend JD → help card already visible from startup → thread reply
  within 3s → top-3 card with names, quotes, cosine + fit scores, and reasons.
- Run the same JD twice and confirm the same three candidates in the same order (cosine ranking
  is deterministic; this is the reproducibility claim being made to judges).
- Post a JD for a skill nobody has and confirm the bot degrades gracefully instead of inventing
  candidates.

## References

- [cognee-demo-slack](https://github.com/qdrant-labs/cognee-demo-slack) — adapter pin, env layout
- [cognee Slack integration docs](https://docs.cognee.ai/integrations/slack-integration)
- [cognee NodeSets](https://docs.cognee.ai/core-concepts/further-concepts/node-sets)
- [cognee embedding providers](https://docs.cognee.ai/setup-configuration/embedding-providers)
- [cognee `.env.template`](https://github.com/topoteretes/cognee/blob/main/.env.template)
- [cognee issue #1023 — dataset scoping leak](https://github.com/topoteretes/cognee/issues/1023)
- [Qdrant multitenancy / `m=0`, `payload_m`](https://qdrant.tech/documentation/guides/multiple-partitions/)
- [Groq supported models](https://console.groq.com/docs/models) — no embedding models
