# app/
Core backend — API, ingestion, retrieval, monitoring.

| File | Does |
|------|------|
| `config.py` | All settings via Pydantic + `.env` |
| `api.py` | FastAPI endpoints (chat, ingest, upload, feedback) |
| `ingestion.py` | PDF → clean → chunk → ChromaDB + BM25 |
| `retriever.py` | BM25 + vector → RRF → Cohere rerank → relevance gate |
| `monitor_db.py` | SQLite — logs queries, sessions, feedback, latency |
| `rag_chain.py` | Legacy chain (superseded by `graph/`) |
| `graph/` | LangGraph pipeline → see `graph/README.md` |

## Key config defaults
```
CHUNK_SIZE=900  CHUNK_OVERLAP=200  RETRIEVER_K=40  RERANKER_TOP_N=4
EMBED_MODEL=BAAI/bge-base-en-v1.5  BM25_WEIGHT=0.35  VECTOR_WEIGHT=0.65
```

## ingestion.py flow
```
PDF → PyPDFLoader → clean_text() → chunk(900c/200ov)
    → ChromaDB (BGE 768-dim) + BM25Okapi
    → hash_registry.pkl  (skip already-indexed files)
```
> BM25 has **no stopword removal** — medical negations (`not`, `no`, `without`) change meaning.  
> BGE queries need prefix: `"Represent this sentence for searching relevant passages: <query>"`

## monitor_db.py tables
```
queries      — question, answer_type, confidence, retrieval_ms, llm_ms, tokens
chat_history — session_id, role, content
feedback     — session_id, score (1.0=👍 / 0.0=👎)
```
DB: `data/monitoring.db` (auto-created)