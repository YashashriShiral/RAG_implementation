"""
monitoring_dashboard.py
─────────────────────────────────────────────────────────────────────────────
Monitoring Dashboard — run separately from the main app

Run: streamlit run monitoring_dashboard.py --server.port 8502

Shows:
  - Total queries, avg confidence, avg latency
  - Token usage (input/output/total)
  - Queries per day chart
  - Token usage per day chart  
  - User feedback score
  - Recent query log with details
  - Error tracking
"""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="RAG Monitoring",
    page_icon="📊",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@600;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #0d1117; --bg2: #161b22; --bg3: #1c2128;
    --border: #30363d; --text: #e6edf3; --muted: #8b949e;
    --blue: #58a6ff; --green: #3fb950; --orange: #f0883e;
    --purple: #bc8cff; --red: #f85149;
}
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
.dash-title {
    font-family: 'Sora', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #58a6ff, #bc8cff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.metric-card {
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--blue);
    line-height: 1;
}
.metric-label {
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.metric-green  { color: var(--green) !important; }
.metric-orange { color: var(--orange) !important; }
.metric-purple { color: var(--purple) !important; }
.metric-red    { color: var(--red) !important; }
.section-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 1.5rem 0 0.8rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
}
.query-row {
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
}
.query-q { color: var(--text); font-weight: 500; margin-bottom: 0.3rem; }
.query-meta { color: var(--muted); font-size: 0.75rem; }
.tag {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    margin-right: 0.3rem;
}
.tag-good { background: rgba(63,185,80,0.15); color: #3fb950; }
.tag-mid  { background: rgba(240,136,62,0.15); color: #f0883e; }
.tag-bad  { background: rgba(248,81,73,0.15);  color: #f85149; }
.tag-blue { background: rgba(88,166,255,0.15); color: #58a6ff; }
.stButton > button {
    background: var(--bg3) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
.stButton > button:hover {
    border-color: var(--blue) !important;
    color: var(--blue) !important;
}
</style>
""", unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)  # refresh every 10 seconds
def load_stats():
    try:
        from app.monitor_db import get_stats
        return get_stats()
    except Exception as e:
        return None


# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([6, 1])
with col_title:
    st.markdown('<div class="dash-title">📊 RAG Monitoring Dashboard</div>', unsafe_allow_html=True)
    st.caption(f"Endometriosis Research AI · Last updated: {datetime.now().strftime('%H:%M:%S')}")
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

stats = load_stats()

if not stats or stats["overall"]["total_queries"] == 0:
    st.markdown("""
    <div style="background:#1c2128;border:1px solid #30363d;border-radius:10px;padding:2rem;text-align:center;margin-top:2rem;">
        <div style="font-size:2rem;margin-bottom:0.5rem;">📭</div>
        <div style="color:#8b949e;">No queries logged yet. Start asking questions in the main app!</div>
        <div style="color:#6e7681;font-size:0.8rem;margin-top:0.5rem;">Run: <code>streamlit run streamlit_app.py</code></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

o = stats["overall"]
fb = stats["feedback"]

# ── Top metrics ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Overview</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{int(o['total_queries'] or 0)}</div>
        <div class="metric-label">Total Queries</div>
    </div>""", unsafe_allow_html=True)

with c2:
    conf = o['avg_confidence_pct'] or 0
    color = "metric-green" if conf >= 70 else ("metric-orange" if conf >= 40 else "metric-red")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value {color}">{conf}%</div>
        <div class="metric-label">Avg Confidence</div>
    </div>""", unsafe_allow_html=True)

with c3:
    lat = o['avg_latency_sec'] or 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value metric-purple">{lat}s</div>
        <div class="metric-label">Avg Latency</div>
    </div>""", unsafe_allow_html=True)

with c4:
    tokens = int(o['total_tokens'] or 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value metric-orange">{tokens:,}</div>
        <div class="metric-label">Total Tokens</div>
    </div>""", unsafe_allow_html=True)

with c5:
    avg_tok = int(o['avg_tokens_per_query'] or 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{avg_tok}</div>
        <div class="metric-label">Avg Tokens/Query</div>
    </div>""", unsafe_allow_html=True)

with c6:
    pos_pct = fb['positive_pct'] or 0
    total_fb = fb['total_feedback'] or 0
    color = "metric-green" if pos_pct >= 70 else ("metric-orange" if pos_pct >= 40 else "metric-red")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value {color}">{pos_pct}%</div>
        <div class="metric-label">👍 Feedback ({total_fb})</div>
    </div>""", unsafe_allow_html=True)

# ── Second row metrics ────────────────────────────────────────────────────────
c7, c8, c9, c10 = st.columns(4)

with c7:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{o['avg_retrieval_sec'] or 0}s</div>
        <div class="metric-label">Avg Retrieval Time</div>
    </div>""", unsafe_allow_html=True)

with c8:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{o['avg_llm_sec'] or 0}s</div>
        <div class="metric-label">Avg LLM Time</div>
    </div>""", unsafe_allow_html=True)

with c9:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{o['avg_sources_cited'] or 0}</div>
        <div class="metric-label">Avg Sources Cited</div>
    </div>""", unsafe_allow_html=True)

with c10:
    err = int(o['error_count'] or 0)
    color = "metric-red" if err > 0 else "metric-green"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value {color}">{err}</div>
        <div class="metric-label">Errors</div>
    </div>""", unsafe_allow_html=True)


# ── Charts ────────────────────────────────────────────────────────────────────
if stats["daily"]:
    st.markdown('<div class="section-title">Activity (Last 7 Days)</div>', unsafe_allow_html=True)
    chart_col1, chart_col2 = st.columns(2)

    daily_df = pd.DataFrame(stats["daily"])

    with chart_col1:
        st.caption("📈 Queries per day")
        st.bar_chart(
            daily_df.set_index("day")["count"],
            color="#58a6ff",
            height=200,
        )

    with chart_col2:
        st.caption("⚡ Avg latency per day (seconds)")
        st.line_chart(
            daily_df.set_index("day")["avg_latency"],
            color="#bc8cff",
            height=200,
        )

if stats["token_daily"]:
    st.markdown('<div class="section-title">Token Usage (Last 7 Days)</div>', unsafe_allow_html=True)
    token_df = pd.DataFrame(stats["token_daily"])
    st.area_chart(
        token_df.set_index("day")[["input_tokens", "output_tokens"]],
        color=["#58a6ff", "#3fb950"],
        height=200,
    )
    st.caption("🔵 Input tokens (questions)  &nbsp; 🟢 Output tokens (answers)")


# ── Recent queries ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Recent Queries</div>', unsafe_allow_html=True)

if stats["recent"]:
    for q in stats["recent"]:
        conf = q["confidence"] or 0
        conf_pct = int(conf * 100)
        conf_tag = "tag-good" if conf >= 0.7 else ("tag-mid" if conf >= 0.4 else "tag-bad")
        err_tag = f'<span class="tag tag-bad">ERROR</span>' if q["error"] else ""
        latency = round((q["total_ms"] or 0) / 1000, 1)
        tokens = q["total_tokens"] or 0
        sources = q["sources_cited"] or 0
        time_str = q["created_at"][:16] if q["created_at"] else ""

        question_preview = q["question"][:120] + "…" if len(q["question"]) > 120 else q["question"]

        st.markdown(f"""
        <div class="query-row">
            <div class="query-q">{question_preview}</div>
            <div class="query-meta">
                {err_tag}
                <span class="tag {conf_tag}">Confidence {conf_pct}%</span>
                <span class="tag tag-blue">⏱ {latency}s</span>
                <span class="tag tag-blue">🪙 {tokens} tokens</span>
                <span class="tag tag-blue">📎 {sources} sources</span>
                &nbsp;·&nbsp; {time_str}
                &nbsp;·&nbsp; Session: {str(q['session_id'])[:8]}…
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Download full log as CSV
    st.markdown("<br>", unsafe_allow_html=True)
    try:
        from app.monitor_db import get_conn
        with get_conn() as conn:
            full_df = pd.read_sql("SELECT * FROM queries ORDER BY id DESC", conn)
        csv = full_df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download Full Query Log (CSV)",
            data=csv,
            file_name="query_log.csv",
            mime="text/csv",
        )
    except Exception:
        pass
else:
    st.caption("No queries yet.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Auto-refreshes every 10 seconds · Data stored in data/monitoring.db · All processing is local")


# ── Full Question History ─────────────────────────────────────────────────────
st.markdown('<div class="section-title">Full Question History (All Sessions)</div>', unsafe_allow_html=True)

try:
    from app.monitor_db import get_session_history_for_monitoring, get_all_sessions

    # Session summary
    sessions = get_all_sessions()
    if sessions:
        st.caption(f"{len(sessions)} total session(s) recorded")
        with st.expander("📋 View all sessions", expanded=False):
            for s in sessions:
                first_q = s["first_question"] or "—"
                preview = first_q[:60] + "…" if len(first_q) > 60 else first_q
                st.markdown(f"""
                <div class="query-row">
                    <div class="query-q">{preview}</div>
                    <div class="query-meta">
                        <span class="tag tag-blue">Session: {s['session_id'][:12]}…</span>
                        <span class="tag tag-blue">{s['message_count']//2} Q&As</span>
                        &nbsp;·&nbsp; Started: {s['started_at'][:16] if s['started_at'] else '—'}
                        &nbsp;·&nbsp; Last active: {s['last_active'][:16] if s['last_active'] else '—'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # All questions
    all_qs = get_session_history_for_monitoring()
    if all_qs:
        st.caption(f"{len(all_qs)} total question(s) asked")
        for q in all_qs:
            conf = q.get("confidence") or 0
            conf_pct = int(float(conf) * 100)
            conf_tag = "tag-good" if conf_pct >= 70 else ("tag-mid" if conf_pct >= 40 else "tag-bad")
            latency = round((q.get("total_ms") or 0) / 1000, 1)
            tokens = q.get("total_tokens") or 0
            sources = q.get("sources_cited") or 0
            err_tag = '<span class="tag tag-bad">ERROR</span>' if q.get("error") else ""
            time_str = (q.get("created_at") or "")[:16]
            question_preview = (q["question"] or "")[:120]
            if len(q.get("question","")) > 120:
                question_preview += "…"

            st.markdown(f"""
            <div class="query-row">
                <div class="query-q">{question_preview}</div>
                <div class="query-meta">
                    {err_tag}
                    <span class="tag {conf_tag}">Confidence {conf_pct}%</span>
                    <span class="tag tag-blue">⏱ {latency}s</span>
                    <span class="tag tag-blue">🪙 {tokens} tokens</span>
                    <span class="tag tag-blue">📎 {sources} sources</span>
                    &nbsp;·&nbsp; {time_str}
                    &nbsp;·&nbsp; Session: {str(q.get('session_id',''))[:8]}…
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Download all questions as CSV
        import pandas as pd
        df = pd.DataFrame(all_qs)
        st.download_button(
            label="⬇️ Download Full Question History (CSV)",
            data=df.to_csv(index=False),
            file_name="question_history.csv",
            mime="text/csv",
        )
    else:
        st.caption("No questions logged yet.")

except Exception as e:
    st.caption(f"Could not load history: {e}")