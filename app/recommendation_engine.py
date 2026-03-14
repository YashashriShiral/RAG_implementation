"""
app/recommendation_engine.py
────────────────────────────────────────────────────────────────────────────
Weekly AI report — RAG + web fallback + 7-day behaviour context.
No hardcoded food or cycle advice. Everything from knowledge_engine.
"""

import requests, os
from datetime import date
from typing import Optional

from app.knowledge_engine import build_week_summary, get_weekly_rag_context, _llama
from app.cycle_intelligence import get_cycle_context

USER_NAME = os.getenv("USER_NAME", "Yashashri")

WEEKLY_SYSTEM = """You are a compassionate endometriosis health coach.
You generate personalised weekly WhatsApp check-ins grounded in research and the user's own data.

FORMAT (use *bold* for WhatsApp):
🌿 *Weekly Check-in* — [date range]

✨ *What went well:*
[2-3 specific positives using their actual numbers]

🗓️ *Cycle phase this week:*
[Name phase. If symptoms MISMATCH expected — say so explicitly with numbers.]

⚠️ *Patterns from YOUR data:*
[Reference actual correlations from their 7-day summary — caffeine vs pain, exercise vs pain etc.
Must use their real numbers. Never be generic.]

🍽️ *Nutrition gaps:*
[What's missing — omega-3, iron, fiber — based on what they actually logged]

📋 *3 focus areas next week:*
1. [Exercise — specific type + duration matched to upcoming cycle phase]
2. [Food swap — specific, e.g. "swap morning chai for ginger tea 3 days"]
3. [Ayurvedic or supplement suggestion grounded in research]

💜 [One warm closing line about their cycle phase]
_Reply log · summary · weekly · help_

Rules:
- Every point must reference their actual data (numbers, food names, exercise logged)
- Never write advice that could apply to anyone — it must be specific to them
- Keep under 350 words total
- Ground all advice in the research context provided"""


