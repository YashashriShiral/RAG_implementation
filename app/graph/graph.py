"""
app/graph/graph.py
─────────────────────────────────────────────────────────────────────────────
LangGraph graph assembly.

Graph structure:
  START
    ↓
  retrieve_node        ← BM25 + vector + RRF + Cohere reranking
    ↓
  grade_docs_node      ← relevance score threshold check
    ↓
    ├── relevant=True  → generate_rag_node   ← LLaMA + paper citations
    │                        ↓
    │                       END
    │
    └── relevant=False → web_search_node     ← Tavily
                              ↓
                         generate_web_node   ← LLaMA + web sources
                              ↓
                             END

To add a new agent in future:
  1. Add node function in nodes.py
  2. Add routing logic in edges.py
  3. Add 3 lines here: graph.add_node(), graph.add_edge() or
     graph.add_conditional_edges()
"""

from __future__ import annotations
from functools import partial

from langgraph.graph import StateGraph, END
from loguru import logger

from app.graph.state import RAGState
from app.graph.nodes import (
    retrieve_node,
    grade_docs_node,
    web_search_node,
    generate_rag_node,
    generate_web_node,
)
from app.graph.edges import route_after_grading
from app import monitor_db


def build_graph(retriever):
    """
    Assemble and compile the RAG LangGraph.
    Returns a compiled graph ready for .invoke().

    Args:
        retriever: HybridRetriever instance (injected at startup)
    """
    graph = StateGraph(RAGState)

    # ── Register nodes ────────────────────────────────────────────────────────
    # partial() injects the retriever into retrieve_node
    # (LangGraph nodes only receive state — use partial for dependencies)
    graph.add_node("retrieve",     partial(retrieve_node, retriever=retriever))
    graph.add_node("grade_docs",   grade_docs_node)
    graph.add_node("web_search",   web_search_node)
    graph.add_node("generate_rag", generate_rag_node)
    graph.add_node("generate_web", generate_web_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("retrieve")

    # ── Edges ─────────────────────────────────────────────────────────────────
    # retrieve → grade_docs (always)
    graph.add_edge("retrieve", "grade_docs")

    # grade_docs → conditional branch
    graph.add_conditional_edges(
        "grade_docs",
        route_after_grading,
        {
            "generate_rag": "generate_rag",
            "web_search":   "web_search",
        },
    )

    # web_search → generate_web (always)
    graph.add_edge("web_search", "generate_web")

    # Both generation nodes → END
    graph.add_edge("generate_rag", END)
    graph.add_edge("generate_web", END)

    # ── Compile ───────────────────────────────────────────────────────────────
    compiled = graph.compile()
    logger.success("LangGraph RAG graph compiled successfully")
    return compiled


class RAGGraphRunner:
    """
    Thin wrapper around the compiled LangGraph.
    Provides the same .invoke() interface as the old EndometriosisRAGChain
    so api.py needs minimal changes.
    Also handles SQLite monitoring logging.
    """

    def __init__(self, retriever):
        self.retriever = retriever
        self.graph     = build_graph(retriever)
        logger.info("RAGGraphRunner ready")

    def invoke(self, question: str, session_id: str = None) -> dict:
        """
        Run the full LangGraph pipeline and return structured result.
        Logs everything to SQLite monitoring DB.
        """
        initial_state: RAGState = {
            "question":      question,
            "session_id":    session_id or "unknown",
            "docs":          [],
            "retrieval_ms":  0,
            "docs_relevant": False,
            "web_results":   "",
            "answer":        "",
            "sources":       [],
            "confidence":    0.0,
            "answer_type":   "none",
            "llm_ms":        0,
            "error":         None,
        }

        try:
            final_state = self.graph.invoke(initial_state)
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            monitor_db.log_query(
                session_id=session_id or "unknown",
                question=question,
                answer="",
                confidence=0.0,
                docs_retrieved=0,
                sources_cited=0,
                retrieval_ms=0,
                llm_ms=0,
                model="llama3.2",
                error=str(e),
            )
            raise

        # ── Log to SQLite ─────────────────────────────────────────────────────
        monitor_db.log_query(
            session_id=session_id or "unknown",
            question=question,
            answer=final_state.get("answer", ""),
            confidence=final_state.get("confidence", 0.0),
            docs_retrieved=len(final_state.get("docs", [])),
            sources_cited=len(final_state.get("sources", [])),
            retrieval_ms=final_state.get("retrieval_ms", 0),
            llm_ms=final_state.get("llm_ms", 0),
            model="llama3.2",
            error=final_state.get("error"),
        )

        return {
            "answer":         final_state.get("answer", ""),
            "sources":        final_state.get("sources", []),
            "confidence":     final_state.get("confidence", 0.0),
            "question":       question,
            "docs_retrieved": len(final_state.get("docs", [])),
            "model":          "llama3.2",
            "answer_type":    final_state.get("answer_type", "none"),
        }
