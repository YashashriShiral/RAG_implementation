"""
app/ingestion.py
─────────────────────────────────────────────────────────────────────────────
Improved Ingestion Pipeline

Chunking improvements:
  - Sentence-aware splitting (preserves medical sentences)
  - Larger chunks (800 chars) with more overlap (150) for better context
  - Cleans PDF artifacts (headers, footers, page numbers)
  - Minimum chunk size filter (drops tiny meaningless chunks)

Embedding improvements:
  - Uses BAAI/bge-base-en-v1.5 — much better for medical/scientific text
    than all-MiniLM-L6-v2 (768 dims vs 384 dims, higher MTEB scores)
  - query_instruction prefix for BGE embedding model
  - normalize_embeddings=True for cosine similarity accuracy
"""

import os
import pickle
import hashlib
import re
import logging
from pathlib import Path
from typing import List, Tuple

from loguru import logger
from tqdm import tqdm

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi

from app.config import get_settings

# ── Suppress ChromaDB telemetry errors (cosmetic bug in chromadb 0.5.x) ──────
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMA_TELEMETRY"]     = "false"
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.ERROR)

settings = get_settings()

# ── Paths ─────────────────────────────────────────────────────────────────────
PDF_DIR            = Path("./data/pdfs")
BM25_INDEX_PATH    = Path("./data/bm25_index.pkl")
HASH_REGISTRY_PATH = Path("./data/hash_registry.pkl")

# ── Better embedding model for scientific/medical text ────────────────────────
EMBED_MODEL = "BAAI/bge-base-en-v1.5"


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()

def load_hash_registry() -> dict:
    if HASH_REGISTRY_PATH.exists():
        with open(HASH_REGISTRY_PATH, "rb") as f:
            return pickle.load(f)
    return {}

def save_hash_registry(registry: dict):
    with open(HASH_REGISTRY_PATH, "wb") as f:
        pickle.dump(registry, f)


# ── Embeddings ────────────────────────────────────────────────────────────────
def get_embeddings() -> HuggingFaceEmbeddings:
    """
    BAAI/bge-base-en-v1.5:
    - 768-dimensional embeddings (vs 384 for MiniLM)
    - Trained on large-scale scientific + web text
    - Significantly better retrieval on medical/technical domains
    - Requires query_instruction prefix for queries (not for passages)
    """
    model_name = getattr(settings, "embed_model", EMBED_MODEL)
    # Use BGE if config still has old MiniLM
    if "MiniLM" in model_name or "minilm" in model_name.lower():
        model_name = EMBED_MODEL
        logger.info(f"Upgrading embedding model to {EMBED_MODEL}")
    logger.info(f"Loading embedding model: {model_name}")
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,
        },
    )


# ── Text Cleaning ─────────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    """
    Clean common PDF extraction artifacts that hurt retrieval quality.
    - Removes lone page numbers
    - Collapses excessive whitespace
    - Removes short header/footer lines
    - Fixes hyphenated line breaks
    """
    # Fix hyphenated line breaks (e.g., "endometrio-\nsis" → "endometriosis")
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    # Remove lone page numbers
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    # Remove very short lines (likely headers/footers, < 4 words)
    lines = text.split('\n')
    lines = [l for l in lines if len(l.split()) >= 4 or len(l.strip()) == 0]
    text = '\n'.join(lines)
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple spaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


# ── PDF Loading ───────────────────────────────────────────────────────────────
def load_pdfs(pdf_dir: Path, registry: dict) -> Tuple[List[Document], List[str], dict]:
    all_docs = []
    new_files = []

    pdf_files = list(pdf_dir.glob("**/*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDFs found in {pdf_dir}")
        return [], [], registry

    logger.info(f"Found {len(pdf_files)} PDF(s)")

    for pdf_path in tqdm(pdf_files, desc="Loading PDFs"):
        fhash = file_hash(pdf_path)
        if registry.get(str(pdf_path)) == fhash:
            logger.debug(f"Skipping unchanged: {pdf_path.name}")
            continue

        try:
            loader = PyPDFLoader(str(pdf_path))
            pages  = loader.load()

            for page in pages:
                # Clean PDF artifacts
                page.page_content = clean_text(page.page_content)
                page.metadata.update({
                    "source_file": pdf_path.name,
                    "source_path": str(pdf_path),
                    "paper_title": pdf_path.stem.replace("_", " ").replace("-", " ").title(),
                    "file_hash":   fhash,
                })

            # Drop pages with very little content after cleaning
            pages = [p for p in pages if len(p.page_content.strip()) > 100]
            all_docs.extend(pages)
            registry[str(pdf_path)] = fhash
            new_files.append(pdf_path.name)
            logger.info(f"  Loaded: {pdf_path.name} ({len(pages)} usable pages)")

        except Exception as e:
            logger.error(f"  Failed to load {pdf_path.name}: {e}")

    return all_docs, new_files, registry


# ── Chunking ──────────────────────────────────────────────────────────────────
def chunk_documents(documents: List[Document]) -> List[Document]:
    """
    RecursiveCharacterTextSplitter for medical/scientific text.

    Separators tried in order (most preferred → least):
      1. Double newline  (paragraph break — best split point)
      2. Single newline  (line break)
      3. Period + space  (sentence boundary)
      4. Space           (word boundary)
      5. Empty string    (character — last resort)

    Settings:
      - chunk_size=800   — large enough for full medical context
      - chunk_overlap=150 — prevents losing context at chunk edges
      - Min 100 chars    — drops tiny meaningless fragments
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    raw_chunks = splitter.split_documents(documents)

    # Drop tiny or empty chunks — add metadata
    chunks = []
    for i, chunk in enumerate(raw_chunks):
        text = chunk.page_content.strip()
        if len(text) < 100:
            continue
        chunk.page_content          = text
        chunk.metadata["chunk_id"]  = i
        chunk.metadata["char_count"] = len(text)
        chunks.append(chunk)

    logger.info(
        f"RecursiveCharacterTextSplitter: {len(chunks)} chunks "
        f"from {len(documents)} pages "
        f"(dropped {len(raw_chunks) - len(chunks)} tiny fragments)"
    )
    return chunks


