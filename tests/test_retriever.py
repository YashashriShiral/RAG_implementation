"""
tests/test_retriever.py — Unit tests for hybrid retrieval + API
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain.schema import Document

from app.retriever import reciprocal_rank_fusion, bm25_retrieve


# ── RRF Tests ─────────────────────────────────────────────────────────────────

def make_doc(content: str, meta: dict = None) -> Document:
    return Document(page_content=content, metadata=meta or {})


def test_rrf_deduplicates():
    """RRF should merge identical documents and not return duplicates."""
    doc_a = make_doc("endometriosis causes")
    doc_b = make_doc("treatment options")

    list1 = [doc_a, doc_b]
    list2 = [doc_a, doc_b]

    result = reciprocal_rank_fusion([list1, list2])
    contents = [doc.page_content for doc, _ in result]
    assert len(contents) == len(set(contents)), "Duplicates found in RRF output"


def test_rrf_scores_higher_ranked_docs_more():
    """Document ranked 1st in both lists should score highest."""
    doc_top = make_doc("highly relevant content about endometriosis symptoms")
    doc_mid = make_doc("moderately relevant content")
    doc_low = make_doc("less relevant content")

    list1 = [doc_top, doc_mid, doc_low]
    list2 = [doc_top, doc_low, doc_mid]

    result = reciprocal_rank_fusion([list1, list2])
    assert result[0][0].page_content == doc_top.page_content, \
        "Top-ranked doc should be first after RRF"


def test_rrf_single_list():
    """RRF with a single list should preserve order."""
    docs = [make_doc(f"doc {i}") for i in range(5)]
    result = reciprocal_rank_fusion([docs])
    result_contents = [d.page_content for d, _ in result]
    assert result_contents[0] == docs[0].page_content


def test_rrf_empty():
    """RRF with empty lists should return empty result."""
    result = reciprocal_rank_fusion([[], []])
    assert result == []


# ── BM25 Tests ────────────────────────────────────────────────────────────────

def test_bm25_returns_relevant_docs():
    """BM25 should return docs containing query terms."""
    from rank_bm25 import BM25Okapi

    corpus = [
        make_doc("endometriosis treatment surgery laparoscopy"),
        make_doc("diabetes insulin blood sugar management"),
        make_doc("endometriosis pain hormonal therapy estrogen"),
        make_doc("cardiovascular heart disease cholesterol"),
    ]
    tokenized = [d.page_content.lower().split() for d in corpus]
    bm25 = BM25Okapi(tokenized)

    results = bm25_retrieve("endometriosis treatment", bm25, corpus, k=2)
    assert len(results) == 2
    contents = " ".join(d.page_content for d in results)
    assert "endometriosis" in contents, "Top results should contain 'endometriosis'"


def test_bm25_k_limit():
    """BM25 should not return more than k results."""
    from rank_bm25 import BM25Okapi

    corpus = [make_doc(f"document {i} about endometriosis") for i in range(10)]
    tokenized = [d.page_content.lower().split() for d in corpus]
    bm25 = BM25Okapi(tokenized)

    results = bm25_retrieve("endometriosis", bm25, corpus, k=3)
    assert len(results) <= 3


# ── Citation Tests ─────────────────────────────────────────────────────────────

def test_citation_extraction():
    """extract_cited_sources should find [SOURCE N] references."""
    from app.rag_chain import extract_cited_sources

    source_map = [
        {"index": 1, "paper_title": "Paper A", "page": 5, "source_file": "a.pdf",
         "rerank_score": 0.9, "excerpt": "excerpt a"},
        {"index": 2, "paper_title": "Paper B", "page": 12, "source_file": "b.pdf",
         "rerank_score": 0.7, "excerpt": "excerpt b"},
    ]

    answer = "Endometriosis [SOURCE 1] is influenced by estrogen [SOURCE 2]."
    cited = extract_cited_sources(answer, source_map)

    assert len(cited) == 2
    assert cited[0]["paper_title"] == "Paper A"
    assert cited[1]["paper_title"] == "Paper B"


def test_citation_extraction_uncited():
    """If no [SOURCE N] found, should return empty list."""
    from app.rag_chain import extract_cited_sources

    source_map = [{"index": 1, "paper_title": "Paper A", "page": 1,
                   "source_file": "a.pdf", "rerank_score": 0.8, "excerpt": "..."}]
    answer = "Endometriosis is a chronic condition."  # No citations
    cited = extract_cited_sources(answer, source_map)
    assert cited == []


# ── API Integration Tests (requires running API) ─────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint():
    """Health endpoint should return 200."""
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://localhost:8000/health", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert "status" in data
            assert "rag_chain_ready" in data
        except httpx.ConnectError:
            pytest.skip("API not running — skipping integration test")


@pytest.mark.asyncio
async def test_chat_endpoint_validation():
    """Chat endpoint should reject empty questions."""
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                "http://localhost:8000/chat",
                json={"question": "hi"},  # too short (min 5 chars)
                timeout=5,
            )
            assert r.status_code == 422  # Validation error
        except httpx.ConnectError:
            pytest.skip("API not running — skipping integration test")
