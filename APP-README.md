# CVlizer — AI Talent Matcher 🤖🎯

> **AI-powered HR & Hiring Matcher for Slack built with Cognee Knowledge Graphs, Qdrant Vector Search, and Groq LLMs.**

---

## 🌟 Overview

**CVlizer** transforms how engineering teams and HR departments match job openings with candidates. Instead of keyword searches or surface-level summaries, CVlizer leverages:
1. **Cognee Knowledge Graphs**: Extracts entities, technologies, roles, and semantic relationships from candidate CVs.
2. **Qdrant Vector Engine**: Measures dense cosine similarity over document chunks using local `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions).
3. **Groq LLMs**: High-throughput entity extraction (`llama-3.1-8b-instant`) + in-depth match reasoning (`llama-3.3-70b-versatile`).
4. **Slack Bolt Socket Mode**: Seamless interactive interface with immediate `<3s` acknowledgment and rich Block Kit cards.

---

## 🧠 How Cognee & Qdrant Are Used

CVlizer adheres strictly to Cognee-native paradigms:

```
Candidate CVs (.md) 
       │
       ▼ (cognee.add, dataset="cvs", node_set=["cv", "candidate:<slug>"])
   Cognee Pipeline
       │
       ├─► Groq llama-3.1-8b-instant (Entity & Relationship Extraction)
       ├─► FastEmbed BAAI/bge-small-en-v1.5 (Local 384-dim Embeddings)
       └─► Qdrant Vector Store (DocumentChunk_text & Payload storage)
```

### 1. Ingestion (`cognee.add` & `cognee.cognify`)
- CVs are loaded into dataset `"cvs"` with node set tags `["cv", "candidate:<slug>"]`.
- `cognee.cognify()` constructs the Ladybug knowledge graph and indexes chunks into Qdrant.

### 2. Two-Stage Matching
1. **Vector Stage (Measured Similarity)**: Queries Qdrant chunks via Cognee's vector engine to find the deterministic **Top 3** candidates sorted by cosine similarity.
2. **Graph Reasoning Stage (`SearchType.GRAPH_COMPLETION`)**: Traverses the candidate knowledge graph in Cognee to evaluate job fit, extract verbatim CV quotes, and generate hiring justifications.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.12** (managed with `uv`)
- **Docker & Docker Compose** (for Qdrant)
- **Groq API Key** (`gsk_...`)
- **Slack Tokens** (optional for Slack UI: `SLACK_BOT_TOKEN="xoxb-..."` and `SLACK_APP_TOKEN="xapp-..."`)

### 1. Installation

```bash
# Clone and enter directory
cd cognee

# Create virtualenv and install dependencies
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install --no-deps cognee-community-vector-adapter-qdrant==0.4.0
uv pip install qdrant-client transformers pytest pytest-asyncio
```

### 2. Environment Configuration

Create or update `.env`:
```bash
# LLM Configuration (Groq)
LLM_PROVIDER="custom"
LLM_MODEL="groq/llama-3.3-70b-versatile"
LLM_ENDPOINT="https://api.groq.com/openai/v1"
LLM_API_KEY="gsk_..."
LLM_EXTRACTION_MODEL="groq/llama-3.1-8b-instant"
LLM_QUERY_MODEL="groq/llama-3.3-70b-versatile"
LLM_RATE_LIMIT_ENABLED="true"
AUTO_RATE_LIMIT="true"

# Embedding Configuration (FastEmbed / Local 384 dims)
EMBEDDING_PROVIDER="fastembed"
EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS=384

# Vector DB Configuration (Qdrant)
VECTOR_DB_PROVIDER="qdrant"
VECTOR_DB_URL="http://localhost:6333"
VECTOR_DB_KEY=""
ENABLE_BACKEND_ACCESS_CONTROL="false"

