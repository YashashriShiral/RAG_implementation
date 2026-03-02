# 🔬 Endo Research AI
### Domain-Specific RAG System — LangGraph · Hybrid Retrieval · Local LLM · SQLite Monitoring

---

## 🏗️ Architecture Overview

```
                    ┌──────────────────────────────────┐
                    │          PDF Ingestion            │
                    │  PyPDF → Text Cleaning            │
                    │  → Chunking (800 chars / 150 ov)  │
                    │  → BAAI/bge-base-en-v1.5 (768-dim)│
                    │       ↙                ↘          │
                    │  ChromaDB           BM25 Index    │
                    └──────────────────────────────────┘
                                   │
                    ┌──────────────────────────────────┐
                    │       LangGraph Pipeline          │
                    │                                  │
                    │  [retrieve_node]                 │
                    │  BM25 + Vector → RRF Fusion       │
                    │  → Cohere Rerank v3 (top-20→5)   │
                    │           ↓                      │
                    │  [grade_docs_node]               │
                    │  Best score < 0.15?              │
                    │   ↙ YES           ↘ NO           │
                    │[web_search]   [generate_rag]     │
                    │ Tavily API    LLaMA 3.2 +         │
                    │     ↓         paper citations    │
                    │[generate_web]       ↓            │
                    │ LLaMA 3.2 +        END           │
                    │ web sources                      │
                    │     ↓                            │
                    │    END                           │
                    └──────────────────────────────────┘
                                   │
                    ┌──────────────────────────────────┐
                    │         FastAPI Backend           │
                    │   /chat  /ingest  /feedback       │
                    └──────────┬───────────────────────┘
                               │
              ┌────────────────┴─────────────────────┐
              │                                      │
   ┌──────────┴──────────┐              ┌────────────┴──────────┐
   │    Streamlit UI      │              │  SQLite Monitoring    │
   │     port 8501        │              │  data/monitoring.db   │
   │  warm theme, cites,  │              │         ↓             │
   │  session history,    │              │ Monitoring Dashboard  │
   │  PDF upload/download │              │      port 8502        │
   └──────────────────────┘              └───────────────────────┘
```

---

## 🧩 LangGraph Pipeline — `app/graph/`

The entire QA logic runs as a **LangGraph state machine**. Each node does exactly one job. Adding a new agent touches only 3 files and ~5 lines of code — no existing logic changes.

### Nodes (`nodes.py`)

| Node | Responsibility |
|------|----------------|
| `retrieve_node` | BM25 + vector search → RRF fusion → Cohere rerank → top-5 docs |
| `grade_docs_node` | Compare best Cohere score to threshold (0.15) → set `docs_relevant` |
| `web_search_node` | Tavily API search (only runs if docs not relevant) |
| `generate_rag_node` | LLaMA 3.2 + paper excerpts → cited answer with References section |
| `generate_web_node` | LLaMA 3.2 + web results → answer with web disclaimer |

### State (`state.py`)
All nodes share one typed state object — `RAGState`:

```python
class RAGState(TypedDict):
    question:      str           # input
    session_id:    str           # input
    docs:          List[Document]  # set by retrieve_node
    retrieval_ms:  int
    docs_relevant: bool          # set by grade_docs_node
    web_results:   str           # set by web_search_node
    answer:        str           # final answer
    sources:       List[dict]    # cited sources with page numbers
    confidence:    float         # best Cohere rerank score
    answer_type:   str           # "rag" | "web" | "none"
    llm_ms:        int
    error:         Optional[str]
```

### Routing (`edges.py`)

```
grade_docs_node
    ├── docs_relevant = True  →  generate_rag_node  →  END
    └── docs_relevant = False →  web_search_node  →  generate_web_node  →  END
```

### Adding a new agent — only 3 steps

```python
# 1. app/graph/nodes.py
def pubmed_node(state: RAGState) -> dict:
    results = search_pubmed(state["question"])
    return {"web_results": results}

# 2. app/graph/edges.py
def route_after_grading(state: RAGState) -> str:
    if state["docs_relevant"]: return "generate_rag"
    if is_clinical(state["question"]): return "pubmed"  # new
    return "web_search"

# 3. app/graph/graph.py  (3 lines)
graph.add_node("pubmed", pubmed_node)
graph.add_edge("pubmed", "generate_web")
```

---

