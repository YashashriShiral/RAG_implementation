# 🔬 Ask Anything About Endometriosis
### A Domain-Specific RAG System with Hybrid Retrieval, Reranking, Citation Enforcement & CI-Gated Evaluation

---

## 🏗️ Architecture Overview

```
PDFs  →  Parser  →  Chunker (600 tokens, 80 overlap)
                          │
              ┌───────────┴───────────────┐
              │                           │
         ChromaDB                    BM25 Index
     (dense vectors,             (sparse keyword,
    HuggingFace embed)           rank_bm25 Okapi)
              │                           │
              └───────────┬───────────────┘
                          │
                 Reciprocal Rank Fusion
               (merges ranked lists by position)
                          │
               Cohere CrossEncoder Reranker
             (top-20 candidates → top-5 passages)
                          │
              LLaMA 3.2 (via Ollama, local)
              + Citation-enforced prompt
                          │
                    FastAPI backend
                  ↙               ↘
          Streamlit UI         Langfuse
         (chat + citations)   (monitoring)
                          │
                   RAGAS Evaluation
                  (CI gate on PRs)
```

---

## ⚡ Quick Start

### 1. Prerequisites — Install on your machine

```bash
# Python 3.11+
python --version

# Ollama (local LLM runtime)
# Mac:
brew install ollama
# Linux:
curl -fsSL https://ollama.com/install.sh | sh

# Pull LLaMA 3.2
ollama pull llama3.2
```

### 2. Clone & Install

```bash
git clone <your-repo>
cd endo_rag

pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   COHERE_API_KEY     → https://cohere.com (free)
#   LANGFUSE_PUBLIC_KEY → https://cloud.langfuse.com (free)
#   LANGFUSE_SECRET_KEY
```

### 4. Add Your PDFs

```bash
# Copy your endometriosis research papers here:
cp /path/to/your/papers/*.pdf data/pdfs/
```

### 5. Run Ingestion (first time)

```bash
python -m app.ingestion
# Optional: force re-index everything
python -m app.ingestion --force
```

### 6. Start the System

**Option A: Run manually (two terminals)**
```bash
# Terminal 1 — FastAPI backend
python -m app.api

# Terminal 2 — Streamlit UI
streamlit run streamlit_app.py
```

**Option B: Docker Compose (recommended)**
```bash
docker-compose up --build
# After startup:
# API  → http://localhost:8000
# UI   → http://localhost:8501
```

---

## 📁 Project Structure

```
endo_rag/
├── app/
│   ├── config.py         # Centralized settings (Pydantic)
│   ├── ingestion.py      # PDF loading, chunking, ChromaDB + BM25 indexing
│   ├── retriever.py      # Hybrid BM25+vector, RRF fusion, Cohere reranking
│   ├── rag_chain.py      # LLaMA 3.2 chain with citation enforcement
│   ├── monitoring.py     # Langfuse tracing wrapper
│   └── api.py            # FastAPI REST endpoints
├── evaluation/
│   └── ragas_eval.py     # RAGAS evaluation + CI gate
├── tests/
│   └── test_retriever.py # Unit + integration tests
├── streamlit_app.py      # Chat UI
├── data/
│   ├── pdfs/             # ← PUT YOUR PDFs HERE
│   ├── chroma_db/        # Auto-created vector store
│   └── bm25_index.pkl    # Auto-created keyword index
├── .github/workflows/
│   └── ragas_eval.yml    # GitHub Actions CI pipeline
├── docker-compose.yml
├── Dockerfile
├── railway.toml          # Railway deployment config
├── requirements.txt
└── .env.example
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health + readiness |
| POST | `/chat` | Ask a question, get cited answer |
| POST | `/ingest` | Trigger PDF ingestion (background) |
| POST | `/upload-pdf` | Upload a new PDF |
| GET | `/sources` | List all indexed papers |
| POST | `/feedback` | Submit thumbs up/down |
| GET | `/stats` | System statistics |

**Chat request example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What causes endometriosis?"}'
```

---

## 📊 RAGAS Evaluation & CI Gate

**Run evaluation manually:**
```bash
python -m evaluation.ragas_eval
```

**CI gate thresholds** (in `evaluation/ragas_eval.py`):
| Metric | Threshold | Purpose |
|--------|-----------|---------|
| faithfulness | 0.75 | Anti-hallucination |
| answer_relevancy | 0.70 | Answers the question |
| context_precision | 0.65 | Retrieved docs are relevant |
| context_recall | 0.60 | Retrieves all relevant info |

Any metric below threshold → CI pipeline fails → PR blocked.

---

## 🚀 Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Set environment variables in Railway dashboard
# (same as .env keys)
```

---

## 🔑 Required API Keys

| Service | Free Tier | Get At |
|---------|-----------|--------|
| Cohere | 1000 reranks/month | cohere.com |
| Langfuse | Unlimited (self-host or cloud) | cloud.langfuse.com |
| Railway | $5/month credit | railway.app |

---

## 🛠️ Tuning Guide

**Retrieval quality low?**
- Increase `RETRIEVER_K` (more candidates for reranker)
- Decrease `CHUNK_SIZE` (more precise chunks)
- Adjust `BM25_WEIGHT` / `VECTOR_WEIGHT` ratio

**Answers hallucinating?**
- Lower `temperature` in `rag_chain.py` (already at 0.1)
- Increase `RERANKER_TOP_N` = 3 (fewer but more precise sources)
- Tighten the system prompt in `rag_chain.py`

**Evaluation scores low?**
- Add more eval questions to `evaluation/ragas_eval.py`
- Improve chunking strategy for your specific PDFs
- Fine-tune RRF weights
