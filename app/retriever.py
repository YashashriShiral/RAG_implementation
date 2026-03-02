"""
app/retriever.py
─────────────────────────────────────────────────────────────────────────────
Hybrid Retrieval + Reranking + Relevance Gating

Key addition: relevance_threshold
  After reranking, if the top document's Cohere score < threshold,
  the retriever returns an EMPTY list. This signals to the RAG chain
  that the question is outside the document scope → triggers web search.

Without this gate, every question gets 5 documents regardless of relevance,
causing the LLM to hallucinate connections or cite papers incorrectly.
"""

from __future__ import annotations
import re
from typing import List, Tuple
import cohere
from loguru import logger
from langchain.schema import Document
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi
from app.config import get_settings

settings = get_settings()

RRF_K = 60

# ── Relevance gate: if best rerank score < this, docs are not relevant ────────
RELEVANCE_THRESHOLD = 0.15   # Cohere scores: 0-1. Below 0.15 = not in docs.


def bm25_tokenize(text: str) -> List[str]:
    """
    Tokenize for BM25 — NO stopword removal.

    Reason: In medical/clinical text, words like "not", "no", "can", "will"
    carry critical meaning (negation, possibility, prognosis).
    Removing them destroys query intent.

    BM25's IDF naturally down-weights truly high-frequency words
    that appear in every document — stopword removal is redundant
    and harmful here.

    Example: "is endometriosis related to cancer?" vs "cancer treatment"
    — keeping "is", "to", "related" preserves the diagnostic intent.
    """
    return re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', text.lower())


def reciprocal_rank_fusion(
    ranked_lists: List[List[Document]],
    k: int = RRF_K,
) -> List[Tuple[Document, float]]:
    scores:  dict[str, float]    = {}
    doc_map: dict[str, Document] = {}
    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list):
            key = doc.page_content[:200].strip()
            scores[key]  = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(doc_map[key], score) for key, score in fused]


def bm25_retrieve(query, bm25, corpus, k) -> List[Document]:
    tokens = bm25_tokenize(query)
    scores = bm25.get_scores(tokens)
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [corpus[i] for i in top_idx]


def vector_retrieve(query, vectorstore, k) -> List[Document]:
    return vectorstore.similarity_search(query, k=k)


def cohere_rerank(
    query: str,
    documents: List[Document],
    top_n: int,
) -> List[Document]:
    if not documents:
        return []
    co = cohere.Client(settings.cohere_api_key)
    passages = [doc.page_content for doc in documents]
    try:
        response = co.rerank(
            model=settings.cohere_rerank_model,
            query=query,
            documents=passages,
            top_n=top_n,
            return_documents=True,
        )
        reranked = []
        for result in response.results:
            doc = documents[result.index]
            doc.metadata["rerank_score"] = round(result.relevance_score, 4)
            reranked.append(doc)
        return reranked
    except Exception as e:
        logger.warning(f"Cohere reranking failed ({e}), using RRF order")
        for doc in documents[:top_n]:
            doc.metadata["rerank_score"] = 0.5
        return documents[:top_n]


class HybridRetriever:
    """
    BM25 + Dense vector + RRF + Cohere reranking.
    Returns empty list if best rerank score < RELEVANCE_THRESHOLD
    so the RAG chain knows to fall back to web search.
    """

    def __init__(self, vectorstore, bm25, bm25_corpus, k=None, reranker_top_n=None):
        self.vectorstore    = vectorstore
        self.bm25           = bm25
        self.bm25_corpus    = bm25_corpus
        self.k              = k or settings.retriever_k
        self.reranker_top_n = reranker_top_n or settings.reranker_top_n

    def retrieve(self, query: str) -> List[Document]:
        logger.info(f"Hybrid retrieval: '{query[:80]}'")

        bm25_results   = bm25_retrieve(query, self.bm25, self.bm25_corpus, self.k)
        vector_results = vector_retrieve(query, self.vectorstore, self.k)
        fused_docs     = [doc for doc, _ in reciprocal_rank_fusion([bm25_results, vector_results])]

        reranked = cohere_rerank(query, fused_docs, self.reranker_top_n)

        if not reranked:
            logger.info("No documents after reranking.")
            return []

        # ── Relevance gate ────────────────────────────────────────────────────
        best_score = reranked[0].metadata.get("rerank_score", 0.0)
        if best_score < RELEVANCE_THRESHOLD:
            logger.info(
                f"Best rerank score {best_score:.3f} < threshold {RELEVANCE_THRESHOLD} "
                f"→ question is outside document scope → triggering web search fallback"
            )
            return []

        # Filter out low-scoring docs even if best passes threshold
        relevant = [
            doc for doc in reranked
            if doc.metadata.get("rerank_score", 0.0) >= RELEVANCE_THRESHOLD * 0.5
        ]
        logger.info(f"Retrieved {len(relevant)} relevant docs (best score: {best_score:.3f})")
        return relevant