def generate_weekly_report(this_week: dict, last_week: Optional[dict] = None,
                           logs: list = None) -> str:

    logs = logs or []

    # ── 7-day behaviour summary ───────────────────────────────────────────────
    week_summary = build_week_summary(logs)

    # ── Cycle context ─────────────────────────────────────────────────────────
    try:
        from app.daily_log_db import get_logs as _get_logs
        all_logs = _get_logs(days=180)
    except Exception:
        all_logs = []

    cycle_ctx  = get_cycle_context(all_logs)
    phase      = cycle_ctx.get("phase", "unknown")
    phase_emoji = cycle_ctx.get("phase_emoji", "🌿")
    mismatches = cycle_ctx.get("mismatches", [])
    cycle_day  = cycle_ctx.get("cycle_day", "?")
    next_period = cycle_ctx.get("next_period", "unknown")

    # ── Identify top issues for targeted RAG queries ──────────────────────────
    top_issues = []
    if week_summary:
        if "caffeine" in week_summary.lower(): top_issues.append("caffeine")
        if "omega" in week_summary.lower() or "0/" in week_summary: top_issues.append("omega-3 deficiency")
        if "high pain" in week_summary.lower(): top_issues.append("pain management")
        if "0 days" in week_summary.lower() and "exercise" in week_summary.lower():
            top_issues.append("exercise")

    # ── RAG + web context ─────────────────────────────────────────────────────
    research = get_weekly_rag_context(phase, top_issues)

    # ── Week comparison ───────────────────────────────────────────────────────
    comparison = ""
    if last_week and last_week.get("days_logged", 0) > 0:
        def chg(key, lower_better=False):
            c, p = this_week.get(key), last_week.get(key)
            if c is None or p is None: return ""
            d = round(c - p, 1)
            if d == 0: return "same"
            better = (d < 0) == lower_better
            return f"{'↓' if d<0 else '↑'}{abs(d)} ({'better ✅' if better else 'worse ⚠️'})"

        comparison = f"""Week-over-week:
Pain: {last_week.get('avg_pain')}→{this_week.get('avg_pain')} {chg('avg_pain', True)}
Mood: {last_week.get('avg_mood')}→{this_week.get('avg_mood')} {chg('avg_mood')}
Energy: {last_week.get('avg_energy')}→{this_week.get('avg_energy')} {chg('avg_energy')}
Steps: {last_week.get('avg_steps')}→{this_week.get('avg_steps')} {chg('avg_steps')}"""

    # ── Mismatch text ─────────────────────────────────────────────────────────
    mismatch_text = "\n".join(f"- {m}" for m in mismatches) \
                    if mismatches else "Symptoms align with expected phase"

    # ── Full prompt ───────────────────────────────────────────────────────────
    user_data = f"""
User: {USER_NAME}
Week: {this_week.get('week_start')} to {this_week.get('week_end')}
Days logged: {this_week.get('days_logged')}/7
Next period expected: {next_period}

HEALTH AVERAGES THIS WEEK:
- Pain:       {this_week.get('avg_pain','N/A')}/10
- Mood:       {this_week.get('avg_mood','N/A')}/10
- Energy:     {this_week.get('avg_energy','N/A')}/10
- Steps/day:  {this_week.get('avg_steps','N/A')}
- Sleep:      {this_week.get('avg_sleep_hours','N/A')} hrs/night
- Meditation: {this_week.get('avg_meditation_minutes','N/A')} min avg, {this_week.get('meditation_days',0)} days
- Exercise:   {this_week.get('avg_exercise_minutes','N/A')} min avg, {this_week.get('exercise_days',0)} days
- Exercise types: {', '.join(this_week.get('exercise_types',[]) or []) or 'none'}
- Medicines:  {', '.join(this_week.get('medicines',[]) or []) or 'none'}

{week_summary}

CYCLE CONTEXT:
- Current phase: {phase_emoji} {phase} (day {cycle_day})
- Symptom mismatches vs expected:
{mismatch_text}

{comparison}

RESEARCH CONTEXT (from knowledge base):
{research[:800] if research else 'No research context retrieved'}
"""

    result = _llama(WEEKLY_SYSTEM, f"Generate weekly check-in:\n{user_data}", max_tokens=500)

    if not result:
        # Clean fallback
        return (
            f"{phase_emoji} *Weekly Check-in* — {this_week.get('week_start')} to {this_week.get('week_end')}\n\n"
            f"🗓️ *{phase}* (day {cycle_day})\n\n"
            f"📊 Pain {this_week.get('avg_pain','—')}/10 · Mood {this_week.get('avg_mood','—')}/10 · "
            f"Steps {this_week.get('avg_steps','—')}/day\n\n"
            + ("\n".join(f"⚠️ {m}" for m in mismatches) + "\n\n" if mismatches else "")
            + "_Reply *log* to track today_"
        )

    return result


def build_quick_summary(logs: list) -> str:
    if not logs:
        return (
            "📊 No logs yet!\n\nStart logging:\n"
            "_Steps 6000, ate dal rice, feeling 6/10, period day 1, ginger tea, 20 min yoga_\n\n"
            "Reply *help* for all options 💜"
        )

    recent = logs[:7]
    n = len(recent)

    def safe_avg(field):
        vals = [l.get(field) for l in recent if l.get(field) is not None]
        return round(sum(vals)/len(vals), 1) if vals else None

    avg_pain  = safe_avg("pain_score")
    avg_mood  = safe_avg("mood_score")
    avg_steps = safe_avg("steps")
    pain_em   = "🟢" if (avg_pain or 0) <= 3 else ("🟡" if (avg_pain or 0) <= 6 else "🔴")

    # Pull one key pattern from week summary
    week_summary = build_week_summary(recent)
    pattern_line = ""
    for line in week_summary.split("\n"):
        if "pain pattern" in line.lower() or "caffeine" in line.lower():
            pattern_line = f"\n💡 {line.strip()}"
            break

    return (
        f"📊 *Your Last {n} Days*\n\n"
        f"{pain_em} Avg Pain:  {avg_pain or '—'}/10\n"
        f"😊 Avg Mood:  {avg_mood or '—'}/10\n"
        f"👣 Avg Steps: {f'{avg_steps:,.0f}' if avg_steps else '—'}"
        f"{pattern_line}\n\n"
        "_Reply *weekly* for full AI report_"
    )
