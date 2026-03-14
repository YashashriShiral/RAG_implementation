"""
app/daily_log_db.py
────────────────────────────────────────────────────────────────────────────
Daily health log — SQLite storage with smart merge + nutrition columns.

Merge rules:
  Lists  → append + deduplicate
  Scores → average morning + evening
  Steps  → keep higher
  Meditation/exercise_minutes → add together
  Sleep / cycle / period → latest non-null wins
  Notes / raw_message → concatenate with " | "
"""

import sqlite3, json, os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH    = Path(os.getenv("HEALTH_DB_PATH", str(_REPO_ROOT / "data" / "health_tracker.db")))

LIST_FIELDS  = ["meals", "pain_locations", "herbal_drinks", "medicines"]
SCORE_FIELDS = ["pain_score", "mood_score", "energy_score"]


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_daily_log_table():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_log (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date            TEXT NOT NULL UNIQUE,
                steps               INTEGER,
                meals               TEXT,
                mood_score          REAL,
                energy_score        REAL,
                pain_score          REAL,
                pain_locations      TEXT,
                on_period           INTEGER DEFAULT 0,
                cycle_day           INTEGER,
                herbal_drinks       TEXT,
                medicines           TEXT,
                meditation_minutes  INTEGER,
                sleep_hours         REAL,
                exercise_type       TEXT,
                exercise_minutes    INTEGER,
                exercise_intensity  TEXT,
                notes               TEXT,
                raw_message         TEXT,
                -- Nutrition columns (estimated by knowledge_engine)
                nutrition_calories  REAL,
                nutrition_protein_g REAL,
                nutrition_carbs_g   REAL,
                nutrition_fat_g     REAL,
                nutrition_fiber_g   REAL,
                nutrition_iron_mg   REAL,
                created_at          TEXT DEFAULT (datetime('now')),
                updated_at          TEXT DEFAULT (datetime('now'))
            )
        """)
        # Add nutrition columns if upgrading existing DB (safe to run multiple times)
        for col, typ in [
            ("nutrition_calories",  "REAL"),
            ("nutrition_protein_g", "REAL"),
            ("nutrition_carbs_g",   "REAL"),
            ("nutrition_fat_g",     "REAL"),
            ("nutrition_fiber_g",   "REAL"),
            ("nutrition_iron_mg",   "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE daily_log ADD COLUMN {col} {typ}")
            except Exception:
                pass  # column already exists
    print(f"health_tracker.db ready at {DB_PATH}")


def _pack(v):
    return json.dumps(v) if isinstance(v, list) else v


def _unpack(row: dict) -> dict:
    for f in LIST_FIELDS:
        raw = row.get(f)
        if isinstance(raw, str) and raw:
            try:    row[f] = json.loads(raw)
            except: row[f] = [raw]
        elif raw is None:
            row[f] = []
    return row


def _merge_lists(old: list, new: list) -> list:
    seen, combined = set(), []
    for item in (old or []) + (new or []):
        k = str(item).strip().lower()
        if k and k not in seen:
            seen.add(k)
            combined.append(str(item).strip())
    return combined


def upsert_daily_log(data: dict) -> dict:
    data = dict(data)
    data.setdefault("log_date", str(date.today()))

    # Store nutrition dict as flat columns if present
    nutrition = data.pop("nutrition", None) or {}
    if nutrition:
        data.setdefault("nutrition_calories",  nutrition.get("calories"))
        data.setdefault("nutrition_protein_g", nutrition.get("protein_g"))
        data.setdefault("nutrition_carbs_g",   nutrition.get("carbs_g"))
        data.setdefault("nutrition_fat_g",     nutrition.get("fat_g"))
        data.setdefault("nutrition_fiber_g",   nutrition.get("fiber_g"))
        data.setdefault("nutrition_iron_mg",   nutrition.get("iron_mg"))

    # Remove None nutrition fields so they don't overwrite good data
    for nk in ["nutrition_calories","nutrition_protein_g","nutrition_carbs_g",
               "nutrition_fat_g","nutrition_fiber_g","nutrition_iron_mg"]:
        if data.get(nk) is None:
            data.pop(nk, None)

    with _conn() as conn:
        existing_row = conn.execute(
            "SELECT * FROM daily_log WHERE log_date=?", (data["log_date"],)
        ).fetchone()

        if not existing_row:
            for f in LIST_FIELDS:
                if f in data:
                    data[f] = _pack(data[f])
            # Only keep columns that exist in DB
            valid_cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_log)")}
            data = {k: v for k, v in data.items() if k in valid_cols}
            cols = ", ".join(data.keys())
            phs  = ", ".join("?" * len(data))
            conn.execute(f"INSERT INTO daily_log ({cols}) VALUES ({phs})", list(data.values()))
            action = "logged"

        else:
            existing = _unpack(dict(existing_row))
            merged   = dict(existing)

            for key, new_val in data.items():
                if key in ("id", "log_date", "created_at", "updated_at"):
                    continue
                old_val = existing.get(key)

                if key in LIST_FIELDS:
                    new_list = new_val if isinstance(new_val, list) else []
                    merged[key] = _merge_lists(old_val, new_list)

                elif key in SCORE_FIELDS:
                    if new_val is not None and old_val is not None:
                        merged[key] = round((float(old_val) + float(new_val)) / 2, 1)
                    elif new_val is not None:
                        merged[key] = new_val

                elif key == "steps":
                    if new_val is not None and old_val is not None:
                        merged[key] = max(int(old_val), int(new_val))
                    elif new_val is not None:
                        merged[key] = new_val

                elif key in ("meditation_minutes", "exercise_minutes"):
                    if new_val is not None and old_val is not None:
                        merged[key] = int(old_val) + int(new_val)
                    elif new_val is not None:
                        merged[key] = new_val

                elif key in ("notes", "raw_message"):
                    if new_val and old_val:
                        merged[key] = f"{old_val} | {new_val}"
                    elif new_val:
                        merged[key] = new_val

                else:
                    # nutrition columns, sleep, period etc → latest non-null wins
                    if new_val is not None:
                        merged[key] = new_val

            for f in LIST_FIELDS:
                if f in merged:
                    merged[f] = _pack(merged[f])

            update_data = {k: v for k, v in merged.items()
                           if k not in ("id", "log_date", "created_at")}
            sql = (
                "UPDATE daily_log SET "
                + ", ".join(f"{k}=?" for k in update_data)
                + ", updated_at=datetime('now') WHERE log_date=?"
            )
            conn.execute(sql, list(update_data.values()) + [data["log_date"]])
            action = "merged"

        row = conn.execute(
            "SELECT * FROM daily_log WHERE log_date=?", (data["log_date"],)
        ).fetchone()

    return {"action": action, "record": _unpack(dict(row))}


def get_logs(days: int = 30, end_date: Optional[str] = None) -> list:
    end   = end_date or str(date.today())
    start = str(date.fromisoformat(end) - timedelta(days=days))
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_log WHERE log_date BETWEEN ? AND ? ORDER BY log_date DESC",
            (start, end),
        ).fetchall()
    return [_unpack(dict(r)) for r in rows]


def get_weekly_summary(week_offset: int = 0) -> dict:
    today      = date.today()
    week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
    week_end   = week_start + timedelta(days=6)

    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_log WHERE log_date BETWEEN ? AND ? ORDER BY log_date",
            (str(week_start), str(min(week_end, today))),
        ).fetchall()

    logs = [_unpack(dict(r)) for r in rows]
    if not logs:
        return {"week_start": str(week_start), "week_end": str(week_end), "days_logged": 0}

    def avg(field):
        vals = [l[field] for l in logs if l.get(field) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    medicines, drinks, meals, period_days = [], [], [], []
    for l in logs:
        medicines.extend(l.get("medicines") or [])
        drinks.extend(l.get("herbal_drinks") or [])
        meals.extend(l.get("meals") or [])
        if l.get("on_period"):
            period_days.append(l["log_date"])

    return {
        "week_start":             str(week_start),
        "week_end":               str(week_end),
        "days_logged":            len(logs),
        "avg_pain":               avg("pain_score"),
        "avg_mood":               avg("mood_score"),
        "avg_energy":             avg("energy_score"),
        "avg_steps":              avg("steps"),
        "avg_sleep_hours":        avg("sleep_hours"),
        "avg_meditation_minutes": avg("meditation_minutes"),
        "avg_exercise_minutes":   avg("exercise_minutes"),
        "meditation_days":        len([l for l in logs if (l.get("meditation_minutes") or 0) > 0]),
        "exercise_days":          len([l for l in logs if (l.get("exercise_minutes") or 0) > 0]),
        "exercise_types":         list(set(l.get("exercise_type") for l in logs if l.get("exercise_type"))),
        "period_days":            period_days,
        "high_pain_days":         [l["log_date"] for l in logs if (l.get("pain_score") or 0) >= 7],
        "medicines":              list(set(medicines)),
        "herbal_drinks":          list(set(drinks)),
        "meals_sample":           meals[:10],
        # Nutrition averages
        "avg_calories":           avg("nutrition_calories"),
        "avg_protein_g":          avg("nutrition_protein_g"),
        "avg_fiber_g":            avg("nutrition_fiber_g"),
        "avg_iron_mg":            avg("nutrition_iron_mg"),
    }


# ── Insight log table ─────────────────────────────────────────────────────────
def init_insight_log_table():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS insight_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date     TEXT NOT NULL,
                user_message TEXT,
                ai_reply     TEXT,
                insight_type TEXT DEFAULT 'daily',  -- 'daily' | 'weekly' | 'summary'
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)


def save_insight(log_date: str, user_message: str, ai_reply: str, insight_type: str = "daily"):
    init_insight_log_table()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO insight_log (log_date, user_message, ai_reply, insight_type) VALUES (?,?,?,?)",
            (log_date, user_message, ai_reply, insight_type)
        )


def get_insights(days: int = 30) -> list:
    init_insight_log_table()
    start = str(date.today() - timedelta(days=days))
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM insight_log WHERE log_date >= ? ORDER BY created_at DESC",
            (start,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_log(log_date: str) -> bool:
    """Delete a log entry from ALL tables — daily_log, insight_log, parse_log."""
    import sqlite3 as _sq
    conn = _sq.connect(str(DB_PATH), isolation_level=None)  # autocommit
    try:
        conn.execute("DELETE FROM daily_log   WHERE log_date = ?", (log_date,))
        conn.execute("DELETE FROM insight_log WHERE log_date = ?", (log_date,))
        conn.execute("DELETE FROM parse_log   WHERE log_date = ?", (log_date,))
        return True
    finally:
        conn.close()


# ── Parse Quality Log ─────────────────────────────────────────────────────────
def init_parse_log_table():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parse_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date        TEXT NOT NULL,
                raw_message     TEXT,
                parse_source    TEXT,  -- 'llama_attempt1' | 'llama_attempt2' | 'regex_fallback'
                success         INTEGER DEFAULT 1,
                fields_extracted INTEGER DEFAULT 0,
                fields_total    INTEGER DEFAULT 17,
                pain_score      REAL,
                mood_score      REAL,
                energy_score    REAL,
                steps           INTEGER,
                meals_count     INTEGER DEFAULT 0,
                validation_errors TEXT,  -- JSON list of field errors
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)


def save_parse_log(
    log_date: str,
    raw_message: str,
    parse_source: str,
    data: dict,
    validation_errors: list = None,
):
    init_parse_log_table()
    core_fields = [
        "pain_score","mood_score","energy_score","steps","sleep_hours",
        "meditation_minutes","exercise_type","exercise_minutes","on_period",
        "cycle_day","meals","herbal_drinks","medicines","notes",
        "nutrition_calories","nutrition_protein_g","nutrition_iron_mg"
    ]
    extracted = sum(1 for f in core_fields if data.get(f) is not None)
    import json as _j
    with _conn() as conn:
        conn.execute("""
            INSERT INTO parse_log
              (log_date, raw_message, parse_source, fields_extracted, fields_total,
               pain_score, mood_score, energy_score, steps, meals_count, validation_errors)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            log_date,
            raw_message[:500],
            parse_source,
            extracted,
            len(core_fields),
            data.get("pain_score"),
            data.get("mood_score"),
            data.get("energy_score"),
            data.get("steps"),
            len(data.get("meals") or []),
            _j.dumps(validation_errors or []),
        ))


def update_nutrition(log_date: str, nutrition: dict) -> bool:
    """Directly update nutrition columns — uses autocommit connection."""
    if not nutrition.get("calories"):
        return False
    import sqlite3 as _sq
    conn = _sq.connect(str(DB_PATH), isolation_level=None)  # autocommit
    try:
        conn.execute("""
            UPDATE daily_log SET
                nutrition_calories  = ?,
                nutrition_protein_g = ?,
                nutrition_carbs_g   = ?,
                nutrition_fat_g     = ?,
                nutrition_fiber_g   = ?,
                nutrition_iron_mg   = ?
            WHERE log_date = ?
        """, (
            nutrition.get("calories"),
            nutrition.get("protein_g"),
            nutrition.get("carbs_g"),
            nutrition.get("fat_g"),
            nutrition.get("fiber_g"),
            nutrition.get("iron_mg"),
            log_date,
        ))
        return True
    finally:
        conn.close()


def get_parse_logs(days: int = 30) -> list:
    init_parse_log_table()
    start = str(date.today() - timedelta(days=days))
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM parse_log WHERE log_date >= ? ORDER BY created_at DESC",
            (start,)
        ).fetchall()
    return [dict(r) for r in rows]
