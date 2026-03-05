# 🔬 Endo Research AI

EndoResearchAI: A privacy-first, fully local RAG system delivering endometriosis insights grounded strictly in medical research, with secure fallback web search when evidence is unavailable. 

For an overview of the inspiration and motivation behind this application, please refer to this article: https://medium.com/@yashashriShiral/ai-powered-endometriosis-management-app-part-1-ff72ddf20fb6

Answers endometriosis questions from research PDFs. Falls back to Tavily web search when the question is out of scope.

**Stack:** LLaMA 3.2 (Ollama) · LangGraph · BM25 + ChromaDB · Cohere rerank · FastAPI · Streamlit · SQLite

## Setup
```bash
pip install -r requirements.txt && pip install msgpack==1.1.0
ollama pull llama3.2
cp env.example.txt .env          # add COHERE_API_KEY, TAVILY_API_KEY
cp papers/*.pdf data/pdfs/
python -m app.ingestion
python -m app.api                # terminal 1 → localhost:8000
streamlit run streamlit_app.py   # terminal 2 → localhost:8501
streamlit run monitoring_dashboard.py --server.port 8502  # optional
```

## Pipeline
```
Question → BM25+Vector(top-40) → RRF → Cohere rerank(top-4)
         → score < 0.15? → Tavily web search → LLaMA → web answer
         → score ≥ 0.15  → LLaMA + paper excerpts → cited answer
```

## Structure
```
app/              backend (api, ingestion, retrieval, monitoring)
app/graph/        LangGraph nodes, edges, state
evaluation/       LLM-as-judge eval + CI gate
tests/            unit tests
streamlit_app.py  chat UI (port 8501)
monitoring_dashboard.py  metrics UI (port 8502)
data/pdfs/        ← put PDFs here
```

## API
| Endpoint | Does |
|----------|------|
| `POST /chat` | ask a question |
| `POST /upload-pdf` | add a paper |
| `DELETE /delete-pdf/{name}` | remove a paper |
| `POST /ingest` | re-index |
| `GET /health` | status |
| `POST /feedback` | 👍/👎 |

## Re-index after changing chunk/embed settings
```bash
rm -rf data/chroma_db data/bm25_index.pkl data/hash_registry.pkl
python -m app.ingestion --force
```
