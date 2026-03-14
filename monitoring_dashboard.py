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

# ── Admin password protection ────────────────────────────────────────────────
import os as _os
ADMIN_PASSWORD = _os.getenv("ADMIN_PASSWORD", "endo-admin-2026")

def _check_password():
    if st.session_state.get("admin_auth"):
        return True
    st.markdown("""
    <div style='max-width:400px;margin:4rem auto;text-align:center;'>
      <div style='font-size:2rem;margin-bottom:1rem;'>🔒</div>
      <div style='font-size:1.2rem;font-weight:700;margin-bottom:.5rem;'>Admin Access</div>
      <div style='color:#8b949e;font-size:.85rem;margin-bottom:1.5rem;'>RAG Monitoring Dashboard</div>
    </div>
    """, unsafe_allow_html=True)
    pwd = st.text_input("Password", type="password", key="admin_pwd")
    if st.button("Login", use_container_width=False):
        if pwd == ADMIN_PASSWORD:
            st.session_state["admin_auth"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False

if not _check_password():
    st.stop()

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
tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "🔍 Queries", "🧪 Evaluations", "🩺 Parse Quality"])

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

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — PARSE QUALITY
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent))
    
    st.markdown("""
    <div style='padding:.4rem 0 .8rem 0;'>
      <span style='font-family:Lora,serif;font-size:1.1rem;font-weight:700;color:#2c1810;'>
        🔍 Parse Quality Monitor
      </span>
      <span style='font-size:.78rem;color:#9e8880;margin-left:.8rem;'>
        How well is LLaMA understanding your WhatsApp messages?
      </span>
    </div>
    """, unsafe_allow_html=True)

    try:
        from app.daily_log_db import get_parse_logs, init_parse_log_table
        import json as _pjson
        init_parse_log_table()

        pq_days = st.selectbox("Show last", [7, 14, 30, 60], index=1, key="pq_days")
        plogs   = get_parse_logs(days=pq_days)

        if not plogs:
            st.info("No parse logs yet — data appears after your next WhatsApp message.")
        else:
            pdf = pd.DataFrame(plogs)

            # ── Summary metrics ───────────────────────────────────────────────
            total     = len(pdf)
            llm1      = len(pdf[pdf["parse_source"] == "llama_attempt1"])
            llm2      = len(pdf[pdf["parse_source"] == "llama_attempt2"])
            regex     = len(pdf[pdf["parse_source"] == "regex_fallback"])
            llm_rate  = round((llm1 + llm2) / total * 100, 1)
            avg_fields= round(pdf["fields_extracted"].mean(), 1)
            completeness = round(avg_fields / 17 * 100, 1)

            st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:.5rem 0 .4rem 0;">OVERALL PARSE QUALITY</p>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)

            def _metric_card(col, emoji, label, value, sub, good=True):
                color = "#7cb69b" if good else "#e8857a"
                col.markdown(f"""
                <div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:10px;
                     padding:.8rem 1rem;'>
                  <div style='font-size:.72rem;color:#9e8880;'>{emoji} {label}</div>
                  <div style='font-size:1.4rem;font-weight:700;color:#2c1810;'>{value}</div>
                  <div style='font-size:.7rem;color:{color};font-weight:600;'>{sub}</div>
                </div>""", unsafe_allow_html=True)

            _metric_card(m1, "🧠", "LLaMA Success Rate", f"{llm_rate}%",
                         "✅ Good" if llm_rate >= 80 else "⚠️ Check prompts", llm_rate >= 80)
            _metric_card(m2, "📋", "Avg Fields Extracted", f"{avg_fields}/17",
                         f"{completeness}% completeness", completeness >= 60)
            _metric_card(m3, "🔄", "Retry Used",
                         f"{llm2}x", f"{round(llm2/total*100,1)}% of messages", llm2/total < 0.2)
            _metric_card(m4, "🔁", "Regex Fallback",
                         f"{regex}x", f"{round(regex/total*100,1)}% of messages", regex/total < 0.1)

            st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

            # ── Attempt breakdown bar ─────────────────────────────────────────
            st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:.5rem 0 .4rem 0;">PARSE SOURCE BREAKDOWN</p>', unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            for col, label, count, color, desc in [
                (b1, "🟢 LLaMA Attempt 1", llm1, "#7cb69b", "Parsed correctly first try"),
                (b2, "🟡 LLaMA Attempt 2", llm2, "#e8c97a", "Needed re-prompt"),
                (b3, "🔴 Regex Fallback",  regex, "#e8857a", "LLaMA failed, used regex"),
            ]:
                pct = round(count / total * 100, 1) if total else 0
                col.markdown(f"""
                <div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:10px;
                     padding:.8rem 1rem;text-align:center;'>
                  <div style='font-size:.8rem;font-weight:600;color:#2c1810;'>{label}</div>
                  <div style='font-size:2rem;font-weight:700;color:{color};'>{count}</div>
                  <div style='font-size:.72rem;color:#9e8880;'>{pct}% · {desc}</div>
                  <div style='height:6px;background:#e8ddd6;border-radius:3px;margin-top:.5rem;'>
                    <div style='width:{pct}%;height:6px;background:{color};border-radius:3px;'></div>
                  </div>
                </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

            # ── Field extraction completeness ─────────────────────────────────
            st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:.5rem 0 .4rem 0;">FIELD EXTRACTION COMPLETENESS</p>', unsafe_allow_html=True)

            TRACKED_FIELDS = {
                "pain_score":   "🔴 Pain",
                "mood_score":   "😊 Mood",
                "energy_score": "⚡ Energy",
                "steps":        "👣 Steps",
                "sleep_hours":  "😴 Sleep",
                "meals_count":  "🍽️ Meals",
            }
            fc1, fc2, fc3 = st.columns(3)
            field_cols = [fc1, fc2, fc3]
            for idx, (field, label) in enumerate(TRACKED_FIELDS.items()):
                col = field_cols[idx % 3]
                if field == "meals_count":
                    filled = len(pdf[pdf["meals_count"] > 0])
                else:
                    filled = len(pdf[pdf[field].notna()]) if field in pdf.columns else 0
                pct = round(filled / total * 100) if total else 0
                ok  = pct >= 70
                col.markdown(f"""
                <div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:8px;
                     padding:.6rem .9rem;margin-bottom:.4rem;'>
                  <div style='display:flex;justify-content:space-between;font-size:.8rem;'>
                    <span style='color:#2c1810;font-weight:500;'>{label}</span>
                    <span style='color:{"#7cb69b" if ok else "#e8857a"};font-weight:600;'>{pct}%</span>
                  </div>
                  <div style='height:5px;background:#e8ddd6;border-radius:3px;margin-top:.4rem;'>
                    <div style='width:{pct}%;height:5px;background:{"#7cb69b" if ok else "#e8857a"};border-radius:3px;'></div>
                  </div>
                  <div style='font-size:.68rem;color:#9e8880;margin-top:.2rem;'>{filled}/{total} messages</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

            # ── Recent parse log table ────────────────────────────────────────
            st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:.5rem 0 .4rem 0;">RECENT PARSE LOG</p>', unsafe_allow_html=True)

            SOURCE_EMOJI = {
                "llama_attempt1": "🟢 LLaMA #1",
                "llama_attempt2": "🟡 LLaMA #2",
                "regex_fallback": "🔴 Regex",
            }
            rows = []
            for _, row in pdf.head(20).iterrows():
                rows.append({
                    "Date":       str(row.get("log_date",""))[:10],
                    "Source":     SOURCE_EMOJI.get(row.get("parse_source",""), row.get("parse_source","")),
                    "Fields":     f"{row.get('fields_extracted',0)}/17",
                    "Pain":       f"{row['pain_score']:.0f}/10" if pd.notna(row.get('pain_score')) else "—",
                    "Mood":       f"{row['mood_score']:.0f}/10" if pd.notna(row.get('mood_score')) else "—",
                    "Energy":     f"{row['energy_score']:.0f}/10" if pd.notna(row.get('energy_score')) else "—",
                    "Steps":      int(row["steps"]) if pd.notna(row.get("steps")) else "—",
                    "Meals":      int(row.get("meals_count", 0)),
                    "Message":    str(row.get("raw_message",""))[:60] + "…",
                    "Time":       str(row.get("created_at",""))[:16],
                })

            st.markdown(html_table(pd.DataFrame(rows)), unsafe_allow_html=True)
            st.download_button("⬇️ Download parse log CSV",
                               pdf.to_csv(index=False),
                               "parse_quality_log.csv", "text/csv")

            # ── Tips if quality is poor ───────────────────────────────────────
            tips = []
            if llm_rate < 80:
                tips.append("⚠️ LLaMA success rate is low — Ollama may be slow or the model needs more context.")
            if completeness < 60:
                tips.append("💡 Low field completeness — try being more specific in messages e.g. 'pain 4/10, mood good, slept 7hrs'.")
            if regex / total > 0.2:
                tips.append("🔁 High regex fallback rate — check if Ollama is running with `ollama ps`.")
            if tips:
                st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
                for tip in tips:
                    st.warning(tip)

    except Exception as e:
        st.error(f"Could not load parse logs: {e}")
        st.caption("This tab populates after your first WhatsApp message post-update.")


st.markdown("---")
st.caption("SQLite · All local · No external services")