## 🔍 Retrieval

### Hybrid BM25 + Vector
- **Dense**: ChromaDB with `BAAI/bge-base-en-v1.5` (768-dim, cosine similarity)
- **Sparse**: BM25Okapi — **no stopword removal** (intentional — see below)
- **Fusion**: Reciprocal Rank Fusion (RRF, k=60) merges both ranked lists

### Why No Stopword Removal in BM25
Words like `not`, `no`, `without`, `can` carry critical clinical meaning:
- `"does NOT cause infertility"` vs `"does cause infertility"` — opposite diagnosis
- `"NO evidence of malignancy"` — clinically critical negation
- BM25's IDF naturally down-weights truly common words — manual stopword lists are redundant and harmful in medical text

### Cohere Reranker + Relevance Gate
- Top-20 RRF candidates → Cohere `rerank-english-v3.0` → top-5
- **Relevance gate**: best score < `0.15` → question is outside paper scope → route to Tavily web search
- Without this gate, off-topic questions get forced paper citations → hallucination

---

## 📦 Embeddings Upgrade

Upgraded from `all-MiniLM-L6-v2` to `BAAI/bge-base-en-v1.5`:

| | all-MiniLM-L6-v2 | BAAI/bge-base-en-v1.5 |
|--|--|--|
| Dimensions | 384 | **768** |
| MTEB Score | 56.3 | **63.6** |
| Medical text | Fair | **Strong** |
| Context window | 256 tokens | **512 tokens** |

> ⚠️ **Upgrading from old version?** ChromaDB collections store dimension in metadata — you must delete and rebuild:
> ```bash
> rm -rf data/chroma_db data/bm25_index.pkl data/hash_registry.pkl
> python -m app.ingestion --force
> ```

---

## 📊 Monitoring — Local SQLite

Langfuse cloud dependency has been **fully removed**. Replaced with a lightweight local SQLite database (`data/monitoring.db`) — zero external services, zero API keys, works offline.

**What's tracked:**

| Field | Description |
|-------|-------------|
| Question + Answer | Full text per query |
| Session ID | Groups queries into conversations |
| `retrieval_ms` | Time spent on BM25 + vector + rerank |
| `llm_ms` | Time spent on LLaMA generation |
| `confidence` | Best Cohere rerank score (0–1) |
| `total_tokens` | Estimated token usage |
| `sources_cited` | Number of papers cited |
| `answer_type` | `rag` / `web` / `none` |
| Feedback | 👍 = 1.0, 👎 = 0.0 |
| Errors | Traceback if any |

### Monitoring Dashboard (port 8502) — 3 tabs

| Tab | Contents |
|-----|----------|
| **Overview** | Total queries, avg confidence, latency, token charts, session list |
| **Queries** | Table with show-N selector (5/10/20/50), filter by confidence/errors/keyword, CSV export |
| **Evaluations** | RAGAS results as formatted colored tables (not raw JSON), per-question breakdown, multi-run comparison, download |

---

## ⚡ Quick Start

### 1. Prerequisites

```bash
# Python 3.11+
python --version

# Ollama
brew install ollama          # Mac
# or: curl -fsSL https://ollama.com/install.sh | sh   # Linux

ollama pull llama3.2
```

### 2. Install

```bash
git clone <your-repo>
cd endo_rag
pip install -r requirements.txt
pip install msgpack==1.1.0   # LangGraph checkpoint dependency
```

### 3. Configure `.env`

```bash
cp env.example.txt .env
```

```env
# Required
COHERE_API_KEY=your-key       # https://cohere.com (free tier)
TAVILY_API_KEY=your-key       # https://app.tavily.com (free, 1000/month)

# Optional overrides
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
CHUNK_SIZE=800
RETRIEVER_K=20
RERANKER_TOP_N=5
```

> Use plain `#` comments in `.env` — special characters like `──` will cause parse errors.

### 4. Add PDFs

```bash
mkdir -p data/pdfs
cp /path/to/your/papers/*.pdf data/pdfs/
```

### 5. Index

```bash
python -m app.ingestion

# Force full re-index (required after changing embedding model or chunk settings):
python -m app.ingestion --force
```

### 6. Run

```bash
# Terminal 1
python -m app.api

# Terminal 2
streamlit run streamlit_app.py

# Terminal 3 (optional)
streamlit run monitoring_dashboard.py --server.port 8502
```

