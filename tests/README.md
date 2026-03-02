# tests/
Unit tests for retrieval logic.

```bash
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Coverage
| Test | Checks |
|------|--------|
| `test_rrf_deduplicates` | RRF merges BM25+vector duplicates correctly |
| `test_rrf_scores_higher_ranked_docs_more` | Higher rank → higher RRF score |
| `test_rrf_single_list` | Works with one source only |
| `test_rrf_empty` | Handles empty input |
| `test_bm25_returns_relevant_docs` | BM25 returns keyword-matching docs |
| `test_bm25_k_limit` | Respects top-k |
| `test_citation_extraction` | Finds cited papers in LLM output |
| `test_citation_extraction_uncited` | Handles no citations gracefully |

## Adding tests
```python
def make_doc(content, meta=None):
    return Document(page_content=content, metadata=meta or {})

def test_my_feature():
    docs = [make_doc("endometriosis estrogen aromatase")]
    assert my_function(docs) is not None
```