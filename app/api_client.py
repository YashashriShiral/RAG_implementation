"""
app/api_client.py
─────────────────────────────────────────────────────────────────────────────
Drop-in replacement for daily_log_db.py when running on Railway.

If API_BASE_URL points to a remote FastAPI (different container),
all DB calls go via HTTP. If API_BASE_URL is localhost, falls back
to importing daily_log_db directly (local dev mode).

Usage in Streamlit pages — replace:
    from app.daily_log_db import get_logs, upsert_daily_log, ...
With:
    from app.api_client import get_logs, upsert_daily_log, ...
"""

import os
import requests
from typing import Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
_IS_LOCAL = "localhost" in API_BASE_URL or "127.0.0.1" in API_BASE_URL

TIMEOUT = 15


def _use_local():
    """Use direct DB imports for local dev."""
    return _IS_LOCAL


# ── get_logs ──────────────────────────────────────────────────────────────────
def get_logs(days: int = 30, end_date: Optional[str] = None) -> list:
    if _use_local():
        from app.daily_log_db import get_logs as _f
        return _f(days=days, end_date=end_date)
    try:
        params = {"days": days}
        if end_date:
            params["end_date"] = end_date
        r = requests.get(f"{API_BASE_URL}/logs", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("logs", [])
    except Exception as e:
        print(f"[api_client] get_logs failed: {e}")
        return []


# ── get_weekly_summary ────────────────────────────────────────────────────────
def get_weekly_summary(week_offset: int = 0) -> dict:
    if _use_local():
        from app.daily_log_db import get_weekly_summary as _f
        return _f(week_offset=week_offset)
    try:
        r = requests.get(f"{API_BASE_URL}/logs/weekly",
                         params={"week_offset": week_offset}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[api_client] get_weekly_summary failed: {e}")
        return {}


# ── get_insights ──────────────────────────────────────────────────────────────
def get_insights(days: int = 30) -> list:
    if _use_local():
        from app.daily_log_db import get_insights as _f
        return _f(days=days)
    try:
        r = requests.get(f"{API_BASE_URL}/logs/insights",
                         params={"days": days}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("insights", [])
    except Exception as e:
        print(f"[api_client] get_insights failed: {e}")
        return []


# ── get_parse_logs ────────────────────────────────────────────────────────────
def get_parse_logs(days: int = 30) -> list:
    if _use_local():
        from app.daily_log_db import get_parse_logs as _f
        return _f(days=days)
    try:
        r = requests.get(f"{API_BASE_URL}/logs/parse",
                         params={"days": days}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("parse_logs", [])
    except Exception as e:
        print(f"[api_client] get_parse_logs failed: {e}")
        return []


# ── upsert_daily_log ──────────────────────────────────────────────────────────
def upsert_daily_log(data: dict) -> dict:
    if _use_local():
        from app.daily_log_db import upsert_daily_log as _f
        return _f(data)
    try:
        r = requests.post(f"{API_BASE_URL}/logs/upsert",
                          json=data, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("result", {})
    except Exception as e:
        print(f"[api_client] upsert_daily_log failed: {e}")
        return {}


# ── delete_log ────────────────────────────────────────────────────────────────
def delete_log(log_date: str) -> bool:
    if _use_local():
        from app.daily_log_db import delete_log as _f
        return _f(log_date)
    try:
        r = requests.delete(f"{API_BASE_URL}/logs/{log_date}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("status") == "ok"
    except Exception as e:
        print(f"[api_client] delete_log failed: {e}")
        return False


# ── init stubs (no-ops when using API) ───────────────────────────────────────
def init_daily_log_table():
    if _use_local():
        from app.daily_log_db import init_daily_log_table as _f
        _f()

def init_parse_log_table():
    if _use_local():
        from app.daily_log_db import init_parse_log_table as _f
        _f()

def init_insight_log_table():
    if _use_local():
        from app.daily_log_db import init_insight_log_table as _f
        _f()
