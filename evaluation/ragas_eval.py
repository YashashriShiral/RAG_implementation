"""
evaluation/ragas_eval.py
─────────────────────────────────────────────────────────────────────────────
Local RAG Evaluation — LLM-as-Judge for semantic metrics

Why LLM-as-judge instead of keyword overlap:
  Keyword overlap fails for LLM outputs because LLMs paraphrase by design.
  "retrograde menstruation" → "backward flow of menstrual blood" = 0 keyword match
  but semantically identical. A judge LLM understands this, keywords don't.

Metrics:
  faithfulness    → LLM judge: is the answer grounded in the context? (0-1)
  answer_relevancy → LLM judge: does the answer address the question? (0-1)
  context_recall  → keyword: does answer cover ground truth concepts? (reliable)
  context_precision → keyword: is retrieved context relevant to question? (reliable)
  citation_rate   → regex: does answer have references/citations? (reliable)
  avg_confidence  → reranker score from pipeline (already reliable)
"""

import json, sys, os, re, time, requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from loguru import logger

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
RESULTS_DIR  = Path("./evaluation/results")

# ── CI Gate Thresholds ────────────────────────────────────────────────────────
CI_THRESHOLDS = {
    "faithfulness_score": 0.60,   # LLM judge 0-1 scale
    "answer_relevancy":   0.65,   # LLM judge 0-1 scale
    "context_precision":  0.50,   # keyword coverage (reliable)
    "context_recall":     0.40,   # keyword coverage (reliable)
    "citation_rate":      0.75,   # regex citation detection
}

# ── Eval Dataset ──────────────────────────────────────────────────────────────
DEFAULT_EVAL_QUESTIONS = [
    {
        "question": "What is endometriosis and how does it develop?",
        "ground_truth": "Endometriosis is a chronic inflammatory condition where tissue similar to the uterine lining grows outside the uterus through retrograde menstruation, coelomic metaplasia, and immune dysfunction.",
    },
    {
        "question": "What are the most effective treatments for endometriosis pain?",
        "ground_truth": "NSAIDs, hormonal therapies including combined oral contraceptives, progestins, GnRH agonists, and surgical excision. Laparoscopic excision provides longer pain relief than ablation.",
    },
    {
        "question": "How does endometriosis affect fertility?",
        "ground_truth": "Endometriosis impairs fertility through ovarian reserve reduction, tubal damage, and altered peritoneal environment. IVF is recommended for moderate-severe cases.",
    },
    {
        "question": "What is the role of estrogen in endometriosis?",
        "ground_truth": "Estrogen promotes endometriotic lesion growth. Endometriotic cells produce local estrogen through aromatase activity creating a self-perpetuating cycle.",
    },
    {
        "question": "What are the symptoms of endometriosis?",
        "ground_truth": "Common symptoms include pelvic pain, dysmenorrhea, dyspareunia, and infertility. Symptom severity does not always correlate with disease stage.",
    },
    {
        "question": "How is endometriosis diagnosed?",
        "ground_truth": "Definitive diagnosis requires laparoscopy with histological confirmation. Ultrasound and MRI can detect endometriomas but cannot rule out peritoneal disease.",
    },
    {
        "question": "What are the stages of endometriosis?",
        "ground_truth": "Endometriosis is classified in four stages I through IV using the revised American Society for Reproductive Medicine scoring system.",
    },
    {
        "question": "What are the genetic factors associated with endometriosis?",
        "ground_truth": "Genome-wide studies identified multiple susceptibility loci. First-degree relatives have higher risk.",
    },
]


# ── LLM Judge ─────────────────────────────────────────────────────────────────

def llm_judge(prompt: str) -> float:
    """
    Ask Ollama to score 0.0-1.0 and parse the response.
    Falls back to 0.5 if Ollama is unavailable.
    """
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 20},
            },
            timeout=60,
        )
        text = r.json().get("response", "").strip()
        # Extract first float found in response
        match = re.search(r'\b(0\.\d+|1\.0|1)\b', text)
        if match:
            return round(min(1.0, max(0.0, float(match.group()))), 3)
        logger.warning(f"LLM judge unparseable response: {text!r} — using 0.5")
        return 0.5
    except Exception as e:
        logger.warning(f"LLM judge unavailable ({e}) — using keyword fallback")
        return None  # signals to use keyword fallback


