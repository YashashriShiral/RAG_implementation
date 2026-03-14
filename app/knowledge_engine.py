"""
app/knowledge_engine.py
────────────────────────────────────────────────────────────────────────────
Central intelligence layer. Replaces all hardcoded food/cycle dicts.

Flow for every query:
  1. Search RAG (ChromaDB + BM25 via FastAPI /chat)
  2. Score confidence from result
  3. If confidence < threshold → web search fallback
  4. Always include: today's data + 7-day behaviour summary
  5. LLaMA synthesises everything → insight

No hardcoded food scores. No hardcoded advice strings.
All intelligence comes from ingested PDFs + LLaMA reasoning.
"""

import os, re, requests, json as _json
from datetime import date, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, ValidationError

class NutritionEstimate(BaseModel):
    calories:   Optional[int]   = Field(None, ge=0, le=10000)
    protein_g:  Optional[float] = Field(None, ge=0, le=500)
    carbs_g:    Optional[float] = Field(None, ge=0, le=1000)
    fat_g:      Optional[float] = Field(None, ge=0, le=500)
    fiber_g:    Optional[float] = Field(None, ge=0, le=200)
    iron_mg:    Optional[float] = Field(None, ge=0, le=100)
    calcium_mg: Optional[float] = Field(None, ge=0)
    omega3_g:   Optional[float] = Field(None, ge=0)
    notes:      Optional[str]   = None

# LLM handled by llm_client.py (OpenRouter or Ollama)
from app.llm_client import llm_complete as _llm_complete
MODEL        = "llama3.2"
FASTAPI_BASE = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

# Confidence threshold — below this, trigger web search
RAG_CONFIDENCE_THRESHOLD = 0.45


# ── RAG query ─────────────────────────────────────────────────────────────────
def _rag_query(question: str) -> dict:
    """Query the RAG pipeline. Returns {answer, confidence, sources}."""
    try:
        r = requests.post(
            f"{FASTAPI_BASE}/chat",
            json={"question": question, "session_id": "knowledge_engine"},
            timeout=30.0,
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "answer":     data.get("answer", ""),
                "confidence": data.get("confidence", 0.0),
                "sources":    data.get("sources", []),
                "type":       "rag",
            }
    except Exception:
        pass
    return {"answer": "", "confidence": 0.0, "sources": [], "type": "rag_failed"}


# ── Web search fallback ───────────────────────────────────────────────────────
def _web_search(query: str) -> str:
    """Simple web search via DuckDuckGo instant answer API — no API key needed."""
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=10.0,
        )
        data = r.json()
        abstract = data.get("AbstractText", "")
        if abstract and len(abstract) > 100:
            return abstract[:800]
        # Try related topics
        for topic in data.get("RelatedTopics", [])[:3]:
            text = topic.get("Text", "")
            if len(text) > 80:
                return text[:600]
    except Exception:
        pass
    return ""


# ── LLaMA call ────────────────────────────────────────────────────────────────
def _llama(system: str, prompt: str, max_tokens: int = 400) -> str:
    """Wrapper — uses OpenRouter in cloud, Ollama locally."""
    return _llm_complete(system=system, prompt=prompt, max_tokens=max_tokens)


