# CVlizer 🤖🎯

> **AI Talent Matcher for Slack powered by Cognee Knowledge Graphs, Qdrant Vector Search & Groq LLMs.**

CVlizer acts as the AI HR matching department of a modern tech organization. Candidate CVs are ingested into a **Cognee Knowledge Graph** backed by **Qdrant**. When hiring managers or engineers `@CVlizer` in Slack with a job description, CVlizer:
1. **Indexes & Cognifies the job description** into Cognee.
2. **Performs vector chunk search** over the candidate CV collection to pick the deterministic **Top 3** candidates via measured cosine similarity.
3. **Traverses the Cognee knowledge graph** (`SearchType.GRAPH_COMPLETION`) to synthesize fit scores (0–100), key CV quotes, and reasons to hire.
4. **Responds in Slack (<3s ack)** via an asynchronous Bolt thread card with rich Block Kit formatting.

---

## 🏛️ Architecture

```
data/cvs/*.md ──► seed.py ──► cognee.add(dataset="cvs", node_set=["cv","candidate:<slug>"])
                                   └─► cognify() ─► FastEmbed (BAAI/bge-small-en-v1.5) ─► Qdrant

Slack @CVlizer ──► Immediate ack (<3s) ──► Async Background Task
                                               1. cognee.add + cognify(dataset="jobs", node_set=["job"])
                                               2. Qdrant vector chunk search (node_set=["cv"]) → Top 3
                                               3. GRAPH_COMPLETION → Fit score, direct quotes & reason
                                               4. Post Block Kit card in thread
```

---

## 🚀 Quickstart (5 Minutes)

### 1. Prerequisites
- Python 3.12 (`uv` recommended)
- Docker & Docker Compose
- Groq API Key (`gsk_...`)
- (Optional) Slack App Bot Token (`xoxb-...`) & App Token (`xapp-...` with Socket Mode enabled)

### 2. Environment Setup

Clone repository and install dependencies:
```bash
# Setup virtualenv and install dependencies
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install --no-deps cognee-community-vector-adapter-qdrant==0.4.0
uv pip install qdrant-client transformers pytest pytest-asyncio
```

Configure `.env`:
```bash
cp .env.example .env
# Add your Groq key and Slack tokens to .env:
# LLM_API_KEY="gsk_..."
# SLACK_BOT_TOKEN="xoxb-..."
# SLACK_APP_TOKEN="xapp-..."
```

### 3. Start Qdrant & Seed Candidate CVs

```bash
# Start local Qdrant container
make up

# Seed synthetic CVs into Cognee & Qdrant
make seed
```

Verify populated Qdrant collections:
```bash
curl http://localhost:6333/collections
```

---

## 🧪 Testing & CLI Matching

### Run Unit Tests (Mocked Cognee, No Network/LLM Required)
```bash
make test
```
**The judgement will happen same day after submission deadline at 9PM**


| Criterion | Points |
|---|---|
| Your project runs and is ready to use | 5 |
| Depth of the stack, not breadth | 0–5 |
| Complexity of your project (subagents, additional tooling, etc.) | 0–5 |
| Novel application | 0–5 |

### Run CLI Job Matcher Directly
You can match job descriptions directly from the terminal without Slack:
```bash
PYTHONPATH=src .venv/bin/python -m cvlizer.matcher "Looking for a Staff SRE with Kubernetes, Terraform, and Istio service mesh experience"
```

---

## 💬 Running the Slack Bot

Start the Slack Socket Mode bot:
```bash
make run
```

### Interacting in Slack:
- Type `@CVlizer help` to view the capabilities card.
- Mention `@CVlizer <job description>` to trigger instant matching and thread response.

---

## 📁 Repository Structure

```
├── data/cvs/               # Synthetic CV corpus (~20 candidates across tech roles)
├── plans/
│   ├── job-matcher.md      # Original MVP specification
│   └── plan.md             # Detailed implementation plan
├── src/cvlizer/
│   ├── config.py           # Cognee & Qdrant adapter initialization
│   ├── seed.py             # Swappable CV ingestion pipeline
│   ├── matcher.py          # Transport-agnostic Cognee/Qdrant matcher
│   ├── blocks.py           # Slack Block Kit card UI templates
│   └── slack_app.py        # Async Slack Bolt Socket Mode bot
├── tests/
│   └── test_matcher.py     # Fast isolated unit tests
├── docker-compose.yml      # Local Qdrant container config
├── pyproject.toml          # Package configuration & dependencies
├── Makefile                # Dev workflow shortcuts (up, seed, run, test)
└── README.md
```
