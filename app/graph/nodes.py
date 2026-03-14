"""
app/graph/nodes.py
─────────────────────────────────────────────────────────────────────────────
All LangGraph node functions.

Each node:
  - Receives the full RAGState
  - Does ONE job
  - Returns a dict with ONLY the fields it updates

Adding a new agent?
  → Add a new function here following the same pattern.
  → Then wire it in graph.py.
"""

from __future__ import annotations

import re
import time
from typing import List, Dict, Optional

from langchain.schema import Document
from loguru import logger
from app.config import get_settings
from app.graph.state import RAGState
from app.llm_client import llm_complete

settings = get_settings()

# ── Relevance threshold ───────────────────────────────────────────────────────
# Cohere scores 0-1. Below this = docs not relevant → trigger web search
RELEVANCE_THRESHOLD = 0.15


# ── Prompts ───────────────────────────────────────────────────────────────────
RAG_PROMPT = """You are a specialized medical research assistant for endometriosis.
Answer ONLY based on the provided research paper excerpts below.

STRICT RULES — follow exactly:
1. Write a clear, flowing answer in plain prose. No bullet points.
2. Do NOT include any inline citations, brackets, or numbers like [1], [7], [5][14] in your answer text.
3. Do NOT reference paper titles inline in your answer text either.
4. If the answer is not in the sources say: "This information is not available in the provided research papers."
5. After your answer, write nothing else — the system will append the references automatically.

=== RESEARCH PAPER EXCERPTS ===
{context}
=== END ===

QUESTION: {question}

ANSWER (plain prose, no inline citations):"""

WEB_PROMPT = """You are a medical research assistant for endometriosis.
The user's question was NOT found in the local research paper database.
Answer using ONLY the web search results below.
Start your answer with exactly this line:
"This information is not available in the provided research papers."
Then on a new line write:
"However, according to web sources:"
Then give a clear helpful answer citing source URLs in brackets.

=== WEB SEARCH RESULTS ===
{web_results}
=== END ===

QUESTION: {question}

ANSWER:"""


# ── Helpers ───────────────────────────────────────────────────────────────────
class _LLMWrapper:
    """Wraps llm_client so nodes can call llm.invoke(prompt) unchanged."""
    def __init__(self, temperature=0.1):
        self.temperature = temperature
    def invoke(self, prompt: str) -> str:
        return llm_complete(system="", prompt=prompt,
                           max_tokens=1024, temperature=self.temperature)

def get_llm(temperature=0.1):
    return _LLMWrapper(temperature=temperature)


def format_context(docs: List[Document]) -> tuple[str, List[Dict]]:
    """Format docs for prompt and build source_map for citations."""
    parts      = []
    source_map = []
    for i, doc in enumerate(docs, 1):
        meta  = doc.metadata
        title = meta.get("paper_title", meta.get("source_file", "Unknown"))
        page  = meta.get("page", "?")
        score = meta.get("rerank_score", "N/A")
        parts.append(f"PAPER: [{title}] | Page {page}\n{doc.page_content.strip()}")
        source_map.append({
            "index":        i,
            "paper_title":  title,
            "page":         page,
            "source_file":  meta.get("source_file", ""),
            "rerank_score": score,
            "excerpt":      doc.page_content[:800] + "…" if len(doc.page_content) > 800 else doc.page_content,
        })
    return "\n---\n".join(parts), source_map


def extract_cited_sources(answer: str, source_map: List[Dict]) -> List[Dict]:
    """Find which papers from source_map are cited in the answer."""
    answer_lower = answer.lower()
    cited = []
    for s in source_map:
        title = s["paper_title"].lower()
        if title[:30] in answer_lower or f"[{title[:20]}" in answer_lower:
            cited.append(s)
    return cited


