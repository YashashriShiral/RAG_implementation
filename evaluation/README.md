# evaluation/
Local eval pipeline — no external API keys needed.

```bash
python -m evaluation.ragas_eval
# → evaluation/results/eval_YYYYMMDD.json
# → viewable in Monitoring Dashboard → Evaluations tab
```

## Metrics & Thresholds
| Metric | Method | Threshold | Measures |
|--------|--------|-----------|---------|
| `faithfulness_score` | LLM judge (Ollama) | ≥ 0.60 | answer grounded in paper context? |
| `answer_relevancy` | LLM judge (Ollama) | ≥ 0.65 | answer addresses the question? |
| `context_precision` | keyword coverage | ≥ 0.50 | retrieved context relevant to question? |
| `context_recall` | keyword coverage | ≥ 0.40 | answer covers ground truth concepts? |
| `citation_rate` | regex | ≥ 0.75 | ≥75% of answers have citations? |

**Why LLM judge for faithfulness/relevancy:**  
Keyword overlap fails on LLM outputs — `"retrograde menstruation"` → `"backward flow of menstrual blood"` is correct but scores 0 on keywords. Ollama judge understands semantics. Falls back to keyword if Ollama unavailable.

**Web answers:** Tavily answers skip faithfulness (no local context) — only relevancy, recall, citation checked.

## Adding questions
Create `evaluation/eval_dataset.json` (overrides built-in 8 questions):
```json
[{"question": "...", "ground_truth": "..."}]
```

## CI gate
Any metric below threshold → `exit 1` → blocks merge.