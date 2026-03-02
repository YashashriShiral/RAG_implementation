"""
app/monitor_db.py
─────────────────────────────────────────────────────────────────────────────
Lightweight SQLite-based monitoring — no external services needed.

Tracks:
  - Every query (question, answer, timestamp, session)
  - Token usage (estimated from char count)
  - Latency (retrieval + LLM generation)
  - Confidence scores
  - Sources cited per query
  - User feedback (thumbs up/down)
  - Errors

All data stored in ./data/monitoring.db (SQLite file, auto-created)
"""

import sqlite3
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from loguru import logger

DB_PATH = Path("./data/monitoring.db")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS queries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT,
            question      TEXT,
            answer        TEXT,
            confidence    REAL DEFAULT 0,
            docs_retrieved INTEGER DEFAULT 0,
            sources_cited  INTEGER DEFAULT 0,
            retrieval_ms  INTEGER DEFAULT 0,
            llm_ms        INTEGER DEFAULT 0,
            total_ms      INTEGER DEFAULT 0,
            input_tokens  INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens  INTEGER DEFAULT 0,
            model         TEXT,
            error         TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            query_id   INTEGER,
            score      REAL,
            comment    TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
    logger.info("Monitoring DB initialized")


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~4 chars per token (standard approximation).
    Good enough for monitoring without needing a tokenizer.
    """
    return max(1, len(text) // 4)


def log_query(
    session_id: str,
    question: str,
    answer: str,
    confidence: float,
    docs_retrieved: int,
    sources_cited: int,
    retrieval_ms: int,
    llm_ms: int,
    model: str,
    error: Optional[str] = None,
) -> int:
    """Log a query to the database. Returns the inserted row ID."""
    total_ms = retrieval_ms + llm_ms
    input_tokens = estimate_tokens(question)
    output_tokens = estimate_tokens(answer)
    total_tokens = input_tokens + output_tokens

    with get_conn() as conn:
        cursor = conn.execute("""
            INSERT INTO queries (
                session_id, question, answer, confidence,
                docs_retrieved, sources_cited,
                retrieval_ms, llm_ms, total_ms,
                input_tokens, output_tokens, total_tokens,
                model, error
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            session_id, question, answer, confidence,
            docs_retrieved, sources_cited,
            retrieval_ms, llm_ms, total_ms,
            input_tokens, output_tokens, total_tokens,
            model, error,
        ))
        return cursor.lastrowid


def log_feedback(session_id: str, score: float, comment: str = ""):
    """Log user feedback."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO feedback (session_id, score, comment)
            VALUES (?,?,?)
        """, (session_id, score, comment))


def get_stats() -> dict:
    """Aggregate stats for the monitoring dashboard."""
    with get_conn() as conn:
        # Overall stats
        row = conn.execute("""
            SELECT
                COUNT(*)                          AS total_queries,
                ROUND(AVG(confidence)*100, 1)     AS avg_confidence_pct,
                ROUND(AVG(total_ms)/1000.0, 2)   AS avg_latency_sec,
                ROUND(AVG(llm_ms)/1000.0, 2)     AS avg_llm_sec,
                ROUND(AVG(retrieval_ms)/1000.0,2) AS avg_retrieval_sec,
                SUM(total_tokens)                 AS total_tokens,
                ROUND(AVG(total_tokens), 0)       AS avg_tokens_per_query,
                ROUND(AVG(sources_cited), 1)      AS avg_sources_cited,
                COUNT(CASE WHEN error IS NOT NULL THEN 1 END) AS error_count
            FROM queries
        """).fetchone()

        # Feedback stats
        fb = conn.execute("""
            SELECT
                COUNT(*)                    AS total_feedback,
                ROUND(AVG(score)*100, 1)    AS positive_pct
            FROM feedback
        """).fetchone()

        # Queries per day (last 7 days)
        daily = conn.execute("""
            SELECT
                DATE(created_at) AS day,
                COUNT(*)         AS count,
                ROUND(AVG(total_ms)/1000.0, 2) AS avg_latency
            FROM queries
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """).fetchall()

        # Recent queries
        recent = conn.execute("""
            SELECT
                id, session_id, question, confidence,
                total_ms, total_tokens, sources_cited,
                error, created_at
            FROM queries
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()

        # Token usage per day
        token_daily = conn.execute("""
            SELECT
                DATE(created_at) AS day,
                SUM(total_tokens) AS tokens,
                SUM(input_tokens) AS input_tokens,
                SUM(output_tokens) AS output_tokens
            FROM queries
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """).fetchall()

        return {
            "overall": dict(row),
            "feedback": dict(fb),
            "daily": [dict(r) for r in daily],
            "recent": [dict(r) for r in recent],
            "token_daily": [dict(r) for r in token_daily],
        }


# Initialize DB on import
init_db()


# ── Chat History Persistence ──────────────────────────────────────────────────

def save_chat_message(session_id: str, role: str, content: str, data: dict = None):
    """Save a single chat message to DB."""
    import json
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role       TEXT,
                content    TEXT,
                data       TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            INSERT INTO chat_history (session_id, role, content, data)
            VALUES (?, ?, ?, ?)
        """, (session_id, role, content, json.dumps(data) if data else None))


def load_chat_history(session_id: str) -> list:
    """Load all messages for a session."""
    import json
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role       TEXT,
                content    TEXT,
                data       TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        rows = conn.execute("""
            SELECT role, content, data FROM chat_history
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,)).fetchall()
    messages = []
    for r in rows:
        msg = {"role": r["role"], "content": r["content"]}
        if r["data"]:
            msg["data"] = json.loads(r["data"])
        messages.append(msg)
    return messages


def get_all_sessions() -> list:
    """Get all unique sessions with their first question and timestamp."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, role TEXT, content TEXT,
                data TEXT, created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        rows = conn.execute("""
            SELECT
                session_id,
                MIN(created_at)  AS started_at,
                MAX(created_at)  AS last_active,
                COUNT(*)         AS message_count,
                MIN(CASE WHEN role='user' THEN content END) AS first_question
            FROM chat_history
            GROUP BY session_id
            ORDER BY last_active DESC
            LIMIT 50
        """).fetchall()
    return [dict(r) for r in rows]


def get_session_history_for_monitoring() -> list:
    """Get all questions across all sessions for monitoring dashboard."""
    with get_conn() as conn:
        try:
            rows = conn.execute("""
                SELECT
                    ch.session_id,
                    ch.content     AS question,
                    ch.created_at,
                    q.confidence,
                    q.total_ms,
                    q.total_tokens,
                    q.sources_cited,
                    q.error
                FROM chat_history ch
                LEFT JOIN queries q
                    ON ch.session_id = q.session_id
                    AND ch.content   = q.question
                WHERE ch.role = 'user'
                ORDER BY ch.created_at DESC
                LIMIT 100
            """).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []