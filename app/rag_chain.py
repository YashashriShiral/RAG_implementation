"""
app/rag_chain.py
─────────────────────────────────────────────────────────────────────────────
RAG Chain with:
  - Citation enforcement (paper names, not [SOURCE N])
  - Relevance gating → if no relevant docs, triggers Tavily web search
  - Web fallback answer clearly labeled as from web, not research papers
  - SQLite monitoring
"""

from __future__ import annotations
import re
import time
from typing import List, Dict, Any, Optional

from langchain.schema import Document
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from loguru import logger

from app.config import get_settings
from app import monitor_db

settings = get_settings()


# ── Prompts ───────────────────────────────────────────────────────────────────

# Used when relevant documents are found
RAG_PROMPT = """You are a specialized medical research assistant for endometriosis.
Answer ONLY based on the provided research paper excerpts below.
Cite the exact paper name in square brackets after every factual claim.
Example: "Retrograde menstruation occurs in 90% of women [Sampson Endometriosis Theory]."
If a fact is in multiple papers, cite all: [Paper A][Paper B].
End your answer with a References section listing cited papers and page numbers.

=== RESEARCH PAPER EXCERPTS ===
{context}
=== END OF EXCERPTS ===

QUESTION: {question}

ANSWER (with paper name citations):"""

# Used when web search results are available (no docs found)
WEB_PROMPT = """You are a medical research assistant for endometriosis.
The user's question was NOT found in the local research paper database.
Answer using ONLY the web search results below.
Start your answer with exactly: "This information is not available in the provided research papers."
Then on a new line say: "However, according to web sources:"
Then give a clear, helpful answer citing the source URLs in brackets.

=== WEB SEARCH RESULTS ===
{web_results}
=== END ===

QUESTION: {question}

ANSWER:"""

# Used when neither docs nor web results are available
NO_INFO_RESPONSE = (
    "This information is not available in the provided research papers, "
    "and a web search did not return relevant results. "
    "Please consult a medical professional or search PubMed directly for this topic."
)


# ── Context Formatting ────────────────────────────────────────────────────────
def format_context(docs: List[Document]) -> tuple[str, List[Dict]]:
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
            "source_path":  meta.get("source_path", ""),
            "rerank_score": score,
            "excerpt":      doc.page_content[:300] + "…" if len(doc.page_content) > 300 else doc.page_content,
        })
    return "\n---\n".join(parts), source_map


# ── Citation Helpers ──────────────────────────────────────────────────────────
def extract_cited_sources(answer: str, source_map: List[Dict]) -> List[Dict]:
    answer_lower = answer.lower()
    cited = []
    for s in source_map:
        title = s["paper_title"].lower()
        if title[:30] in answer_lower or f"[{title[:20]}" in answer_lower:
            cited.append(s)
    return cited

def enforce_citations(answer: str, source_map: List[Dict]) -> tuple[str, List[Dict]]:
    cited = extract_cited_sources(answer, source_map)
    if not cited and source_map:
        logger.warning("No citations found — auto-appending references")
        ref = "\n\n**References:**\n" + "".join(
            f"- [{s['paper_title']}], Page {s['page']}\n" for s in source_map
        )
        answer += ref
        cited = source_map
    return answer, cited


# ── Tavily Web Search ─────────────────────────────────────────────────────────
def tavily_search(query: str) -> Optional[str]:
    """
    Search the web using Tavily API.
    Returns formatted string of results or None if unavailable.
    """
    tavily_key = getattr(settings, "tavily_api_key", None)
    if not tavily_key:
        logger.warning("TAVILY_API_KEY not set — web search unavailable")
        return None
    try:
        from tavily import TavilyClient
        client  = TavilyClient(api_key=tavily_key)
        results = client.search(
            query=f"endometriosis {query}",
            max_results=4,
            include_answer=True,
            include_raw_content=False,
        )
        if not results:
            return None

        parts = []
        # Include Tavily's direct answer if available
        if results.get("answer"):
            parts.append(f"Summary: {results['answer']}\n")

        for r in results.get("results", []):
            title   = r.get("title", "")
            url     = r.get("url", "")
            content = r.get("content", "")[:500]
            parts.append(f"Source: {title}\nURL: {url}\nContent: {content}\n")

        return "\n---\n".join(parts) if parts else None

    except ImportError:
        logger.warning("tavily-python not installed. Run: pip install tavily-python")
        return None
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return None