# Slack Configuration (Socket Mode)
SLACK_BOT_TOKEN="xoxb-..."
SLACK_APP_TOKEN="xapp-..."
```

### 3. Start Database & Seed Candidate CVs

```bash
# 1. Start Qdrant container
make up

# 2. Ingest & cognify synthetic CV corpus
make seed
```

---

## 💬 Using CVlizer in Slack

Start the Slack bot:
```bash
make run
```

### Example Slack Prompts:

1. **Help & Usage Card:**
   ```text
   @CVlizer help
   ```

2. **Staff SRE / Kubernetes Match:**
   ```text
   @CVlizer We need a Staff Site Reliability Engineer with deep Kubernetes, Terraform, ArgoCD, and service mesh experience.
   ```
   *Expected #1:* **Devon Adams** (Staff SRE, multi-cluster Kubernetes, Istio, ArgoCD canary rollouts).

3. **Principal Frontend Architect Match:**
   ```text
   @CVlizer Looking for a Principal Frontend Architect with deep expertise in React, Next.js App Router, design systems, and Web Performance Core Web Vitals.
   ```
   *Expected #1:* **Marcus Vance** (Principal Frontend Architect, Next.js App Router, WCAG AAA design systems).

4. **Senior Backend Engineer Match:**
   ```text
   @CVlizer We are looking for a Senior Backend Engineer with deep experience in Python, FastAPI, Kafka, and high-throughput distributed systems.
   ```
   *Expected #1:* **Alice Chen** (Senior Backend Engineer, 65k req/s payment ingestion, FastAPI & Kafka).

5. **Senior Machine Learning & RAG Match:**
   ```text
   @CVlizer We need a Senior ML / AI Engineer with production experience in PyTorch, LLM fine-tuning, RAG architectures, and Qdrant vector databases.
   ```
   *Expected #1:* **Elena Rostova** (Senior AI Engineer, Qdrant hybrid RAG, Llama 3 fine-tuning).

6. **Low-Latency Systems Match:**
   ```text
   @CVlizer Looking for a Low-Latency Systems Engineer experienced in C++20, Rust, Linux kernel bypass, DPDK, and lock-free data structures.
   ```
   *Expected #1:* **Liam O'Connor** (Principal Systems Architect, sub-microsecond latency, DPDK, C++20/Rust).

---

## 💻 CLI Usage (No Slack Required)

Match job descriptions directly from your terminal:

```bash
PYTHONPATH=src .venv/bin/python -m cvlizer.matcher "Staff Backend Engineer with Python, FastAPI, Kafka, and distributed systems"
```

---

## 🧪 Testing

Run unit tests (Cognee and network calls are mocked, runs in <3 seconds):
```bash
make test
```

---

## 📁 Project Structure

| Path | Purpose |
|---|---|
| `src/cvlizer/config.py` | Registers Qdrant vector adapter with Cognee and loads environment |
| `src/cvlizer/seed.py` | Ingests and cognifies candidate CVs into Cognee datasets |
| `src/cvlizer/matcher.py` | Transport-agnostic matcher (Qdrant vector chunks + Cognee GRAPH_COMPLETION) |
| `src/cvlizer/blocks.py` | Slack Block Kit UI components (help card, loading state, match cards) |
| `src/cvlizer/slack_app.py` | Asynchronous Slack Bolt bot running on Socket Mode (<3s ack) |
| `data/cvs/` | Synthetic candidate CV dataset across tech specializations |
| `tests/test_matcher.py` | Isolated unit test suite |
| `docker-compose.yml` | Qdrant vector database container |
| `Makefile` | Dev shortcuts (`make up`, `make seed`, `make test`, `make run`, `make reset`) |

---

## 📜 Makefile Reference

- `make up`: Start local Qdrant container.
- `make seed`: Ingest & cognify all CVs in `data/cvs/`.
- `make run`: Launch the Slack Socket Mode bot.
- `make test`: Run unit tests with pytest.
- `make reset`: Reset Qdrant storage volume and restart database.
