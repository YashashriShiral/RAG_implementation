"""
monitoring_dashboard.py
Run: streamlit run monitoring_dashboard.py --server.port 8502
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json, glob
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="RAG Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS injection into parent page ────────────────────────────────────────────
components.html("""<script>
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { font-family: 'Inter', sans-serif !important; }
  html, body, [data-testid="stAppViewContainer"],
  section[data-testid="stMain"] > div,
  div[data-testid="block-container"] { background: #0d1117 !important; }
  header[data-testid="stHeader"] { background: #0d1117 !important; }
  section[data-testid="stSidebar"] { background: #161b22 !important; border-right: 1px solid #30363d !important; }
  p, div, span, label, h1, h2, h3, li { color: #e6edf3 !important; }
  div[data-testid="stMetric"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
  }
  div[data-testid="stMetricValue"] > div { color: #58a6ff !important; font-weight: 700 !important; }
  div[data-testid="stMetricLabel"] > div { color: #8b949e !important; font-size: .78rem !important; }
  [data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
  }
  [data-testid="stExpander"] summary { color: #e6edf3 !important; }
  [data-testid="stSelectbox"] > div > div,
  [data-testid="stTextInput"] input {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
  }
  .stButton > button {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
    font-size: .83rem !important;
    transition: all .15s !important;
  }
  .stButton > button:hover {
    border-color: #58a6ff !important;
    color: #58a6ff !important;
    background: #1c2128 !important;
  }
  [data-testid="stDownloadButton"] button {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
  }
  [data-testid="stTabs"] [role="tablist"] {
    background: #161b22 !important;
    border-radius: 10px !important;
    border: 1px solid #30363d !important;
  }
  [data-testid="stTabs"] button[role="tab"] { color: #8b949e !important; }
  [data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: #58a6ff !important; border-bottom-color: #58a6ff !important; }
  [data-testid="stDataFrame"] { background: #161b22 !important; border-radius: 12px !important; }
  [data-testid="stDataFrame"] * { color: #e6edf3 !important; }
  div[data-baseweb="tab-panel"] { background: #0d1117 !important; }
  .stAlert { background: #161b22 !important; border-color: #30363d !important; color: #e6edf3 !important; }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #0d1117; }
  ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 2px; }
`;
const s = document.createElement('style');
s.textContent = css;
window.parent.document.head.appendChild(s);
</script>""", height=0)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def load_stats():
    try:
        from app.monitor_db import get_stats
        return get_stats()
    except: return None

@st.cache_data(ttl=10)
def load_sessions():
    try:
        from app.monitor_db import get_all_sessions
        return get_all_sessions()
    except: return []

def load_eval_files():
    return sorted(glob.glob("./evaluation/results/eval_*.json"), reverse=True)

# ── Page header ───────────────────────────────────────────────────────────────
h1, h2 = st.columns([5, 1])
with h1:
    st.markdown("## 📊 RAG Monitoring Dashboard")
    st.caption(f"Updated {datetime.now().strftime('%b %d, %Y · %H:%M')}")
with h2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⟳ Refresh", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Overview", "🔍 Queries", "🧪 Evaluations"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    stats = load_stats()

    if not stats or not stats["overall"]["total_queries"]:
        st.info("📭 No data yet — start asking questions in the main app!")
    else:
        o  = stats["overall"]
        fb = stats["feedback"]

        # Row 1 — primary metrics
        st.markdown("**Key Metrics**")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Queries",    int(o["total_queries"] or 0))
        c2.metric("Avg Confidence",   f"{o['avg_confidence_pct'] or 0:.1f}%")
        c3.metric("Avg Latency",      f"{o['avg_latency_sec'] or 0:.2f}s")
        c4.metric("Total Tokens",     f"{int(o['total_tokens'] or 0):,}")
        c5.metric("👍 Feedback",       f"{fb['positive_pct'] or 0:.0f}%")

        # Row 2 — secondary metrics
        st.markdown("<br>", unsafe_allow_html=True)
        c6, c7, c8, c9 = st.columns(4)
        c6.metric("Avg Retrieval",    f"{o['avg_retrieval_sec'] or 0:.2f}s")
        c7.metric("Avg LLM Time",     f"{o['avg_llm_sec'] or 0:.2f}s")
        c8.metric("Avg Sources/Query",o['avg_sources_cited'] or 0)
        c9.metric("Errors",           int(o['error_count'] or 0))

        # Charts
        if stats["daily"]:
            st.markdown("<br>**Activity**", unsafe_allow_html=True)
            ch1, ch2 = st.columns(2)
            daily_df = pd.DataFrame(stats["daily"])
            with ch1:
                st.caption("Queries per day")
                st.bar_chart(daily_df.set_index("day")["count"], color="#6366f1", height=220)
            with ch2:
                st.caption("Avg latency (s)")
                st.line_chart(daily_df.set_index("day")["avg_latency"], color="#ec4899", height=220)

        if stats["token_daily"]:
            st.markdown("**Token Usage**")
            tdf = pd.DataFrame(stats["token_daily"])
            st.area_chart(tdf.set_index("day")[["input_tokens","output_tokens"]],
                color=["#6366f1","#ec4899"], height=200)
            st.caption("🟣 Input tokens   🩷 Output tokens")

        # Sessions summary
        sessions = load_sessions()
        if sessions:
            st.markdown("<br>**Sessions**", unsafe_allow_html=True)
            sdf = pd.DataFrame([{
                "Session":        s["session_id"][:14] + "…",
                "First Question": (s["first_question"] or "—")[:55],
                "Q&As":           s["message_count"]//2,
                "Started":        (s["started_at"] or "")[:16],
                "Last Active":    (s["last_active"] or "")[:16],
            } for s in sessions])
            st.dataframe(sdf, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — QUERIES
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    stats = load_stats()

    if not stats or not stats["recent"]:
        st.info("No queries yet.")
    else:
        all_queries = stats["recent"]   # already ordered newest first

        # ── Filters ──────────────────────────────────────────────────────────
        f1, f2, f3 = st.columns([1, 2, 2])
        with f1:
            show_n = st.selectbox("Show", [5, 10, 20, 50], index=0)
        with f2:
            ftype = st.selectbox("Filter", [
                "All", "High confidence (≥70%)",
                "Low confidence (<40%)", "Errors only", "Web search answers"
            ])
        with f3:
            keyword = st.text_input("Search keyword", placeholder="e.g. fertility, pain…")

        # ── Apply filters ─────────────────────────────────────────────────────
        filtered = all_queries
        if ftype == "High confidence (≥70%)":
            filtered = [q for q in filtered if (q.get("confidence") or 0) >= 0.7]
        elif ftype == "Low confidence (<40%)":
            filtered = [q for q in filtered if (q.get("confidence") or 0) < 0.4]
        elif ftype == "Errors only":
            filtered = [q for q in filtered if q.get("error")]
        elif ftype == "Web search answers":
            filtered = [q for q in filtered if (q.get("sources_cited") or 0) == 0]
        if keyword:
            filtered = [q for q in filtered if keyword.lower() in (q.get("question") or "").lower()]

        total = len(filtered)
        display = filtered[:show_n]

        st.caption(f"Showing {len(display)} of {total} matching queries · {len(all_queries)} total")

        if display:
            rows = []
            for q in display:
                conf = float(q.get("confidence") or 0)
                rows.append({
                    "Question":    (q.get("question") or "")[:75],
                    "Confidence":  f"{int(conf*100)}%",
                    "Latency":     f"{round((q.get('total_ms') or 0)/1000, 1)}s",
                    "Tokens":      q.get("total_tokens") or 0,
                    "Sources":     q.get("sources_cited") or 0,
                    "Status":      "❌ Error" if q.get("error") else "✅ OK",
                    "Time":        (q.get("created_at") or "")[:16],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── CSV download ──────────────────────────────────────────────────────
        try:
            from app.monitor_db import get_conn
            with get_conn() as conn:
                full_df = pd.read_sql("SELECT * FROM queries ORDER BY id DESC", conn)
            st.download_button("⬇️ Download Full Log (CSV)",
                data=full_df.to_csv(index=False),
                file_name="query_log.csv", mime="text/csv")
        except: pass

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EVALUATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    eval_files = load_eval_files()

    if not eval_files:
        st.info("No evaluation runs yet.\n\nRun: `python -m evaluation.ragas_eval`")
    else:
        # ── Run selector ──────────────────────────────────────────────────────
        labels = [Path(f).stem.replace("eval_","") for f in eval_files]
        try:
            friendly = [datetime.strptime(l,"%Y%m%d_%H%M%S").strftime("%b %d, %Y · %H:%M") for l in labels]
        except:
            friendly = labels

        sel_idx = st.selectbox("Evaluation run", range(len(friendly)),
            format_func=lambda i: friendly[i])
        ef = eval_files[sel_idx]

        with open(ef) as f:
            ed = json.load(f)

        scores     = ed.get("scores", {})
        thresholds = ed.get("thresholds", {})
        passed     = ed.get("passed", False)
        n_q        = ed.get("n_questions", 0)

        # ── Run summary ───────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns([2,1,1,1])
        with s1: st.markdown(f"**{friendly[sel_idx]}** · {n_q} questions evaluated")
        with s2:
            if passed: st.success("✅ CI Passed")
            else:      st.error("❌ CI Failed")
        with s3: st.metric("Questions", n_q)
        with s4:
            with open(ef) as f: raw = f.read()
            st.download_button("⬇️ JSON", data=raw,
                file_name=Path(ef).name, mime="application/json")

        st.markdown("---")

        # ── CI Gate metrics — clear table ─────────────────────────────────────
        ci = {k:v for k,v in scores.items() if k in thresholds}
        if ci:
            st.markdown("**CI Gate Metrics**")
            st.caption("These metrics must pass threshold for CI to approve a deployment.")

            ci_rows = []
            for metric, score in ci.items():
                thresh  = thresholds.get(metric, 0)
                score_f = float(score)
                gap     = round(score_f - thresh, 4)
                ci_rows.append({
                    "Metric":     metric.replace("_"," ").title(),
                    "Score":      round(score_f, 4),
                    "Threshold":  thresh,
                    "Gap":        f"+{gap}" if gap >= 0 else str(gap),
                    "Pass/Fail":  "✅ Pass" if score_f >= thresh else "❌ Fail",
                })

            ci_df = pd.DataFrame(ci_rows)

            # Color the Pass/Fail column using Streamlit's native styling
            def color_status(val):
                if "Pass" in val: return "background-color: #dcfce7; color: #166534"
                return "background-color: #fee2e2; color: #991b1b"

            styled = ci_df.style.applymap(color_status, subset=["Pass/Fail"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Info metrics ──────────────────────────────────────────────────────
        info = {k:v for k,v in scores.items() if k not in thresholds}
        if info:
            st.markdown("<br>**Additional Metrics**", unsafe_allow_html=True)
            ic = st.columns(min(len(info), 4))
            for col, (k, v) in zip(ic, info.items()):
                col.metric(k.replace("_"," ").title(), v)

        # ── Per-question breakdown ────────────────────────────────────────────
        per_q = ed.get("per_question", [])
        if per_q:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f"📋 Per-question breakdown — {len(per_q)} questions"):
                want = ["question","faithfulness_score","answer_relevancy",
                        "context_precision","context_recall","has_citation",
                        "latency_sec","tokens","sources_count"]
                want = [c for c in want if per_q and c in per_q[0]]
                pdf  = pd.DataFrame(per_q)[want].copy()
                pdf.columns = [c.replace("_score","").replace("_"," ").title()
                               for c in pdf.columns]
                if "Question" in pdf.columns:
                    pdf["Question"] = pdf["Question"].str[:65] + "…"
                st.dataframe(pdf, use_container_width=True, hide_index=True)

        # ── Compare runs (if multiple exist) ─────────────────────────────────
        if len(eval_files) > 1:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("📊 Compare all runs"):
                compare_rows = []
                for ef2, lbl2 in zip(eval_files, friendly):
                    try:
                        with open(ef2) as f2: d2 = json.load(f2)
                        row = {"Run": lbl2, "Questions": d2.get("n_questions",0),
                               "Passed": "✅" if d2.get("passed") else "❌"}
                        for k, v in d2.get("scores",{}).items():
                            row[k.replace("_"," ").title()] = round(float(v),3)
                        compare_rows.append(row)
                    except: pass
                if compare_rows:
                    st.dataframe(pd.DataFrame(compare_rows),
                        use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("SQLite · All local · No external services")