"""
app/api.py
─────────────────────────────────────────────────────────────────────────────
FastAPI Backend — uses LangGraph RAG pipeline
"""

import os
import uuid
import asyncio
import logging
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# ── Suppress ChromaDB telemetry + other noisy warnings ───────────────────────
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMA_TELEMETRY"]     = "false"
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from app.config import get_settings
from app.ingestion import run_ingestion, load_vectorstore, load_bm25_index, get_embeddings
from app.retriever import HybridRetriever
from app.graph.graph import RAGGraphRunner
from app import monitor_db
from app.daily_log_db import init_daily_log_table
from app.whatsapp_routes import router as whatsapp_router, start_weekly_scheduler

settings = get_settings()

# ── Global state ──────────────────────────────────────────────────────────────
_runner: Optional[RAGGraphRunner] = None
_is_ingesting: bool = False


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    logger.info("Starting Endometriosis RAG API (LangGraph) …")

    try:
        embeddings  = get_embeddings()
        vectorstore = load_vectorstore(embeddings)
        doc_count   = vectorstore._collection.count()

        if doc_count == 0:
            logger.warning("ChromaDB empty — RAG disabled. Upload PDFs via /upload-pdf or POST /ingest.")
            _runner = None
        else:
            logger.info(f"ChromaDB loaded: {doc_count} chunks")
            bm25, corpus = load_bm25_index()
            retriever    = HybridRetriever(vectorstore, bm25, corpus)
            _runner      = RAGGraphRunner(retriever)
            logger.success("LangGraph RAG pipeline ready!")

    except FileNotFoundError as e:
        logger.warning(f"Index not ready ({e}) — RAG disabled. Run POST /ingest after uploading PDFs.")
        _runner = None
    except Exception as e:
        logger.warning(f"RAG startup failed ({e}) — continuing without RAG.")
        _runner = None

    # ── WhatsApp health tracker ───────────────────────────────────────────────
    init_daily_log_table()       # creates data/health_tracker.db if needed
    start_weekly_scheduler()     # Sunday 7pm auto-reports

    yield
    logger.info("API shutdown.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Ask Anything About Endometriosis",
    description="LangGraph-powered RAG with hybrid retrieval + web search fallback.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WhatsApp routes ───────────────────────────────────────────────────────────
app.include_router(whatsapp_router)


# ── Request / Response models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question:   str = Field(..., min_length=3, max_length=2000)
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer:         str
    sources:        list
    confidence:     float
    question:       str
    session_id:     str
    docs_retrieved: int
    model:          str
    answer_type:    str     # "rag" | "web" | "none"

class FeedbackRequest(BaseModel):
    session_id: str
    score:      float = Field(..., ge=0.0, le=1.0)
    comment:    Optional[str] = ""

class IngestResponse(BaseModel):
    status:  str
    message: str

class HealthResponse(BaseModel):
    status:          str
    rag_chain_ready: bool
    model:           str
    doc_count:       int
    is_ingesting:    bool
    pipeline:        str


# ── Background ingestion ──────────────────────────────────────────────────────
def _run_ingestion_background():
    global _runner, _is_ingesting
    _is_ingesting = True
    try:
        vectorstore, bm25, corpus = run_ingestion()
        retriever = HybridRetriever(vectorstore, bm25, corpus)
        _runner   = RAGGraphRunner(retriever)
        logger.success("LangGraph pipeline reloaded after ingestion.")
    except Exception as e:
        logger.error(f"Background ingestion failed: {e}")
    finally:
        _is_ingesting = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/ping")
async def ping():
    """Instant response — used by Railway health check during startup."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root redirect — tells users where the UI is."""
    from fastapi.responses import JSONResponse
    return JSONResponse({
        "app": "Endometriosis Research AI",
        "status": "running",
        "ui": "Open Streamlit on port 8501",
        "docs": "/docs",
        "health": "/health",
    })


@app.get("/health", response_model=HealthResponse)
async def health():
    doc_count = 0
    if _runner:
        try:
            doc_count = _runner.retriever.vectorstore._collection.count()
        except Exception:
            pass
    return {
        "status":          "ok" if _runner else "initializing",
        "rag_chain_ready": _runner is not None,
        "model":           settings.ollama_model,
        "doc_count":       doc_count,
        "is_ingesting":    _is_ingesting,
        "pipeline":        "LangGraph",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not _runner:
        raise HTTPException(
            status_code=503,
            detail="RAG system not ready. Run POST /ingest first.",
        )
    session_id = request.session_id or str(uuid.uuid4())
    try:
        result = await asyncio.to_thread(
            _runner.invoke,
            question=request.question,
            session_id=session_id,
        )
        result["session_id"] = session_id
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest(background_tasks: BackgroundTasks):
    global _is_ingesting
    if _is_ingesting:
        return {"status": "already_running", "message": "Ingestion already in progress."}
    background_tasks.add_task(_run_ingestion_background)
    return {"status": "started", "message": "Ingestion started. Check /health for status."}


@app.post("/upload-pdf")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auto_ingest: bool = True,
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted.")

    save_path = Path("./data/pdfs") / file.filename
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if save_path.exists():
        raise HTTPException(status_code=409, detail=f"'{file.filename}' already exists.")

    content = await file.read()
    save_path.write_bytes(content)
    size_kb = round(len(content) / 1024, 1)
    logger.info(f"PDF uploaded: {file.filename} ({size_kb} KB)")

    if auto_ingest:
        background_tasks.add_task(_run_ingestion_background)

    return {
        "status":               "uploaded",
        "filename":             file.filename,
        "size_kb":              size_kb,
        "ingestion_triggered":  auto_ingest,
        "message":              f"'{file.filename}' uploaded. Indexing started." if auto_ingest else f"'{file.filename}' uploaded.",
    }


@app.delete("/delete-pdf/{filename}")
async def delete_pdf(filename: str, background_tasks: BackgroundTasks):
    save_path = Path("./data/pdfs") / filename
    if not save_path.exists():
        raise HTTPException(status_code=404, detail=f"'{filename}' not found.")
    save_path.unlink()
    background_tasks.add_task(_run_ingestion_background)
    return {"status": "deleted", "filename": filename, "message": "Deleted. Re-indexing started."}


@app.get("/sources")
async def list_sources():
    if not _runner:
        return {"sources": [], "total": 0}
    try:
        all_data = _runner.retriever.vectorstore._collection.get(include=["metadatas"])
        seen, sources = set(), []
        for m in all_data.get("metadatas", []):
            fname = m.get("source_file", "")
            if fname and fname not in seen:
                seen.add(fname)
                sources.append({"file": fname, "title": m.get("paper_title", fname)})
        return {"sources": sorted(sources, key=lambda x: x["title"]), "total": len(sources)}
    except Exception as e:
        return {"sources": [], "total": 0, "error": str(e)}


@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    monitor_db.log_feedback(
        session_id=request.session_id,
        score=request.score,
        comment=request.comment or "",
    )
    return {"status": "ok", "message": "Feedback recorded."}


@app.get("/stats")
async def stats():
    doc_count = bm25_count = 0
    if _runner:
        try:
            doc_count  = _runner.retriever.vectorstore._collection.count()
            bm25_count = len(_runner.retriever.bm25_corpus)
        except Exception:
            pass
    return {
        "chromadb_chunks": doc_count,
        "bm25_chunks":     bm25_count,
        "model":           settings.ollama_model,
        "embed_model":     settings.embed_model,
        "rerank_model":    settings.cohere_rerank_model,
        "retriever_k":     settings.retriever_k,
        "reranker_top_n":  settings.reranker_top_n,
        "pipeline":        "LangGraph",
        "rag_ready":       _runner is not None,
    }


# ── Health Tracker endpoints (so Streamlit can read from FastAPI's DB) ────────

@app.get("/logs")
async def get_logs(days: int = 30):
    from app.daily_log_db import get_logs as _get_logs
    return {"logs": _get_logs(days=days)}

@app.get("/logs/weekly")
async def get_weekly(week_offset: int = 0):
    from app.daily_log_db import get_weekly_summary
    return get_weekly_summary(week_offset=week_offset)

@app.get("/logs/insights")
async def get_insights(days: int = 30):
    from app.daily_log_db import get_insights as _get_insights
    return {"insights": _get_insights(days=days)}

@app.get("/logs/parse")
async def get_parse_logs(days: int = 30):
    from app.daily_log_db import get_parse_logs as _get_parse_logs
    return {"parse_logs": _get_parse_logs(days=days)}

@app.post("/logs/upsert")
async def upsert_log(data: dict):
    from app.daily_log_db import upsert_daily_log
    result = upsert_daily_log(data)
    return {"status": "ok", "result": result}

@app.delete("/logs/{log_date}")
async def delete_log(log_date: str):
    from app.daily_log_db import delete_log as _delete_log
    ok = _delete_log(log_date)
    return {"status": "ok" if ok else "not_found"}


@app.post("/logs/insight")
async def generate_insight(data: dict, background_tasks: BackgroundTasks):
    """Generate AI insight for a manually logged entry (sidebar form)."""
    def _run_insight(data):
        try:
            from app.daily_log_db import get_logs, save_insight
            from app.knowledge_engine import get_food_and_cycle_insight, get_cycle_context
            all_logs = get_logs(days=120)
            cycle_ctx = get_cycle_context(all_logs)
            recent_7  = get_logs(days=7)
            insight = get_food_and_cycle_insight(
                today_data=data,
                logs=recent_7,
                cycle_day=cycle_ctx.get("cycle_day"),
                phase=cycle_ctx.get("phase_key"),
            )
            if insight:
                save_insight(
                    log_date=data.get("log_date"),
                    user_message="[dashboard entry]",
                    ai_reply=insight,
                    insight_type="daily"
                )
        except Exception as e:
            logger.warning(f"Insight generation failed: {e}")
    background_tasks.add_task(_run_insight, data)
    return {"status": "generating"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