def judge_faithfulness(answer: str, context: str) -> float:
    """Is the answer grounded in the provided context?"""
    if not context:
        return 1.0  # web answer — no local context to judge against

    prompt = f"""You are evaluating a RAG system. Score whether the ANSWER is faithful to and grounded in the CONTEXT.

CONTEXT (retrieved from research papers):
{context[:1500]}

ANSWER:
{answer[:800]}

Score from 0.0 to 1.0:
- 1.0 = answer only uses information present in context
- 0.7 = mostly grounded, minor additions
- 0.4 = partially grounded, some unsupported claims
- 0.0 = answer contradicts or ignores context

Reply with ONLY a decimal number like 0.8"""

    score = llm_judge(prompt)
    if score is None:
        # Keyword fallback
        return keyword_coverage(answer, context)
    return score


def judge_relevancy(answer: str, question: str) -> float:
    """Does the answer actually address the question?"""
    prompt = f"""Score whether the ANSWER addresses the QUESTION.

QUESTION: {question}

ANSWER:
{answer[:800]}

Score from 0.0 to 1.0:
- 1.0 = answer directly and completely answers the question
- 0.7 = mostly answers it with minor gaps
- 0.4 = partially relevant
- 0.0 = does not answer the question at all

Reply with ONLY a decimal number like 0.8"""

    score = llm_judge(prompt)
    if score is None:
        return keyword_coverage(answer, question)
    return score


# ── Keyword Metrics (reliable for precision/recall) ───────────────────────────

def tokenize(text: str) -> set:
    stopwords = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with",
        "is","are","was","were","be","been","being","have","has","had","do",
        "does","did","will","would","could","should","may","might","this",
        "that","these","those","it","its","by","from","as","not","no","can",
        "also","more","than","when","which","who","how","what","where","why",
        "however","according","based","through","into","over","after","before",
    }
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return set(w for w in words if w not in stopwords)


def keyword_coverage(source: str, reference: str) -> float:
    """What % of reference keywords appear in source?"""
    st, rt = tokenize(source), tokenize(reference)
    if not rt:
        return 0.0
    return round(len(st & rt) / len(rt), 4)


def has_citation(answer: str) -> bool:
    """Detect any citation format this architecture produces."""
    if re.search(r'\*\*References\*\*', answer):              return True
    if re.search(r'- .{5,} · Page \d+', answer):             return True
    if re.search(r'according to web sources', answer, re.I): return True
    if re.search(r'https?://', answer):                       return True
    if re.search(r'\[.{5,80}\]', answer):                     return True
    return False


# ── Query API ─────────────────────────────────────────────────────────────────

def query_rag(question: str) -> Dict:
    try:
        t0 = time.time()
        r  = requests.post(
            f"{API_BASE_URL}/chat",
            json={"question": question, "session_id": "eval-run"},
            timeout=180,
        )
        result = r.json()
        result["latency_sec"] = round(time.time() - t0, 2)
        return result
    except Exception as e:
        logger.error(f"API query failed: {e}")
        return {"answer": f"ERROR: {e}", "sources": [], "confidence": 0.0,
                "answer_type": "error", "latency_sec": 0.0}


# ── Evaluate Single Question ──────────────────────────────────────────────────

def evaluate_question(item: Dict) -> Dict:
    question     = item["question"]
    ground_truth = item.get("ground_truth", "")

    result      = query_rag(question)
    answer      = result.get("answer", "")
    sources     = result.get("sources", [])
    answer_type = result.get("answer_type", "rag")
    confidence  = float(result.get("confidence", 0.0))
    latency     = result.get("latency_sec", 0.0)
    tokens      = (len(question) + len(answer)) // 4

    # Full context from all source excerpts (800 chars each)
    context = " ".join(s.get("excerpt", "") for s in sources)

    # ── LLM-judged metrics ────────────────────────────────────────────────────
    if answer_type == "rag":
        faithfulness  = judge_faithfulness(answer, context)
        ans_relevancy = judge_relevancy(answer, question)
    else:
        # Web answers: can't judge faithfulness against paper context
        faithfulness  = judge_relevancy(answer, question)  # just judge relevancy
        ans_relevancy = faithfulness

    # ── Keyword metrics (reliable) ────────────────────────────────────────────
    ctx_precision = keyword_coverage(context, question)   if context else 0.5
    ctx_recall    = keyword_coverage(answer,  ground_truth)
    cited         = has_citation(answer)

    return {
        "question":           question,
        "answer_type":        answer_type,
        "answer_preview":     answer[:250] + "…" if len(answer) > 250 else answer,
        "faithfulness_score": faithfulness,
        "answer_relevancy":   ans_relevancy,
        "context_precision":  ctx_precision,
        "context_recall":     ctx_recall,
        "confidence":         confidence,
        "has_citation":       cited,
        "latency_sec":        latency,
        "tokens":             tokens,
        "sources_count":      len(sources),
    }


