"""
app/graph/edges.py
─────────────────────────────────────────────────────────────────────────────
Routing logic (conditional edges) for the LangGraph RAG pipeline.

Each function:
  - Receives the current state
  - Returns a string matching a node name
  - LangGraph uses this to decide which node to run next

Adding a new route in future?
  → Add a new condition here
  → Wire it in graph.py with add_conditional_edges()
"""

from __future__ import annotations
from app.graph.state import RAGState


def route_after_grading(state: RAGState) -> str:
    """
    After grade_docs_node, decide:
      - docs are relevant  → go to generate_rag
      - docs not relevant  → go to web_search
    """
    if state.get("docs_relevant", False):
        return "generate_rag"
    return "web_search"


def route_after_web_search(state: RAGState) -> str:
    """
    After web_search_node, always go to generate_web.
    Web results may be empty — generate_web handles that gracefully.
    """
    return "generate_web"


# ── Future routing stubs ──────────────────────────────────────────────────────

# def route_after_grading_extended(state: RAGState) -> str:
#     """Extended routing when more agents are added."""
#     if state.get("docs_relevant"):
#         return "generate_rag"
#     if state.get("needs_clarification"):
#         return "clarify"
#     if state.get("is_clinical_trial_question"):
#         return "pubmed"
#     return "web_search"

# def route_after_generation(state: RAGState) -> str:
#     """Self-evaluation route — re-retrieve if answer quality is low."""
#     if state.get("answer_quality_score", 1.0) < 0.4:
#         return "retrieve"   # loop back
#     return END
