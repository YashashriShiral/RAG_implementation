"""
app/config.py
─────────────────────────────────────────────
Single source of truth for all configuration.
Langfuse removed — monitoring via SQLite only.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────────
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str    = Field("llama3.2",              env="OLLAMA_MODEL")

    # ── Embeddings ────────────────────────────────────────────────────────────
    embed_model: str = Field(
        "BAAI/bge-base-en-v1.5", env="EMBED_MODEL"
    )

    # ── Cohere (Reranking) ────────────────────────────────────────────────────
    cohere_api_key:      str = Field(...,                    env="COHERE_API_KEY")
    cohere_rerank_model: str = Field("rerank-english-v3.0", env="COHERE_RERANK_MODEL")

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field("./data/chroma_db",        env="CHROMA_PERSIST_DIR")
    chroma_collection:  str = Field("endometriosis_papers",    env="CHROMA_COLLECTION")

    # ── RAG Tuning ────────────────────────────────────────────────────────────
    chunk_size:      int   = Field(900,  env="CHUNK_SIZE")    # bigger = more context per chunk
    chunk_overlap:   int   = Field(200,  env="CHUNK_OVERLAP") # more overlap = fewer split sentences
    retriever_k:     int   = Field(40,   env="RETRIEVER_K")   # more candidates for reranker
    reranker_top_n:  int   = Field(4,    env="RERANKER_TOP_N")# top-4 only: higher avg quality
    bm25_weight:     float = Field(0.35, env="BM25_WEIGHT")
    vector_weight:   float = Field(0.65, env="VECTOR_WEIGHT")

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000,      env="API_PORT")

    # ── Tavily Web Search (fallback when docs not relevant) ─────────────────────
    tavily_api_key: Optional[str] = Field(None, env="TAVILY_API_KEY")

    # ── Streamlit ─────────────────────────────────────────────────────────────
    api_base_url: str = Field("http://localhost:8000", env="API_BASE_URL")

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        extra             = "ignore"   # silently ignore unknown env vars


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()