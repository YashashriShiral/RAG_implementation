"""
app/graph/state.py
─────────────────────────────────────────────────────────────────────────────
Shared state object passed between all LangGraph nodes.

Adding a new agent in future?
  1. Add new fields here
  2. Add node in nodes.py
  3. Add edge in graph.py
  That's it — no other files need changing.
"""

from __future__ import annotations
from typing import List, Optional
from typing_extensions import TypedDict
from langchain.schema import Document


class RAGState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    question:       str
    session_id:     str

    # ── Retrieval ─────────────────────────────────────────────────────────────
    docs:           List[Document]
    retrieval_ms:   int

    # ── Grading ───────────────────────────────────────────────────────────────
    docs_relevant:  bool

    # ── Web Search ────────────────────────────────────────────────────────────
    web_results:    str

    # ── Generation ────────────────────────────────────────────────────────────
    answer:         str
    sources:        List[dict]
    confidence:     float
    answer_type:    str          # "rag" | "web" | "none"
    llm_ms:         int

    # ── Meta ──────────────────────────────────────────────────────────────────
    error:          Optional[str]

    # ── Future agent slots (add fields here as you extend) ────────────────────
    # clarification_needed: bool
    # pubmed_results:        str
    # decomposed_questions:  List[str]
    # clinical_trial_data:   str
