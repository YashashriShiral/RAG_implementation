"""
app/cycle_intelligence.py
────────────────────────────────────────────────────────────────────────────
SIMPLIFIED — only keeps cycle day → phase mapping.
All advice and recommendations now come from knowledge_engine (RAG + LLaMA).
No hardcoded advice strings.
"""

from datetime import date, timedelta
from typing import Optional


# ── Phase day ranges — the ONLY thing still hardcoded (biological fact) ───────
PHASE_MAP = [
    ("menstrual",     range(1, 8),   "Menstrual phase",         "🩸"),
    ("post_menstrual",range(8, 12),  "Early follicular phase",  "🌱"),
    ("ovulatory",     range(12, 17), "Ovulatory phase",         "🥚"),
    ("luteal",        range(17, 26), "Luteal phase",            "🌙"),
    ("pms",           range(26, 35), "PMS / late luteal phase", "⚠️"),
]

# Expected symptom ranges per phase — used for mismatch detection only
PHASE_EXPECTED = {
    "menstrual":      {"energy": (1, 4), "mood": (2, 6), "pain": (5, 10)},
    "post_menstrual": {"energy": (4, 7), "mood": (5, 8), "pain": (1, 4)},
    "ovulatory":      {"energy": (7, 10),"mood": (7, 10),"pain": (1, 3)},
    "luteal":         {"energy": (4, 7), "mood": (4, 7), "pain": (3, 6)},
    "pms":            {"energy": (1, 5), "mood": (1, 5), "pain": (4, 9)},
}


def get_phase(cycle_day: int) -> dict:
    """Return phase info for a given cycle day."""
    cd = min(max(cycle_day, 1), 34)
    for key, days, label, emoji in PHASE_MAP:
        if cd in days:
            return {"key": key, "label": label, "emoji": emoji,
                    "expected": PHASE_EXPECTED[key]}
    return {"key": "luteal", "label": "Luteal phase", "emoji": "🌙",
            "expected": PHASE_EXPECTED["luteal"]}


def detect_mismatches(logs: list, cycle_day: int) -> list:
    """
    Detect when actual symptoms don't match expected phase symptoms.
    Returns list of mismatch strings for LLaMA to elaborate on.
    """
    if not logs or not cycle_day:
        return []

    phase    = get_phase(cycle_day)
    expected = phase["expected"]
    recent   = logs[:3]

    def avg(field):
        vals = [l.get(field) for l in recent if l.get(field) is not None]
        return round(sum(vals)/len(vals), 1) if vals else None

    mismatches = []
    avg_energy = avg("energy_score")
    avg_mood   = avg("mood_score")
    avg_pain   = avg("pain_score")

    # Check each metric against expected range
    for metric, actual, label in [
        ("energy", avg_energy, "energy"),
        ("mood",   avg_mood,   "mood"),
        ("pain",   avg_pain,   "pain"),
    ]:
        if actual is None:
            continue
        lo, hi = expected[metric]
        if actual < lo:
            mismatches.append(
                f"{label} is {actual}/10 — lower than expected for {phase['label']} ({lo}–{hi}/10)"
            )
        elif actual > hi:
            mismatches.append(
                f"{label} is {actual}/10 — higher than expected for {phase['label']} ({lo}–{hi}/10)"
            )

    return mismatches


def get_cycle_context(all_logs: list) -> dict:
    """
    Calculate cycle position from period logs.
    Returns minimal context dict for knowledge_engine and recommendation_engine.
    """
    if not all_logs:
        return {"phase": "unknown", "cycle_day": None, "mismatches": []}

    import pandas as pd
    try:
        adf = pd.DataFrame(all_logs)
        adf["log_date"] = pd.to_datetime(adf["log_date"])

        if "on_period" not in adf.columns:
            return {"phase": "unknown", "cycle_day": None, "mismatches": []}

        period_dates = sorted(
            adf[adf["on_period"] == 1]["log_date"].dt.date.tolist()
        )
        if not period_dates:
            return {"phase": "unknown", "cycle_day": None, "mismatches": []}

        # Find cycle start dates
        starts = [period_dates[0]]
        for d in period_dates[1:]:
            if (d - starts[-1]).days > 2:
                starts.append(d)

        last_start  = starts[-1]
        lengths     = [(starts[i+1] - starts[i]).days for i in range(len(starts)-1)]
        avg_cycle   = round(sum(lengths)/len(lengths)) if lengths else 28
        cycle_day   = (date.today() - last_start).days + 1
        next_period = last_start + timedelta(days=avg_cycle)

        phase_info  = get_phase(min(cycle_day, 34))
        mismatches  = detect_mismatches(all_logs[:7], cycle_day)

        return {
            "cycle_day":   cycle_day,
            "avg_cycle":   avg_cycle,
            "last_start":  str(last_start),
            "next_period": str(next_period),
            "phase":       phase_info["label"],
            "phase_key":   phase_info["key"],
            "phase_emoji": phase_info["emoji"],
            "expected":    phase_info["expected"],
            "mismatches":  mismatches,
            "starts":      [str(s) for s in starts],
        }
    except Exception:
        return {"phase": "unknown", "cycle_day": None, "mismatches": []}