# ── LLM ──────────────────────────────────────────────────────────────────────
def get_llm() -> OllamaLLM:
    return OllamaLLM(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.1,
        top_p=0.9,
        num_ctx=4096,
        repeat_penalty=1.1,
    )


# ── RAG Chain ─────────────────────────────────────────────────────────────────
class EndometriosisRAGChain:

    def __init__(self, retriever):
        self.retriever = retriever
        self.llm       = get_llm()
        logger.info(f"RAG chain ready — model: {settings.ollama_model}")

    def _confidence(self, docs: List[Document]) -> float:
        if not docs:
            return 0.0
        scores = [float(d.metadata.get("rerank_score", 0.5)) for d in docs]
        return round(sum(scores) / len(scores), 3)

    def invoke(self, question: str, session_id: str = None) -> Dict[str, Any]:
        t0 = time.time()

        # ── Step 1: Hybrid retrieval ──────────────────────────────────────────
        docs         = self.retriever.retrieve(question)
        retrieval_ms = int((time.time() - t0) * 1000)
        confidence   = self._confidence(docs)

        # ── Step 2: Branch on whether docs are relevant ───────────────────────
        if docs:
            # ── BRANCH A: Relevant docs found → normal RAG answer ─────────────
            context, source_map = format_context(docs)
            prompt = RAG_PROMPT.format(context=context, question=question)

            logger.info(f"Generating RAG answer ({len(docs)} docs) …")
            t1 = time.time()
            try:
                raw = self.llm.invoke(prompt)
            except Exception as e:
                monitor_db.log_query(
                    session_id=session_id or "unknown", question=question,
                    answer="", confidence=0.0, docs_retrieved=len(docs),
                    sources_cited=0, retrieval_ms=retrieval_ms, llm_ms=0,
                    model=settings.ollama_model, error=str(e),
                )
                raise
            llm_ms       = int((time.time() - t1) * 1000)
            final, cited = enforce_citations(raw, source_map)
            answer_type  = "rag"

        else:
            # ── BRANCH B: No relevant docs → try web search ───────────────────
            logger.info("No relevant docs found — trying Tavily web search …")
            source_map = []
            cited      = []
            t1         = time.time()

            web_results = tavily_search(question)

            if web_results:
                prompt = WEB_PROMPT.format(web_results=web_results, question=question)
                logger.info("Generating answer from web results …")
                try:
                    final = self.llm.invoke(prompt)
                except Exception as e:
                    final = (
                        "This information is not available in the provided research papers. "
                        f"Web search was attempted but generation failed: {e}"
                    )
                # Ensure the required prefix is present
                if not final.strip().startswith("This information is not available"):
                    final = (
                        "This information is not available in the provided research papers.\n\n"
                        "However, according to web sources:\n\n" + final
                    )
                answer_type = "web"
            else:
                # Neither docs nor web → clean fallback
                final       = NO_INFO_RESPONSE
                answer_type = "none"

            llm_ms     = int((time.time() - t1) * 1000)
            confidence = 0.0

        # ── Step 3: Log to SQLite ─────────────────────────────────────────────
        monitor_db.log_query(
            session_id=session_id or "unknown",
            question=question,
            answer=final,
            confidence=confidence,
            docs_retrieved=len(docs),
            sources_cited=len(cited),
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            model=settings.ollama_model,
        )

        logger.success(
            f"[{answer_type.upper()}] confidence={confidence} sources={len(cited)} "
            f"retrieval={retrieval_ms}ms llm={llm_ms}ms"
        )

        return {
            "answer":         final,
            "sources":        cited,
            "confidence":     confidence,
            "question":       question,
            "docs_retrieved": len(docs),
            "model":          settings.ollama_model,
            "answer_type":    answer_type,   # "rag" | "web" | "none"
        }