# ── BM25 Tokenizer ────────────────────────────────────────────────────────────
def bm25_tokenize(text: str) -> List[str]:
    """
    Tokenize for BM25 index — NO stopword removal.

    Reason: In medical/clinical text, negation words (not, no, without),
    modal verbs (can, may, will, should) and connectives carry
    critical diagnostic meaning. Removing them corrupts retrieval.

    BM25's IDF handles high-frequency words naturally by down-weighting
    terms that appear across all documents — no manual stoplist needed.
    """
    return re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', text.lower())


# ── Vector Store ──────────────────────────────────────────────────────────────
def build_or_update_vectorstore(chunks, embeddings) -> Chroma:
    logger.info(f"Upserting {len(chunks)} chunks into ChromaDB …")
    vectorstore = Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )
    if chunks:
        vectorstore.add_documents(chunks)
        logger.success(f"ChromaDB updated. Total: {vectorstore._collection.count()} chunks")
    return vectorstore

def load_vectorstore(embeddings) -> Chroma:
    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


# ── BM25 Index ────────────────────────────────────────────────────────────────
def build_bm25_index(all_chunks: List[Document]):
    logger.info("Building BM25 index with improved tokenization …")
    tokenized = [bm25_tokenize(doc.page_content) for doc in all_chunks]
    bm25 = BM25Okapi(tokenized)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump({"bm25": bm25, "documents": all_chunks, "tokenized": tokenized}, f)
    logger.success(f"BM25 index saved ({len(all_chunks)} docs)")
    return bm25, all_chunks

def load_bm25_index():
    if not BM25_INDEX_PATH.exists():
        raise FileNotFoundError("BM25 index not found. Run: python -m app.ingestion")
    with open(BM25_INDEX_PATH, "rb") as f:
        data = pickle.load(f)
    logger.info(f"BM25 loaded ({len(data['documents'])} docs)")
    return data["bm25"], data["documents"]


# ── Full Ingestion ────────────────────────────────────────────────────────────
def run_ingestion(pdf_dir: Path = PDF_DIR, force: bool = False):
    logger.info("=" * 60)
    logger.info("INGESTION PIPELINE — improved chunking + BGE embeddings")
    logger.info("=" * 60)

    pdf_dir.mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(exist_ok=True)

    registry = {} if force else load_hash_registry()
    new_docs, new_files, registry = load_pdfs(pdf_dir, registry)

    if not new_docs and not force:
        logger.info("Nothing new to index.")
        embeddings  = get_embeddings()
        vectorstore = load_vectorstore(embeddings)
        bm25, docs  = load_bm25_index()
        return vectorstore, bm25, docs

    new_chunks  = chunk_documents(new_docs) if new_docs else []
    embeddings  = get_embeddings()
    vectorstore = build_or_update_vectorstore(new_chunks, embeddings)

    # Rebuild BM25 from full corpus
    all_data = vectorstore._collection.get(include=["documents", "metadatas"])
    all_corpus = [
        Document(page_content=t, metadata=m)
        for t, m in zip(all_data["documents"], all_data["metadatas"])
    ]
    bm25, corpus = build_bm25_index(all_corpus)
    save_hash_registry(registry)

    logger.success(f"Ingestion complete — {len(new_files)} new file(s), {len(all_corpus)} total chunks")
    return vectorstore, bm25, corpus


if __name__ == "__main__":
    import sys
    run_ingestion(force="--force" in sys.argv)