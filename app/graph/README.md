# app/graph/
LangGraph pipeline — QA logic as a state machine.

| File | Does |
|------|------|
| `state.py` | `RAGState` TypedDict — shared data across all nodes |
| `nodes.py` | All node functions |
| `edges.py` | Routing between nodes |
| `graph.py` | Assembles graph + `RAGGraphRunner` wrapper |

## Flow
```
retrieve_node  →  grade_docs_node
                      ├── relevant → generate_rag_node → END
                      └── not relevant → web_search_node → generate_web_node → END
```

## Nodes
| Node | Does |
|------|------|
| `retrieve_node` | BM25 + vector → RRF → Cohere rerank |
| `grade_docs_node` | best score < 0.15 → `docs_relevant=False` |
| `web_search_node` | Tavily search |
| `generate_rag_node` | LLaMA + paper context → strips `[7][14]` → References block |
| `generate_web_node` | LLaMA + web results → adds disclaimer |

## RAGState fields
```python
question, session_id          # inputs
docs, retrieval_ms            # from retrieve_node
docs_relevant                 # from grade_docs_node
web_results                   # from web_search_node
answer, sources, confidence   # from generate_*_node
answer_type                   # "rag" | "web" | "none"
llm_ms, error
```
> `confidence = max(rerank_scores)` — not average (avg is dragged down by lower-ranked docs)

## Adding a new agent
```python
# 1. nodes.py
def pubmed_node(state): return {"web_results": search_pubmed(state["question"])}

# 2. edges.py
def route_after_grading(state):
    if state["docs_relevant"]: return "generate_rag"
    if is_clinical(state["question"]): return "pubmed"   # ← new
    return "web_search"

# 3. graph.py
graph.add_node("pubmed", pubmed_node)
graph.add_edge("pubmed", "generate_web")
```