# ── 7-day behaviour summary ───────────────────────────────────────────────────
def build_week_summary(logs: list) -> str:
    """
    Summarise last 7 days of logs into a text block for LLaMA context.
    This is ALWAYS included in every insight so the AI is pattern-aware.
    """
    if not logs:
        return "No previous logs this week."

    recent = logs[:7]
    n = len(recent)

    def avg(field):
        vals = [l.get(field) for l in recent if l.get(field) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    # Food patterns
    all_meals = []
    all_herbal = []
    for l in recent:
        meals = l.get("meals") or []
        herbal = l.get("herbal_drinks") or []
        if isinstance(meals, list): all_meals.extend(meals)
        if isinstance(herbal, list): all_herbal.extend(herbal)

    # Caffeine days
    caffeine_words = ["chai", "tea", "coffee", "caffeine"]
    caffeine_days = sum(
        1 for l in recent
        if any(
            any(c in str(f).lower() for c in caffeine_words)
            for f in (l.get("meals") or []) + (l.get("herbal_drinks") or [])
        )
    )

    # Omega-3 logged
    omega3_words = ["flaxseed", "flax", "walnut", "fish", "salmon", "chia"]
    omega3_days = sum(
        1 for l in recent
        if any(
            any(o in str(f).lower() for o in omega3_words)
            for f in (l.get("meals") or [])
        )
    )

    # Exercise days
    ex_days = sum(1 for l in recent if (l.get("exercise_minutes") or 0) > 0)
    ex_types = list(set(l.get("exercise_type") for l in recent if l.get("exercise_type")))

    # High pain days
    pain_vals = [l.get("pain_score") for l in recent if l.get("pain_score") is not None]
    high_pain_days = sum(1 for p in pain_vals if p >= 7)

    # Pain on caffeine vs no caffeine days (simple correlation)
    caff_pain, no_caff_pain = [], []
    for l in recent:
        has_caff = any(
            any(c in str(f).lower() for c in caffeine_words)
            for f in (l.get("meals") or []) + (l.get("herbal_drinks") or [])
        )
        if l.get("pain_score") is not None:
            (caff_pain if has_caff else no_caff_pain).append(l["pain_score"])

    caff_note = ""
    if caff_pain and no_caff_pain:
        diff = round(sum(caff_pain)/len(caff_pain) - sum(no_caff_pain)/len(no_caff_pain), 1)
        if abs(diff) >= 0.8:
            caff_note = f"Pain was {abs(diff)} pts {'higher' if diff > 0 else 'lower'} on caffeine days ({round(sum(caff_pain)/len(caff_pain),1)}/10 vs {round(sum(no_caff_pain)/len(no_caff_pain),1)}/10)."

    # Exercise vs pain correlation
    ex_pain, no_ex_pain = [], []
    for l in recent:
        if l.get("pain_score") is not None:
            (ex_pain if (l.get("exercise_minutes") or 0) > 0 else no_ex_pain).append(l["pain_score"])

    ex_note = ""
    if ex_pain and no_ex_pain:
        diff = round(sum(no_ex_pain)/len(no_ex_pain) - sum(ex_pain)/len(ex_pain), 1)
        if diff >= 0.8:
            ex_note = f"Pain was {diff} pts lower on exercise days ({round(sum(ex_pain)/len(ex_pain),1)}/10 vs {round(sum(no_ex_pain)/len(no_ex_pain),1)}/10)."

    lines = [
        f"LAST {n} DAYS BEHAVIOUR SUMMARY:",
        f"- Avg pain: {avg('pain_score') or 'N/A'}/10  |  Avg mood: {avg('mood_score') or 'N/A'}/10  |  Avg energy: {avg('energy_score') or 'N/A'}/10",
        f"- Avg steps: {avg('steps') or 'N/A'}  |  Avg sleep: {avg('sleep_hours') or 'N/A'} hrs",
        f"- Exercise: {ex_days}/{n} days  |  Types: {', '.join(ex_types) if ex_types else 'none'}",
        f"- Caffeine logged: {caffeine_days}/{n} days",
        f"- Omega-3 sources: {omega3_days}/{n} days {'⚠️ none this week' if omega3_days == 0 else ''}",
        f"- High pain days (≥7/10): {high_pain_days}/{n}",
        f"- Common foods: {', '.join(list(dict.fromkeys(all_meals))[:6]) if all_meals else 'not logged'}",
        f"- Herbal drinks: {', '.join(list(dict.fromkeys(all_herbal))[:4]) if all_herbal else 'none'}",
    ]
    if caff_note: lines.append(f"- Caffeine-pain pattern: {caff_note}")
    if ex_note:   lines.append(f"- Exercise-pain pattern: {ex_note}")

    return "\n".join(lines)


# ── Main intelligence function ────────────────────────────────────────────────
def get_food_and_cycle_insight(
    today_data: dict,
    logs: list,
    cycle_day: Optional[int] = None,
    phase: Optional[str] = None,
) -> str:
    """
    Generate daily WhatsApp insight combining:
    - RAG knowledge (from your ingested PDFs)
    - Web search if RAG confidence is low
    - Today's logged data
    - 7-day behaviour pattern summary

    Returns plain text ready for WhatsApp.
    """
    meals    = today_data.get("meals") or []
    herbal   = today_data.get("herbal_drinks") or []
    exercise = today_data.get("exercise_type", "")
    ex_mins  = today_data.get("exercise_minutes", 0) or 0
    pain     = today_data.get("pain_score")
    energy   = today_data.get("energy_score")
    mood     = today_data.get("mood_score")

    all_foods = meals + herbal
    week_summary = build_week_summary(logs)

    # Build RAG query — use raw_message text if parsed meals list is empty
    raw_msg = today_data.get("raw_message", "")
    if all_foods:
        food_str = ", ".join(all_foods[:6])
    elif raw_msg:
        food_str = raw_msg[:200]  # use raw text so insight is specific
    else:
        food_str = "mixed Indian foods"
    rag_query = f"endometriosis {phase or 'menstrual'} phase diet {food_str} inflammation pain management"
    rag       = _rag_query(rag_query)

    # Web search fallback if RAG confidence is low
    research_context = rag["answer"]
    source_label     = "research"
    if rag["confidence"] < RAG_CONFIDENCE_THRESHOLD or not rag["answer"].strip():
        web = _web_search(f"endometriosis {food_str} anti-inflammatory diet pain")
        if web:
            research_context = web
            source_label     = "web"

    # Exercise RAG if exercise was logged
    ex_context = ""
    if exercise and ex_mins > 0:
        ex_rag = _rag_query(f"endometriosis {phase or ''} phase {exercise} exercise benefits pain")
        if ex_rag["confidence"] >= RAG_CONFIDENCE_THRESHOLD and ex_rag["answer"]:
            ex_context = ex_rag["answer"][:400]
        else:
            ex_context = _web_search(f"endometriosis {exercise} exercise {phase or 'menstrual phase'} pain relief")[:400]

    # Build LLaMA prompt
    system = """You are a warm endometriosis health coach. Give short, specific, actionable daily insights.

STRICT RULES:
- Max 80 words total
- Mention specific foods/drinks by name from the log (never say "unspecified" or "your foods")
- 2 insights only: one food tip, one cycle/pattern tip
- No preamble, no repeating what they ate
- WhatsApp format: plain text, minimal emoji, *bold* key points only
- If foods unclear, give a general endo-friendly tip for their cycle phase"""

    ex_line = f"\nExercise: {exercise} {ex_mins}min" if exercise else ""
    prompt = (
        f"Patient log today:\n"
        f"Foods/drinks: {food_str}\n"
        f"Pain: {pain}/10 | Mood: {mood}/10 | Energy: {energy}/10\n"
        f"Cycle: {phase or 'unknown'} day {cycle_day or '?'}"
        + ex_line +
        f"\n\n{week_summary}\n\n"
        f"Research: {research_context[:400] if research_context else ''}\n\n"
        "Give exactly 2 insights (no headers, no numbering, no repeating food list):\n"
        "First: specific tip about today's foods and endo inflammation\n"
        "Second: cycle-phase tip or weekly pattern observation\n"
        "Start immediately with the first insight."
    )

    insight = _llama(system, prompt, max_tokens=150)

    # Fallback if LLaMA fails
    if not insight:
        lines = []
        if all_foods:
            lines.append(f"🍽️ Logged: {', '.join(all_foods[:4])}")
        if exercise:
            lines.append(f"✅ {exercise.title()} {ex_mins} min — great for {phase or 'your cycle phase'}")
        if phase:
            lines.append(f"🗓️ {phase} — keep logging to build your pattern insights")
        return "\n".join(lines) if lines else ""

    return insight


# ── Nutrition estimation ──────────────────────────────────────────────────────
def estimate_nutrition(meals: list, herbal: list, raw_message: str = "") -> dict:
    """
    Estimate nutrition for logged meals using LLaMA + RAG knowledge of Indian foods.
    Returns calories, protein, carbs, fat, iron, fiber estimates.
    """
    # Use raw_message as fallback if meals list is empty
    if not meals and not herbal:
        if raw_message:
            food_list = raw_message[:400]  # use raw text directly
        else:
            return {}
    else:
        food_list = ", ".join(meals + herbal)

    system = """You are a nutrition expert specialising in Indian foods and endometriosis dietary needs.
Estimate nutrition for the listed foods. Use standard Indian portion sizes:
- 1 roti = 80g (~120 kcal, 3g protein, 24g carbs)
- 1 bowl dal = 200ml (~120 kcal, 8g protein)
- 1 bowl sabji/curry = 200g (varies)
- 1 cup chai = 150ml (~60 kcal with milk and sugar)
- 1 bowl rice = 150g cooked (~195 kcal, 4g protein)

Return ONLY a JSON object, no explanation:
{
  "calories": integer,
  "protein_g": float,
  "carbs_g": float,
  "fat_g": float,
  "fiber_g": float,
  "iron_mg": float,
  "calcium_mg": float,
  "omega3_g": float,
  "notes": "brief note about endo-relevant nutrients"
}

If a food is unknown, estimate conservatively. Always return valid JSON."""

    prompt = f"Estimate nutrition for an Indian woman with endometriosis who ate: {food_list}\n\nReturn JSON only."

    def _try_parse(raw_text):
        if not raw_text:
            return None
        try:
            import re as _re, json as _j
            clean = _re.sub(r'```json|```', '', raw_text).strip()
            # Find the opening brace
            start_i = clean.find('{')
            if start_i == -1:
                return None
            clean = clean[start_i:]
            # Count only complete key-value pairs and rebuild JSON
            # Extract all complete "key": value pairs
            pairs = _re.findall(
                r'"(\w+)"\s*:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|"[^"]*"|true|false|null)',
                clean
            )
            if not pairs:
                return None
            # Rebuild clean JSON from only complete pairs
            obj = {}
            for k, v in pairs:
                try:
                    obj[k] = _j.loads(v)
                except Exception:
                    obj[k] = v
            if not obj.get("calories"):
                return None
            validated = NutritionEstimate(**obj)
            result = {k: v for k, v in validated.model_dump().items() if v is not None}
            return result if result.get("calories") else None
        except Exception as ex:
            import logging as _log2
            _log2.getLogger("knowledge_engine").warning(
                f"[NUTRITION] parse failed: {ex} | raw: {str(raw_text)[:80]}"
            )
            return None


    # Attempt 1
    raw = _llama(system, prompt, max_tokens=200)
    result = _try_parse(raw) if raw else None

    # Attempt 2 — re-prompt if failed
    if result is None:
        retry_prompt = "Give ONLY a JSON object for: " + food_list + ". Keys: calories(int), protein_g, carbs_g, fat_g, fiber_g, iron_mg(float). No extra text."
        raw2 = _llama(system, retry_prompt, max_tokens=200)
        result = _try_parse(raw2) if raw2 else None

    # Attempt 3 — plain JSON parse without Pydantic as last resort
    if result is None and raw:
        try:
            clean = re.sub(r"```json|```", "", raw).strip()
            m = re.search(r'[{].*[}]', clean, re.DOTALL)
            if m:
                parsed = _json.loads(m.group(0))
                if parsed.get("calories"):
                    result = {
                        "calories":  int(parsed.get("calories", 0)),
                        "protein_g": float(parsed.get("protein_g", 0)),
                        "carbs_g":   float(parsed.get("carbs_g", 0)),
                        "fat_g":     float(parsed.get("fat_g", 0)),
                        "fiber_g":   float(parsed.get("fiber_g", 0)),
                        "iron_mg":   float(parsed.get("iron_mg", 0)),
                        "notes":     str(parsed.get("notes", "")),
                    }
        except Exception:
            pass

    return result or {}



# ── Weekly report context ─────────────────────────────────────────────────────
def get_weekly_rag_context(phase: str, top_issues: list) -> str:
    """
    Get RAG context for weekly report — queries multiple topics,
    uses web fallback for any with low confidence.
    """
    topics = [
        f"endometriosis {phase} diet exercise recommendations",
        f"endometriosis anti-inflammatory foods weekly plan",
    ]
    if "caffeine" in " ".join(top_issues).lower():
        topics.append("caffeine endometriosis pain inflammation")
    if "omega" in " ".join(top_issues).lower():
        topics.append("omega-3 endometriosis pain prostaglandins")

    contexts = []
    for topic in topics[:3]:
        rag = _rag_query(topic)
        if rag["confidence"] >= RAG_CONFIDENCE_THRESHOLD and rag["answer"]:
            contexts.append(rag["answer"][:400])
        else:
            web = _web_search(topic)
            if web:
                contexts.append(web[:300])

    return "\n\n---\n".join(contexts)