def strip_inline_citations(answer: str) -> str:
    """Remove all [N], [N][M], [N, M] style inline citations the LLM may add."""
    import re
    # Remove number-based citations like [7], [5][14][15], [1, 2, 3]
    answer = re.sub(r'\[(\d+[,\s]*)+\]', '', answer)
    # Remove stray brackets left over
    answer = re.sub(r'\[\s*\]', '', answer)
    # Clean up extra spaces left behind
    answer = re.sub(r' {2,}', ' ', answer)
    return answer.strip()


def enforce_citations(answer: str, source_map: List[Dict]) -> tuple[str, List[Dict]]:
    """Strip any inline [N] citations LLM added, then append a clean References block."""
    # Always strip inline numbered citations from the answer body
    clean_answer = strip_inline_citations(answer)

    # Always append a References block with all retrieved sources
    if source_map:
        ref_lines = ["\n\n---\n**References**"]
        for s in source_map:
            ref_lines.append(f"- {s['paper_title']} · Page {s['page']}")
        clean_answer += "\n".join(ref_lines)

    cited = source_map  # All retrieved sources are the references
    return clean_answer, cited


def get_confidence(docs: List[Document]) -> float:
    """Use BEST rerank score as confidence — not average.
    Average pulls score down because lower-ranked docs score 0.1-0.3.
    Best score reflects how well the top retrieved chunk matches the question.
    """
    if not docs:
        return 0.0
    scores = [float(d.metadata.get("rerank_score", 0.0)) for d in docs]
    return round(max(scores), 3)


# ── Node 1: Retrieve ──────────────────────────────────────────────────────────
def retrieve_node(state: RAGState, retriever) -> dict:
    """
    Hybrid retrieval: BM25 + vector + RRF + Cohere reranking.
    Stores docs and retrieval latency in state.
    """
    logger.info(f"[retrieve_node] question: '{state['question'][:80]}'")
    t0   = time.time()
    docs = retriever.retrieve(state["question"])
    ms   = int((time.time() - t0) * 1000)
    logger.info(f"[retrieve_node] retrieved {len(docs)} docs in {ms}ms")
    return {"docs": docs, "retrieval_ms": ms}


# ── Node 2: Grade Documents ───────────────────────────────────────────────────
def grade_docs_node(state: RAGState) -> dict:
    """
    Grades retrieved docs by checking Cohere rerank scores.
    If best score < RELEVANCE_THRESHOLD → docs_relevant=False → web search.
    This is a deterministic gate (no extra LLM call needed).
    """
    docs = state.get("docs", [])

    if not docs:
        logger.info("[grade_docs_node] no docs → not relevant")
        return {"docs_relevant": False}

    best_score = max(
        float(d.metadata.get("rerank_score", 0.0)) for d in docs
    )

    relevant = best_score >= RELEVANCE_THRESHOLD
    logger.info(
        f"[grade_docs_node] best_score={best_score:.3f} "
        f"threshold={RELEVANCE_THRESHOLD} → relevant={relevant}"
    )
    return {"docs_relevant": relevant}


# ── Node 3: Web Search ────────────────────────────────────────────────────────
def web_search_node(state: RAGState) -> dict:
    """
    Tavily web search fallback.
    Called when docs are not relevant to the question.
    Always prefixes query with 'endometriosis' for domain focus.
    """
    logger.info("[web_search_node] running Tavily search …")

    tavily_key = getattr(settings, "tavily_api_key", None)
    if not tavily_key:
        logger.warning("[web_search_node] TAVILY_API_KEY not set")
        return {"web_results": ""}

    try:
        from tavily import TavilyClient
        client  = TavilyClient(api_key=tavily_key)
        results = client.search(
            query=f"endometriosis {state['question']}",
            max_results=4,
            include_answer=True,
            include_raw_content=False,
        )
        parts = []
        if results.get("answer"):
            parts.append(f"Summary: {results['answer']}\n")
        for r in results.get("results", []):
            parts.append(
                f"Source: {r.get('title','')}\n"
                f"URL: {r.get('url','')}\n"
                f"Content: {r.get('content','')[:500]}\n"
            )
        web_results = "\n---\n".join(parts)
        logger.info(f"[web_search_node] got {len(results.get('results',[]))} web results")
        return {"web_results": web_results}

    except ImportError:
        logger.warning("[web_search_node] tavily-python not installed")
        return {"web_results": ""}
    except Exception as e:
        logger.warning(f"[web_search_node] search failed: {e}")
        return {"web_results": ""}