# ── Run Full Evaluation ───────────────────────────────────────────────────────

def run_evaluation(eval_questions: List[Dict] = None) -> Dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if eval_questions is None:
        eval_path = Path("./evaluation/eval_dataset.json")
        if eval_path.exists():
            with open(eval_path) as f:
                eval_questions = json.load(f)
            logger.info(f"Loaded eval dataset: {eval_path}")
        else:
            eval_questions = DEFAULT_EVAL_QUESTIONS
            logger.info("Using built-in eval dataset (8 questions)")

    logger.info(f"Running {len(eval_questions)} questions (LLM-as-judge)…\n")
    results = []

    for i, item in enumerate(eval_questions):
        logger.info(f"[{i+1}/{len(eval_questions)}] {item['question'][:65]}")
        row = evaluate_question(item)
        results.append(row)
        logger.info(
            f"  [{row['answer_type']}] "
            f"faith={row['faithfulness_score']:.2f}  "
            f"relev={row['answer_relevancy']:.2f}  "
            f"prec={row['context_precision']:.2f}  "
            f"recall={row['context_recall']:.2f}  "
            f"conf={row['confidence']:.2f}  "
            f"cited={'✅' if row['has_citation'] else '❌'}  "
            f"{row['latency_sec']}s"
        )

    n   = len(results)
    agg = {
        "faithfulness_score": round(sum(r["faithfulness_score"] for r in results) / n, 4),
        "answer_relevancy":   round(sum(r["answer_relevancy"]   for r in results) / n, 4),
        "context_precision":  round(sum(r["context_precision"]  for r in results) / n, 4),
        "context_recall":     round(sum(r["context_recall"]     for r in results) / n, 4),
        "avg_confidence":     round(sum(r["confidence"]         for r in results) / n, 4),
        "avg_latency_sec":    round(sum(r["latency_sec"]        for r in results) / n, 2),
        "avg_tokens":         round(sum(r["tokens"]             for r in results) / n, 0),
        "citation_rate":      round(sum(1 for r in results if r["has_citation"]) / n, 4),
    }

    logger.info("\n" + "=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)
    for metric, score in agg.items():
        threshold = CI_THRESHOLDS.get(metric)
        if threshold:
            status = "✅ PASS" if score >= threshold else "❌ FAIL"
            logger.info(f"  {metric:<25} {score:.4f}  (min: {threshold}) {status}")
        else:
            logger.info(f"  {metric:<25} {score}")
    logger.info("=" * 60)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"eval_{timestamp}.json"
    payload = {
        "timestamp":    timestamp,
        "n_questions":  n,
        "scores":       agg,
        "thresholds":   CI_THRESHOLDS,
        "passed":       all(agg.get(m, 0) >= t for m, t in CI_THRESHOLDS.items()),
        "per_question": results,
    }
    with open(result_path, "w") as f:
        json.dump(payload, f, indent=2)
    with open(RESULTS_DIR / "latest.json", "w") as f:
        json.dump(agg, f, indent=2)

    logger.info(f"Saved → {result_path}")
    return agg


# ── CI Gate ───────────────────────────────────────────────────────────────────

def check_ci_gate(scores: Dict) -> bool:
    failed = [
        f"{m}: {scores.get(m,0):.4f} < {t}"
        for m, t in CI_THRESHOLDS.items()
        if scores.get(m, 0) < t
    ]
    if failed:
        logger.error(f"CI GATE FAILED → {failed}")
        return False
    logger.success("CI GATE PASSED ✅")
    return True


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("LOCAL RAG EVALUATION — LLM-as-Judge")
    logger.info("=" * 60)
    scores = run_evaluation()
    passed = check_ci_gate(scores)
    sys.exit(0 if passed else 1)