| Service | URL |
|---------|-----|
| Chat UI | http://localhost:8501 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Monitoring | http://localhost:8502 |

---

## 📁 Project Structure

```
endo_rag/
├── app/
│   ├── config.py              # Pydantic settings — all env vars in one place
│   ├── ingestion.py           # PDF loading, text cleaning, chunking, ChromaDB + BM25
│   ├── retriever.py           # Hybrid BM25+vector, RRF, Cohere rerank, relevance gate
│   ├── monitor_db.py          # SQLite monitoring — queries, sessions, feedback, stats
│   ├── api.py                 # FastAPI endpoints
│   └── graph/
│       ├── state.py           # RAGState TypedDict
│       ├── nodes.py           # All node functions
│       ├── edges.py           # Routing / conditional edges
│       └── graph.py           # Graph assembly + RAGGraphRunner wrapper
├── evaluation/
│   ├── ragas_eval.py          # Local RAGAS evaluation + CI gate
│   └── results/               # eval_YYYYMMDD_HHMMSS.json files
├── tests/
│   └── test_retriever.py
├── streamlit_app.py           # Chat UI
├── monitoring_dashboard.py    # Monitoring dashboard
├── data/
│   ├── pdfs/                  # ← PUT YOUR PDFs HERE
│   ├── chroma_db/             # Auto-created vector store
│   ├── bm25_index.pkl         # Auto-created keyword index
│   ├── hash_registry.pkl      # Tracks already-indexed PDFs
│   └── monitoring.db          # Auto-created SQLite monitoring DB
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── env.example.txt
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Status, doc count, pipeline name |
| POST | `/chat` | Question → answer + sources + confidence |
| POST | `/ingest` | Trigger background re-indexing |
| POST | `/upload-pdf` | Upload new PDF |
| DELETE | `/delete-pdf/{filename}` | Remove PDF + re-index |
| GET | `/sources` | List all indexed papers |
| POST | `/feedback` | Submit 👍/👎 |
| GET | `/stats` | Query/token/latency stats |

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What causes endometriosis?", "session_id": "abc123"}'
```

**Response:**
```json
{
  "answer": "Endometriosis is thought to arise from...",
  "sources": [{"paper_title": "...", "page": 4, "rerank_score": 0.87, "excerpt": "..."}],
  "confidence": 0.87,
  "answer_type": "rag",
  "retrieval_ms": 340,
  "llm_ms": 2100
}
```

---

## 🧪 Evaluation

All metrics computed **locally** — no external API needed.

```bash
python -m evaluation.ragas_eval
# Output → evaluation/results/eval_YYYYMMDD_HHMMSS.json
# View in Monitoring Dashboard → Evaluations tab
```

| Metric | Threshold | Measures |
|--------|-----------|---------|
| Faithfulness | ≥ 0.75 | Answer grounded in retrieved sources |
| Answer Relevancy | ≥ 0.70 | Answer addresses the question |
| Context Precision | ≥ 0.65 | Retrieved chunks are on-topic |
| Context Recall | ≥ 0.60 | All relevant info retrieved |

Any metric below threshold → CI exits with code 1 → PR blocked.

---

## 🔑 API Keys

| Service | Purpose | Free Tier | Link |
|---------|---------|-----------|------|
| **Cohere** | Reranking — required | 1,000/month | cohere.com |
| **Tavily** | Web fallback — optional | 1,000/month | app.tavily.com |
| **Ollama** | LLaMA 3.2 — local, free | Unlimited | ollama.com |

> **Removed:** Langfuse. Monitoring is now 100% local SQLite.

---

## 🛠️ Tuning

**Retrieval quality low?**
```env
RETRIEVER_K=30        # more reranker candidates (default 20)
RERANKER_TOP_N=7      # more sources in context (default 5)
BM25_WEIGHT=0.5       # more keyword weight (default 0.4)
CHUNK_SIZE=600        # smaller = more precise (default 800)
```

**Web search triggering too often?** (relevance gate too strict)
```python
# app/graph/nodes.py + app/retriever.py
RELEVANCE_THRESHOLD = 0.10   # lower = more tolerant (default 0.15)
```

**Web search not triggering?** (papers being cited incorrectly)
```python
RELEVANCE_THRESHOLD = 0.25   # higher = stricter
```