# ── Node 4: Generate from Docs (RAG) ─────────────────────────────────────────
def generate_rag_node(state: RAGState) -> dict:
    """
    LLaMA generation grounded in retrieved research paper docs.
    Enforces paper name citations.
    """
    logger.info("[generate_rag_node] generating from research papers …")
    docs = state["docs"]

    context, source_map = format_context(docs)
    prompt = RAG_PROMPT.format(context=context, question=state["question"])

    llm = get_llm()
    t0  = time.time()
    try:
        raw = llm.invoke(prompt)
    except Exception as e:
        logger.error(f"[generate_rag_node] LLM error: {e}")
        return {
            "answer":      f"Generation failed: {e}",
            "sources":     [],
            "confidence":  0.0,
            "answer_type": "rag",
            "llm_ms":      0,
            "error":       str(e),
        }
    llm_ms = int((time.time() - t0) * 1000)

    final, cited = enforce_citations(raw, source_map)
    confidence   = get_confidence(docs)

    logger.success(
        f"[generate_rag_node] done — {len(cited)} citations, "
        f"confidence={confidence}, llm={llm_ms}ms"
    )
    return {
        "answer":      final,
        "sources":     cited,
        "confidence":  confidence,
        "answer_type": "rag",
        "llm_ms":      llm_ms,
        "error":       None,
    }


# ── Node 5: Generate from Web Results ────────────────────────────────────────
def generate_web_node(state: RAGState) -> dict:
    """
    LLaMA generation from Tavily web search results.
    Always prefixes answer with the standard "not in papers" disclaimer.
    """
    web_results = state.get("web_results", "")

    if not web_results:
        logger.info("[generate_web_node] no web results — returning fallback")
        return {
            "answer": (
                "This information is not available in the provided research papers, "
                "and a web search did not return relevant results. "
                "Please consult a medical professional or search PubMed directly."
            ),
            "sources":     [],
            "confidence":  0.0,
            "answer_type": "none",
            "llm_ms":      0,
            "error":       None,
        }

    logger.info("[generate_web_node] generating from web results …")
    prompt = WEB_PROMPT.format(
        web_results=web_results,
        question=state["question"],
    )

    llm = get_llm()
    t0  = time.time()
    try:
        answer = llm.invoke(prompt)
    except Exception as e:
        logger.error(f"[generate_web_node] LLM error: {e}")
        answer = (
            "This information is not available in the provided research papers. "
            f"Web search was attempted but generation failed: {e}"
        )
    llm_ms = int((time.time() - t0) * 1000)

    # Ensure required prefix is present
    if not answer.strip().startswith("This information is not available"):
        answer = (
            "This information is not available in the provided research papers.\n\n"
            "However, according to web sources:\n\n" + answer
        )

    logger.success(f"[generate_web_node] done — llm={llm_ms}ms")
    return {
        "answer":      answer,
        "sources":     [],
        "confidence":  0.0,
        "answer_type": "web",
        "llm_ms":      llm_ms,
        "error":       None,
    }


# ── Future node stubs (wire in graph.py when ready) ──────────────────────────

# def clarify_node(state: RAGState) -> dict:
#     """Ask LLM to rewrite ambiguous question before retrieval."""
#     ...

# def decompose_node(state: RAGState) -> dict:
#     """Break multi-hop question into sub-questions."""
#     ...

# def pubmed_node(state: RAGState) -> dict:
#     """Search PubMed API for clinical evidence."""
#     ...

# def grade_answer_node(state: RAGState) -> dict:
#     """Self-evaluate answer quality — re-retrieve if low."""
#     ...