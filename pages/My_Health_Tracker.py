"""
pages/My_Health_Tracker.py
─────────────────────────────────────────────────────────────────────────────
Health Tracker page. Fixes sys.path so app/daily_log_db.py is always found.
"""

import sys, os, json
from pathlib import Path

# ── CRITICAL: fix import path before anything else ───────────────────────────
# pages/ runs with a different cwd; insert repo root so `from app.X` works
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(
    page_title="My Health Tracker · EndoResearch AI",
    page_icon="💜", layout="wide", initial_sidebar_state="expanded",
)

components.html("""
<script>
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');
  [data-testid="stSidebarNav"] { display: none !important; }
  html, body, [data-testid="stAppViewContainer"] { background: #fdf6f0 !important; }
  section[data-testid="stMain"] > div { background: #fdf6f0 !important; }
  section[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e8ddd6 !important; }
  header[data-testid="stHeader"] { background: #fdf6f0 !important; }
  [data-testid="stBottom"], [data-testid="stBottom"] > div,
  [data-testid="stBottom"] > div > div { background: #fdf6f0 !important; }
  html, body, p, div, span, label, h1, h2, h3 { font-family: 'DM Sans', sans-serif !important; color: #2c1810 !important; }
  .stButton > button {
    background: #ffffff !important; color: #2c1810 !important;
    border: 1px solid #e8ddd6 !important; border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important; font-size: 0.83rem !important;
    font-weight: 500 !important; width: 100% !important; transition: all 0.15s !important;
  }
  .stButton > button:hover { border-color: #c0392b !important; color: #c0392b !important; background: #fff5f5 !important; }
  [data-testid="stExpander"] { background: #ffffff !important; border: 1px solid #e8ddd6 !important; border-radius: 8px !important; }
  [data-testid="stSelectbox"] > div > div,
  [data-testid="stTextInput"] input { background: #ffffff !important; color: #2c1810 !important; border: 1px solid #e8ddd6 !important; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #fdf6f0; }
  ::-webkit-scrollbar-thumb { background: #e8ddd6; border-radius: 2px; }
  /* Fix dropdown list background */
  [data-baseweb="select"] { background: #ffffff !important; }
  [data-baseweb="menu"] { background: #ffffff !important; }
  [data-baseweb="menu"] ul { background: #ffffff !important; }
  [data-baseweb="option"] { background: #ffffff !important; color: #2c1810 !important; }
  [data-baseweb="option"]:hover { background: #fdf6f0 !important; color: #2c1810 !important; }
  [aria-selected="true"][data-baseweb="option"] { background: #f0e8e0 !important; color: #2c1810 !important; }
  [data-baseweb="popover"] { background: #ffffff !important; }
  li[role="option"] { background: #ffffff !important; color: #2c1810 !important; }
  li[role="option"]:hover { background: #fdf6f0 !important; }
  [data-testid="stSidebar"] .stButton > button {
    font-size: .78rem !important; padding: .3rem .6rem !important; border-radius: 6px !important;
    background: transparent !important; border: 1px solid transparent !important;
    color: #5a3e35 !important; height: 2rem !important; min-height: 0 !important; line-height: 1.2 !important;
  }
  [data-testid="stSidebar"] .stButton > button:hover { background: #f0e8e0 !important; border-color: #e8ddd6 !important; color: #2c1810 !important; }
  [data-testid="stMetric"] { background: #ffffff !important; border: 1px solid #e8ddd6 !important; border-radius: 10px !important; padding: 0.8rem 1rem !important; }
  [data-testid="stMetricLabel"] { font-size: .78rem !important; color: #9e8880 !important; }
  [data-testid="stMetricValue"] { color: #2c1810 !important; }

  /* ── Fix ALL black tables everywhere ── */
  [data-testid="stDataFrame"] { background: #ffffff !important; border-radius: 8px !important; border: 1px solid #e8ddd6 !important; }
  [data-testid="stDataFrame"] > div { background: #ffffff !important; }
  [data-testid="stDataFrame"] iframe { background: #ffffff !important; }
  /* Streamlit uses an iframe for dataframes — target it */
  .stDataFrame { background: #ffffff !important; }
  /* Arrow table (newer Streamlit) */
  [data-testid="stArrowVegaLiteChart"] { background: #ffffff !important; }
  /* The actual glide-data-grid inside the iframe */
  .dvn-scroller { background: #ffffff !important; }
  /* Tab panels background */
  div[data-baseweb="tab-panel"] { background: #fdf6f0 !important; }
  .stTabs [data-baseweb="tab-list"] { background: #f8f3ef !important; border-radius: 8px !important; gap: 4px !important; }
  .stTabs [data-baseweb="tab"] { color: #9e8880 !important; border-radius: 6px !important; }
  .stTabs [aria-selected="true"] { background: #ffffff !important; color: #2c1810 !important; font-weight: 600 !important; }
  /* Download button */
  [data-testid="stDownloadButton"] button { background: #ffffff !important; color: #2c1810 !important; border: 1px solid #e8ddd6 !important; border-radius: 8px !important; }
  /* Number inputs */
  [data-testid="stNumberInput"] input { background: #ffffff !important; color: #2c1810 !important; border: 1px solid #e8ddd6 !important; border-radius: 8px !important; }
  /* Info/warning boxes */
  .stAlert { background: #fff8f5 !important; border-color: #e8ddd6 !important; color: #2c1810 !important; }
  /* Caption text */
  .stCaption { color: #9e8880 !important; }
`;
const s = document.createElement('style');
s.textContent = css;
window.parent.document.head.appendChild(s);
</script>
""", height=0)

# ── Import DB ─────────────────────────────────────────────────────────────────
DB_OK = False
DB_ERR = ""
try:
    from app.daily_log_db import init_daily_log_table, get_logs, get_weekly_summary, upsert_daily_log
    init_daily_log_table()
    DB_OK = True
except Exception as e:
    DB_ERR = str(e)

PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#2c1810", size=12),
    margin=dict(l=10, r=10, t=10, b=40),
    legend=dict(
        orientation="h", y=-0.25, x=0.5, xanchor="center",
        bgcolor="rgba(0,0,0,0)", font=dict(size=12, color="#2c1810"),
        itemsizing="constant",
    ),
)

XAXIS = dict(
    gridcolor="#e8ddd6",
    type="category",
    tickangle=-20,
    tickfont=dict(size=11, color="#2c1810"),
    linecolor="#e8ddd6",
    zerolinecolor="#e8ddd6",
)

YAXIS = dict(
    gridcolor="#e8ddd6",
    tickfont=dict(size=11, color="#2c1810"),
    linecolor="#e8ddd6",
    zerolinecolor="#e8ddd6",
)

@st.cache_data(ttl=30)  # refresh every 30s so new WhatsApp logs appear
def load_df(days=90, cache_key=0):
    logs = get_logs(days=days)
    if not logs: return pd.DataFrame()
    df = pd.DataFrame(logs)
    df["log_date"] = pd.to_datetime(df["log_date"]).dt.strftime("%Y-%m-%d")
    return df.sort_values("log_date")

def html_table(df, max_rows=50):
    """Render a pandas DataFrame as a styled HTML table — never goes black."""
    if df.empty:
        return "<p style='color:#9e8880;font-size:.83rem;'>No data</p>"
    rows_html = ""
    for _, row in df.head(max_rows).iterrows():
        cells = ""
        for val in row:
            cells += f"<td style='padding:.4rem .7rem;border-bottom:1px solid #f0e8e0;font-size:.8rem;color:#2c1810;white-space:nowrap;'>{val}</td>"
        rows_html += f"<tr>{cells}</tr>"
    headers = "".join(
        f"<th style='padding:.4rem .7rem;text-align:left;font-size:.72rem;font-weight:600;color:#9e8880;border-bottom:2px solid #e8ddd6;white-space:nowrap;letter-spacing:.04em;'>{col.upper()}</th>"
        for col in df.columns
    )
    return f"""
    <div style='overflow-x:auto;border:1px solid #e8ddd6;border-radius:8px;background:#ffffff;'>
      <table style='width:100%;border-collapse:collapse;background:#ffffff;'>
        <thead><tr style='background:#f8f3ef;'>{headers}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""


def fmt(v, suffix=""):
    if v is None: return "—"
    return f"{float(v):.1f}{suffix}" if isinstance(v, float) else f"{v}{suffix}"

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="font-size:.95rem;font-weight:700;margin:0;padding:.2rem 0;">🌸 EndoResearch AI</p>', unsafe_allow_html=True)
    n1, n2 = st.columns(2)
    with n1: st.page_link("streamlit_app.py", label="🔬 Research AI", use_container_width=True)
    with n2: st.page_link("pages/My_Health_Tracker.py", label="💜 Health Tracker", use_container_width=True)
    st.markdown("---")

    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .3rem 0;">⚙️ View settings</p>', unsafe_allow_html=True)
    days_range = st.selectbox("Time window", [7, 14, 30, 60, 90], index=2,
                              format_func=lambda x: f"Last {x} days")

    st.markdown("---")
    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .3rem 0;">✏️ Log today</p>', unsafe_allow_html=True)
    st.caption("Or send a WhatsApp message to your bot")

    with st.form("manual_log", clear_on_submit=True):
        log_date       = st.date_input("Date", value=date.today())
        log_pain       = st.slider("Pain (1–10)", 1, 10, 5)
        log_mood       = st.slider("Mood (1–10)", 1, 10, 6)
        log_energy     = st.slider("Energy (1–10)", 1, 10, 6)
        log_steps      = st.number_input("Steps", 0, 50000, 0, step=500)
        log_meditation = st.number_input("Meditation (min)", 0, 180, 0)
        log_sleep      = st.number_input("Sleep (hrs)", 0.0, 24.0, 7.0, step=0.5)
        log_period     = st.checkbox("On period today")
        log_cycle_day  = st.number_input("Cycle day", 1, 35, 1) if log_period else None
        log_pain_loc   = st.text_input("Pain location(s)", placeholder="lower abdomen, back")
        log_herbal     = st.text_input("Herbal drinks", placeholder="ginger tea, ashwagandha")
        log_meds       = st.text_input("Medicines", placeholder="ibuprofen")
        log_meals      = st.text_input("Meals", placeholder="dal rice, salad")
        st.markdown('<p style="font-size:.75rem;font-weight:600;color:#9e8880;margin:.3rem 0 0 0;">🏃 Exercise / Yoga / Stretch</p>', unsafe_allow_html=True)
        log_exercise_type = st.selectbox("Type", 
            ["None", "Yoga", "Stretching", "Walking", "Running", "Gym", "Swimming", "Cycling", "Dance", "Pilates"],
            index=0)
        log_exercise_mins = st.number_input("Duration (min)", 0, 180, 0, step=5) if log_exercise_type != "None" else 0
        log_exercise_int  = st.selectbox("Intensity", ["Gentle", "Moderate", "Intense"], index=1) if log_exercise_type != "None" else None
        log_notes      = st.text_area("Notes", placeholder="How are you feeling?", height=68)

        if st.form_submit_button("💜 Save entry", use_container_width=True):
            if not DB_OK:
                st.error(f"DB error: {DB_ERR}")
            else:
                upsert_daily_log({
                    "log_date":           str(log_date),
                    "pain_score":         float(log_pain),
                    "mood_score":         float(log_mood),
                    "energy_score":       float(log_energy),
                    "steps":              int(log_steps) if log_steps else None,
                    "meditation_minutes": int(log_meditation) if log_meditation else None,
                    "sleep_hours":        float(log_sleep),
                    "on_period":          1 if log_period else 0,
                    "cycle_day":          int(log_cycle_day) if log_cycle_day else None,
                    "pain_locations":     [p.strip() for p in log_pain_loc.split(",") if p.strip()],
                    "herbal_drinks":      [h.strip() for h in log_herbal.split(",") if h.strip()],
                    "medicines":          [m.strip() for m in log_meds.split(",") if m.strip()],
                    "meals":              [m.strip() for m in log_meals.split(",") if m.strip()],
                    "notes":              log_notes.strip() or None,
                })
                st.success(f"✅ Saved for {log_date}!")
                st.rerun()

    st.markdown("---")
    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .3rem 0;">📲 WhatsApp logging</p>', unsafe_allow_html=True)
    st.caption("Once Twilio is set up, just send:")
    st.code("Steps 7200, ate dal rice,\nfeeling 6/10, mild cramps,\nperiod day 2, ginger tea,\nibuprofen, meditated 15 min", language="text")
    st.markdown("---")
    st.caption("LLaMA 3.2 · LangGraph · BGE · Cohere")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN AREA
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:1.2rem 0 1rem 0;border-bottom:1px solid #e8ddd6;margin-bottom:1.2rem;'>
  <div style='font-size:2.2rem;margin-bottom:.4rem;'>💜</div>
  <div style='font-family:Lora,serif;font-size:1.7rem;font-weight:700;color:#2c1810;'>My Health Tracker</div>
  <div style='color:#9e8880;font-size:.85rem;margin-top:.3rem;'>WhatsApp-logged · Week-over-week trends · Endometriosis-focused</div>
</div>
""", unsafe_allow_html=True)

# Scale reference card
st.markdown("""
<div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:10px;
     padding:0.8rem 1.2rem;margin-bottom:1rem;'>
  <p style='font-size:.75rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:0 0 .5rem 0;'>
    📊 SCORING GUIDE (for WhatsApp logging)
  </p>
  <div style='display:flex;gap:2rem;flex-wrap:wrap;'>
    <div>
      <span style='font-weight:600;font-size:.82rem;'>🔴 Pain</span>
      <span style='font-size:.8rem;color:#9e8880;'> — higher = worse</span><br>
      <span style='font-size:.78rem;'>1 = no pain &nbsp;·&nbsp; 5 = moderate &nbsp;·&nbsp; 10 = unbearable</span>
    </div>
    <div>
      <span style='font-weight:600;font-size:.82rem;'>😊 Mood</span>
      <span style='font-size:.8rem;color:#9e8880;'> — higher = better</span><br>
      <span style='font-size:.78rem;'>1 = terrible &nbsp;·&nbsp; 5 = okay &nbsp;·&nbsp; 10 = great</span>
    </div>
    <div>
      <span style='font-weight:600;font-size:.82rem;'>⚡ Energy</span>
      <span style='font-size:.8rem;color:#9e8880;'> — higher = better</span><br>
      <span style='font-size:.78rem;'>1 = exhausted &nbsp;·&nbsp; 5 = average &nbsp;·&nbsp; 10 = energised</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if not DB_OK:
    st.error(f"❌ Database error: `{DB_ERR}`")
    st.code(f"Repo root detected as: {_REPO_ROOT}\nLooking for: {_REPO_ROOT}/app/daily_log_db.py")
    st.stop()

# cache-bust key changes whenever a delete happens — forces fresh DB read
_cache_key = st.session_state.get("db_version", 0)
df = load_df(days=days_range, cache_key=_cache_key)

if df.empty:
    st.markdown("""
    <div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:12px;
         padding:2.5rem;text-align:center;margin-top:1rem;'>
      <div style='font-size:2.5rem;margin-bottom:.8rem;'>📋</div>
      <div style='font-family:Lora,serif;font-size:1.2rem;font-weight:600;color:#2c1810;margin-bottom:.6rem;'>
        No entries yet
      </div>
      <div style='color:#9e8880;font-size:.88rem;line-height:1.7;'>
        Use the <b>✏️ Log today</b> form in the sidebar to add your first entry.<br>
        Charts and trends will appear here as you log more days.
      </div>
    </div>""", unsafe_allow_html=True)
    st.stop()



def _phase(d, last_start, avg_cycle, next_period, period_dates, ovul_dates, pms_dates):
    if d in period_dates: return "Period"
    if last_start and (d - last_start).days < 8: return "Post-period"
    if d in ovul_dates: return "Ovulation"
    if d in pms_dates: return "PMS"
    if next_period and (next_period - d).days <= 10: return "Late luteal"
    return "Follicular"

tab1, tab2, tab3 = st.tabs(["📊 Health Trends", "🗓️ Cycle Tracker", "📋 Log History"])

with tab1:
    # ── Period selector + comparison ─────────────────────────────────────────────
    from datetime import date as _dt, timedelta as _td
    import calendar as _cal

    _today = _dt.today()

    period_opts = ["This week vs Last week", "This month vs Last month",
                   "Last 30 days vs Prior 30 days", "Last 90 days vs Prior 90 days"]
    sel_period = st.selectbox("📅 Compare", period_opts, key="period_compare",
                              label_visibility="collapsed")

    def _date_ranges(sel):
        if sel == "This week vs Last week":
            s1 = _today - _td(days=_today.weekday())
            e1 = _today
            s2 = s1 - _td(days=7)
            e2 = s1 - _td(days=1)
            l1, l2 = "This week", "Last week"
        elif sel == "This month vs Last month":
            s1 = _today.replace(day=1)
            e1 = _today
            last_m = (s1 - _td(days=1))
            s2 = last_m.replace(day=1)
            e2 = last_m
            l1 = _today.strftime("%B")
            l2 = last_m.strftime("%B")
        elif sel == "Last 30 days vs Prior 30 days":
            s1 = _today - _td(days=29)
            e1 = _today
            s2 = _today - _td(days=59)
            e2 = _today - _td(days=30)
            l1, l2 = "Last 30 days", "Prior 30 days"
        else:
            s1 = _today - _td(days=89)
            e1 = _today
            s2 = _today - _td(days=179)
            e2 = _today - _td(days=90)
            l1, l2 = "Last 90 days", "Prior 90 days"
        return s1, e1, s2, e2, l1, l2

    def _period_stats(start, end):
        logs = get_logs(days=999)
        filtered = [l for l in logs
                    if start.isoformat() <= str(l.get("log_date",""))[:10] <= end.isoformat()]
        if not filtered:
            return {}
        def avg(f):
            vals = [l[f] for l in filtered if l.get(f) is not None]
            return round(sum(vals)/len(vals), 1) if vals else None
        return {
            "avg_pain":       avg("pain_score"),
            "avg_mood":       avg("mood_score"),
            "avg_energy":     avg("energy_score"),
            "avg_steps":      avg("steps"),
            "meditation_days": len([l for l in filtered if (l.get("meditation_minutes") or 0) > 0]),
            "days_logged":    len(filtered),
            "period_days":    len(sel_period),
        }

    s1, e1, s2, e2, label1, label2 = _date_ranges(sel_period)
    cur  = _period_stats(s1, e1)
    prev = _period_stats(s2, e2)

    def wd(key, lower_better=False):
        c, p = cur.get(key), prev.get(key)
        if c is None or p is None: return None
        d = round(c - p, 1)
        return -d if lower_better else d

    days_in_period = (e1 - s1).days + 1
    logged = cur.get("days_logged", 0)

    st.markdown(
        f'<p style="font-size:.82rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:0 0 .5rem 0;">' +
        f'{label1.upper()} VS {label2.upper()} &nbsp;·&nbsp; ' +
        f'<span style="font-weight:400;">{logged}/{days_in_period} days logged</span></p>',
        unsafe_allow_html=True
    )

    if logged == 0:
        st.info(f"No logs found for {label1}. Send a WhatsApp message to start tracking!")
    else:
        mc = st.columns(5)
        mc[0].metric("🔴 Avg Pain",        fmt(cur.get("avg_pain"),"/10"),   delta=wd("avg_pain", lower_better=True))
        mc[1].metric("😊 Avg Mood",        fmt(cur.get("avg_mood"),"/10"),   delta=wd("avg_mood"))
        mc[2].metric("⚡ Avg Energy",      fmt(cur.get("avg_energy"),"/10"), delta=wd("avg_energy"))
        mc[3].metric("👣 Avg Steps",       fmt(cur.get("avg_steps")),        delta=wd("avg_steps"))
        mc[4].metric("🧘 Meditation days", f"{cur.get('meditation_days',0)}/{days_in_period}",
                     delta=int((cur.get("meditation_days") or 0) - (prev.get("meditation_days") or 0)))

    # keep these for rest of tab1 code
    this_week = cur
    last_week = prev

    # ── Period pain banner ────────────────────────────────────────────────────────
    if "on_period" in df.columns and "pain_score" in df.columns:
        pp  = df[df["on_period"] == 1]["pain_score"].dropna()
        npp = df[df["on_period"] != 1]["pain_score"].dropna()
        if not pp.empty and not npp.empty:
            diff = round(pp.mean() - npp.mean(), 1)
            em   = "🔴" if diff > 1.5 else ("🟡" if diff > 0.5 else "🟢")
            st.markdown(f"""
            <div style='background:#ffffff;border:1px solid #e8ddd6;border-left:3px solid #c0392b;
                 border-radius:8px;padding:.65rem 1rem;margin:.8rem 0;font-size:.84rem;'>
              {em} <b>Period pattern:</b> pain is <b>{abs(diff):.1f} pts {"higher" if diff>0 else "lower"}</b>
              on period days ({pp.mean():.1f}/10) vs non-period ({npp.mean():.1f}/10)
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    # ── Row 1: Pain/Mood/Energy | Steps ──────────────────────────────────────────
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:0 0 .3rem 0;">PAIN · MOOD · ENERGY</p>', unsafe_allow_html=True)
        fig = go.Figure()
        for col_name, label, color in [("pain_score","Pain","#c0392b"),("mood_score","Mood","#833ab4"),("energy_score","Energy","#e67e22")]:
            if col_name in df.columns and df[col_name].notna().any():
                sub = df.dropna(subset=[col_name])
                fig.add_trace(go.Scatter(x=sub["log_date"], y=sub[col_name], name=label,
                    mode="lines+markers", line=dict(color=color, width=2), marker=dict(size=6, color=color),
                    hovertemplate=f"<b>{label}</b>: %{{y}}/10<br>%{{x|%b %d}}<extra></extra>"))
        if "on_period" in df.columns:
            for _, row in df[df["on_period"] == 1].iterrows():
                fig.add_vrect(x0=row["log_date"], x1=row["log_date"],
                              fillcolor="rgba(192,57,43,0.15)", line_width=1,
                              line_color="rgba(192,57,43,0.2)")
        fig.update_layout(**PLOT, height=300,
                          yaxis=dict(range=[0,10.5], title="Score (1–10)", **YAXIS),
                          xaxis={**XAXIS},
                          showlegend=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("🩸 Shaded = period days")

    with c2:
        st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:0 0 .3rem 0;">DAILY STEPS</p>', unsafe_allow_html=True)
        if "steps" in df.columns and df["steps"].notna().any():
            sd = df.dropna(subset=["steps"])
            fig2 = go.Figure(go.Bar(x=sd["log_date"], y=sd["steps"],
                marker=dict(color=sd["steps"], colorscale=[[0,"#f8d7da"],[0.5,"#fff3cd"],[1,"#d4edda"]],
                            cmin=0, cmax=10000, showscale=False),
                hovertemplate="<b>%{y:,} steps</b><br>%{x|%b %d}<extra></extra>"))
            fig2.add_hline(y=7500, line_dash="dot", line_color="#9e8880",
                           annotation_text="Goal 7,500", annotation_font_size=10)
            fig2.update_layout(**PLOT, height=300, yaxis={**YAXIS}, xaxis={**XAXIS})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No steps data yet")

    # ── Row 2: Meditation | Heatmap ───────────────────────────────────────────────
    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:0 0 .3rem 0;">MEDITATION</p>', unsafe_allow_html=True)
        if "meditation_minutes" in df.columns and df["meditation_minutes"].notna().any():
            md = df[df["meditation_minutes"] > 0].dropna(subset=["meditation_minutes"])
            if not md.empty:
                fig3 = go.Figure(go.Bar(x=md["log_date"], y=md["meditation_minutes"], marker_color="#833ab4",
                    hovertemplate="<b>%{y} min</b><br>%{x|%b %d}<extra></extra>"))
                fig3.update_layout(**PLOT, height=220, yaxis=dict(title="Minutes", gridcolor="#e8ddd6", tickfont=dict(size=11,color="#2c1810")), xaxis={**XAXIS})
                st.plotly_chart(fig3, use_container_width=True)
            streak = 0
            for _, row in df.sort_values("log_date", ascending=False).iterrows():
                if (row.get("meditation_minutes") or 0) > 0: streak += 1
                else: break
            st.markdown(f"""<div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:8px;
                padding:.5rem 1rem;font-size:.84rem;text-align:center;'>
                {'🔥' if streak > 1 else '✨'} <b>Streak: {streak} day{"s" if streak!=1 else ""}</b></div>""",
                unsafe_allow_html=True)
        else:
            st.info("No meditation data yet")

    with c4:
        st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:0 0 .3rem 0;">PAIN BY WEEKDAY</p>', unsafe_allow_html=True)
        if "pain_score" in df.columns and df["pain_score"].notna().any() and len(df) >= 3:
            dh = df.copy()
            dh["log_date_dt"] = pd.to_datetime(dh["log_date"])
            dh["weekday"] = dh["log_date_dt"].dt.day_name()
            dh["week"]    = dh["log_date_dt"].dt.isocalendar().week.astype(str)
            pivot = dh.pivot_table(values="pain_score", index="week", columns="weekday", aggfunc="mean")
            ordered = [d for d in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"] if d in pivot.columns]
            fig4 = px.imshow(pivot.reindex(columns=ordered), aspect="auto",
                             color_continuous_scale=["#d4edda","#fff3cd","#f8d7da","#c62828"],
                             zmin=1, zmax=10, labels=dict(color="Pain"))
            fig4.update_layout(**PLOT, height=200, coloraxis_colorbar=dict(thickness=8, len=0.7))
            st.plotly_chart(fig4, use_container_width=True)
            st.caption("Darker red = higher pain")
        else:
            st.info("Log at least 3 days to see heatmap")

    # ── Row 2b: Exercise ──────────────────────────────────────────────────────────
    st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:.8rem 0 .3rem 0;">EXERCISE & MOVEMENT</p>', unsafe_allow_html=True)

    ex_cols = st.columns([3, 2])
    with ex_cols[0]:
        if "exercise_minutes" in df.columns and df["exercise_minutes"].notna().any():
            ex = df[df["exercise_minutes"] > 0].dropna(subset=["exercise_minutes"]).copy()
            if not ex.empty:
                TYPE_COLORS = {"yoga":"#9c27b0","walking":"#4caf50","running":"#f44336",
                               "stretching":"#2196f3","gym":"#ff9800","swimming":"#00bcd4",
                               "cycling":"#8bc34a","dance":"#e91e63","pilates":"#673ab7"}
                ex["color"] = ex["exercise_type"].map(lambda t: TYPE_COLORS.get(str(t).lower(),"#9e8880"))
                fig_ex = go.Figure()
                for etype, grp in ex.groupby("exercise_type"):
                    color = TYPE_COLORS.get(str(etype).lower(), "#9e8880")
                    icon  = {"yoga":"🧘","walking":"🚶","running":"🏃","stretching":"🤸",
                             "gym":"🏋️","swimming":"🏊","cycling":"🚴","dance":"💃","pilates":"🤸"}.get(str(etype).lower(),"🏃")
                    fig_ex.add_trace(go.Bar(
                        x=grp["log_date"], y=grp["exercise_minutes"],
                        name=f"{icon} {str(etype).title()}",
                        marker_color=color,
                        hovertemplate=f"<b>{str(etype).title()}</b>: %{{y}} min<br>%{{x}}<extra></extra>"
                    ))
                fig_ex.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="DM Sans", color="#2c1810", size=12),
                    margin=dict(l=10, r=10, t=10, b=40),
                    height=240, barmode="stack",
                    legend=dict(orientation="h", y=-0.35, x=0.5, xanchor="center",
                                bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#2c1810")),
                    xaxis=dict(type="category", tickangle=-20, gridcolor="#e8ddd6",
                               tickfont=dict(color="#2c1810"), linecolor="#e8ddd6"),
                    yaxis=dict(title="Minutes", gridcolor="#e8ddd6", tickfont=dict(color="#2c1810")),
                )
                st.plotly_chart(fig_ex, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No exercise logged yet — send '30 min yoga' or '20 min walk' on WhatsApp")

    with ex_cols[1]:
        # Exercise stats summary
        if "exercise_minutes" in df.columns and df["exercise_minutes"].notna().any():
            ex_days  = int((df["exercise_minutes"] > 0).sum())
            ex_total = int(df["exercise_minutes"].sum())
            ex_avg   = round(df[df["exercise_minutes"] > 0]["exercise_minutes"].mean())
            types    = df["exercise_type"].dropna().value_counts()

            st.markdown(f"""
            <div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:10px;padding:.8rem 1rem;'>
              <div style='font-size:.72rem;color:#9e8880;margin-bottom:.5rem;font-weight:600;'>MOVEMENT SUMMARY</div>
              <div style='font-size:.85rem;margin-bottom:.25rem;'>🗓️ <b>{ex_days}</b> active days</div>
              <div style='font-size:.85rem;margin-bottom:.25rem;'>⏱️ <b>{ex_total}</b> min total</div>
              <div style='font-size:.85rem;margin-bottom:.5rem;'>📊 <b>{ex_avg}</b> min avg/session</div>
              <div style='font-size:.72rem;color:#9e8880;margin-bottom:.3rem;font-weight:600;'>MOST LOGGED</div>
              {"".join(f"<div style='font-size:.8rem;'>{'🧘' if t=='yoga' else '🚶' if t=='walking' else '🤸' if t=='stretching' else '🏃'} {t.title()}: {c}x</div>" for t,c in types.head(3).items())}
            </div>""", unsafe_allow_html=True)

            # Phase-appropriate exercise tip
            if "on_period" in df.columns:
                recent_period = df[df["on_period"]==1]["log_date"].max()
                if recent_period:
                    from datetime import date as _date
                    days_since_period = (pd.Timestamp(_date.today()) - pd.Timestamp(recent_period)).days
                    if days_since_period <= 7:
                        tip = "🧘 Period phase: gentle yoga & stretching only"
                    elif days_since_period <= 14:
                        tip = "🌱 Follicular: ramp up — walks, light yoga"
                    elif days_since_period <= 21:
                        tip = "🥚 Ovulatory: peak strength! Run, gym, vinyasa"
                    else:
                        tip = "🌙 Luteal/PMS: moderate — yoga, pilates, walks"
                    st.markdown(f"""
                    <div style='background:#f3e5f5;border:1px solid #ce93d8;border-radius:8px;
                         padding:.6rem .9rem;margin-top:.5rem;font-size:.78rem;'>
                      {tip}
                    </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background:#f8f3ef;border:1px solid #e8ddd6;border-radius:10px;padding:.8rem 1rem;font-size:.8rem;'>
              <b>How to log exercise:</b><br><br>
              WhatsApp: <i>"30 min yoga"</i><br>
              or <i>"walked 45 min"</i><br>
              or use the sidebar form above 👆
            </div>""", unsafe_allow_html=True)

        # ── Row 3: Medicines | Herbal ─────────────────────────────────────────────────
        c5, c6 = st.columns(2)
        with c5:
            st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:0 0 .3rem 0;">MEDICINE USAGE</p>', unsafe_allow_html=True)
            all_meds = []
            if "medicines" in df.columns:
                for lst in df["medicines"].dropna():
                    if isinstance(lst, list): all_meds.extend([m.strip().lower() for m in lst if m.strip()])
            if all_meds:
                counts = pd.Series(all_meds).value_counts().head(7)
                fig5 = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h",
                    marker_color="#c0392b", hovertemplate="<b>%{y}</b>: %{x} times<extra></extra>"))
                fig5.update_layout(**PLOT, height=200, xaxis=dict(title="Times used", gridcolor="#f0e8e0"),
                                   yaxis=dict(gridcolor="rgba(0,0,0,0)"))
                st.plotly_chart(fig5, use_container_width=True)
            else:
                st.info("No medicine data yet")

        with c6:
            st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:0 0 .3rem 0;">HERBAL DRINKS</p>', unsafe_allow_html=True)
            all_drinks = []
            if "herbal_drinks" in df.columns:
                for lst in df["herbal_drinks"].dropna():
                    if isinstance(lst, list): all_drinks.extend([d.strip().lower() for d in lst if d.strip()])
            if all_drinks:
                counts = pd.Series(all_drinks).value_counts().head(7)
                pie_colors = ["#fce4ec","#f8bbd0","#f48fb1","#f06292","#ec407a","#e91e63","#c2185b"]
                fig6 = go.Figure(go.Pie(values=counts.values, labels=counts.index,
                    marker=dict(colors=pie_colors[:len(counts)]), hole=0.4,
                    textinfo="percent", textfont=dict(size=12),
                    hovertemplate="<b>%{label}</b>: %{value} times<extra></extra>",
                    showlegend=True))
                pie_plot = {k: v for k, v in PLOT.items() if k not in ("legend", "margin")}
                fig6.update_layout(
                    **pie_plot, height=240,
                    margin=dict(l=0, r=100, t=10, b=10),
                    legend=dict(
                        orientation="v", x=1.02, y=0.5, xanchor="left",
                        font=dict(size=11, color="#2c1810"),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                )
                st.plotly_chart(fig6, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("No herbal drinks logged yet")

        # ── Pattern insights ──────────────────────────────────────────────────────────
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        st.markdown('<p style="font-size:.82rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:0 0 .5rem 0;">PATTERN INSIGHTS</p>', unsafe_allow_html=True)

        def card(icon, label, v1, v2, note, good=True):
            border = "#2e7d32" if good else "#c0392b"
            return f"""<div style='background:#ffffff;border:1px solid #e8ddd6;border-left:3px solid {border};
                border-radius:10px;padding:.85rem 1rem;font-size:.83rem;'>
              <div style='font-size:.73rem;color:#9e8880;margin-bottom:.3rem;'>{icon} {label}</div>
              <div style='display:flex;gap:.8rem;align-items:baseline;margin-bottom:.25rem;'>
                <b>{v1}</b><span style='color:#9e8880;font-size:.78rem;'>vs</span><b>{v2}</b>
              </div>
              <div style='color:#9e8880;font-size:.75rem;font-style:italic;'>{note}</div></div>"""

        ic1, ic2, ic3 = st.columns(3)
        with ic1:
            if "meditation_minutes" in df.columns and "pain_score" in df.columns:
                m_yes = df[df["meditation_minutes"] > 0]["pain_score"].dropna()
                m_no  = df[(df["meditation_minutes"].isna())|(df["meditation_minutes"]==0)]["pain_score"].dropna()
                if not m_yes.empty and not m_no.empty:
                    diff = round(m_no.mean() - m_yes.mean(), 1)
                    st.markdown(card("🧘","Pain: meditated vs not",
                        f"{m_yes.mean():.1f}/10",f"{m_no.mean():.1f}/10",
                        f"↓ {diff} pts lower on meditation days" if diff>0 else "Keep logging to see pattern",
                        good=diff>0), unsafe_allow_html=True)

        with ic2:
            if "steps" in df.columns and "pain_score" in df.columns:
                act = df[df["steps"]>=7000]["pain_score"].dropna()
                les = df[(df["steps"]<7000)&df["steps"].notna()]["pain_score"].dropna()
                if not act.empty and not les.empty:
                    diff = round(les.mean()-act.mean(), 1)
                    st.markdown(card("👣","Pain: 7k+ steps vs fewer",
                        f"{act.mean():.1f}/10",f"{les.mean():.1f}/10",
                        f"↓ {diff} pts lower on active days" if diff>0 else "No clear link yet",
                        good=diff>0), unsafe_allow_html=True)

        with ic3:
            if "on_period" in df.columns and "mood_score" in df.columns:
                pm  = df[df["on_period"]==1]["mood_score"].dropna()
                npm = df[df["on_period"]!=1]["mood_score"].dropna()
                if not pm.empty and not npm.empty:
                    diff = round(npm.mean()-pm.mean(), 1)
                    st.markdown(card("🩸","Mood: period vs non-period",
                        f"{pm.mean():.1f}/10",f"{npm.mean():.1f}/10",
                        f"↓ {diff} pts lower during period" if diff>0 else "Stable mood across cycle 💪",
                        good=diff<=0), unsafe_allow_html=True)

        # ── Nutrition Section ──────────────────────────────────────────────────────
        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        st.markdown('<p style="font-size:.78rem;font-weight:600;color:#9e8880;letter-spacing:.05em;margin:.8rem 0 .3rem 0;">NUTRITION TRACKING</p>', unsafe_allow_html=True)

        # ── User Profile — saved to file so it persists across reloads ─────────
        import json as _json
        _PROFILE_PATH = _REPO_ROOT / "data" / "user_profile.json"
        _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _profile = {}
        if _PROFILE_PATH.exists():
            try: _profile = _json.loads(_PROFILE_PATH.read_text())
            except: _profile = {}

        _ACTIVITY_OPTS = ["Sedentary (desk job)", "Light (1-3x/week)", "Moderate (3-5x/week)", "Active (6-7x/week)"]
        with st.expander("⚙️ Set your profile for accurate nutrition goals", expanded=not bool(_profile)):
            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1:
                weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=150.0,
                    value=float(_profile.get("weight_kg", 58.0)), step=0.5, key="inp_weight")
            with pc2:
                height_cm = st.number_input("Height (cm)", min_value=130.0, max_value=200.0,
                    value=float(_profile.get("height_cm", 160.0)), step=0.5, key="inp_height")
            with pc3:
                age = st.number_input("Age", min_value=15, max_value=60,
                    value=int(_profile.get("age", 28)), step=1, key="inp_age")
            with pc4:
                activity = st.selectbox("Activity level", _ACTIVITY_OPTS,
                    index=int(_profile.get("activity_idx", 1)), key="inp_activity")
            if st.button("Save profile", key="save_profile"):
                _profile = {
                    "weight_kg":    weight_kg,
                    "height_cm":    height_cm,
                    "age":          age,
                    "activity_idx": _ACTIVITY_OPTS.index(activity),
                }
                _PROFILE_PATH.write_text(_json.dumps(_profile))
                st.success("✅ Profile saved! Goals updated.")
                st.rerun()

        # Calculate BMR → TDEE using Mifflin-St Jeor (from saved profile)
        _w  = float(_profile.get("weight_kg", 58.0))
        _h  = float(_profile.get("height_cm", 160.0))
        _a  = int(_profile.get("age", 28))
        _ai = int(_profile.get("activity_idx", 1))
        _bmr = 10 * _w + 6.25 * _h - 5 * _a - 161  # Mifflin-St Jeor for women
        _activity_multipliers = [1.2, 1.375, 1.55, 1.725]
        _tdee = _bmr * _activity_multipliers[_ai]
        # For endo: slight deficit recommended to reduce estrogen
        cal_rda  = round(_tdee * 0.95 / 50) * 50  # round to nearest 50
        prot_rda = round(_w * 1.2)   # 1.2g per kg for endo (higher than normal)
        iron_rda = 18.0              # mg/day (higher on period days ideally 27mg)
        fiber_rda = 30               # g/day (higher fiber for estrogen elimination)

        # Always load fresh for nutrition — bypasses cache to show latest log
        _fresh_logs = get_logs(days=days_range)
        _fresh_df   = pd.DataFrame(_fresh_logs) if _fresh_logs else pd.DataFrame()
        nutr_cols_present = "nutrition_calories" in _fresh_df.columns and _fresh_df["nutrition_calories"].notna().any()
        if nutr_cols_present:
            df = _fresh_df  # update df so nutrition charts use fresh data too

        if not nutr_cols_present:
            st.markdown(f"""
            <div style='background:#f8f3ef;border:1px dashed #c9b8b0;border-radius:10px;
                 padding:1rem 1.2rem;font-size:.83rem;color:#7a5c55;text-align:center;'>
              📊 Nutrition data appears after your next WhatsApp log.<br>
              Log meals naturally — <i>"ate dal rice, sabji, ginger tea"</i> — and AI estimates your nutrition.<br>
              <span style='font-size:.75rem;'>Your calorie goal: <b>{cal_rda} kcal/day</b> based on your profile</span>
            </div>""", unsafe_allow_html=True)
        else:
            ndf = df.copy()
            for nc in ["nutrition_calories","nutrition_protein_g","nutrition_carbs_g",
                       "nutrition_fat_g","nutrition_fiber_g","nutrition_iron_mg"]:
                if nc not in ndf.columns:
                    ndf[nc] = None

            ndf_clean = ndf[ndf["nutrition_calories"].notna()].copy()

            if not ndf_clean.empty:
                # Summary cards — now using real calculated goals
                avg_cal    = round(ndf_clean["nutrition_calories"].mean())
                avg_prot   = round(ndf_clean["nutrition_protein_g"].mean(), 1) if "nutrition_protein_g" in ndf_clean else 0
                avg_iron   = round(ndf_clean["nutrition_iron_mg"].mean(), 1) if "nutrition_iron_mg" in ndf_clean else 0
                avg_fiber  = round(ndf_clean["nutrition_fiber_g"].mean(), 1) if "nutrition_fiber_g" in ndf_clean else 0

                nc1, nc2, nc3, nc4 = st.columns(4)
                def nutr_card(col, emoji, label, val, unit, target=None, lower_better=False):
                    if target:
                        pct     = int((val / target) * 100)
                        bar_pct = min(pct, 100)
                        ok      = 80 <= pct <= 115
                        over    = pct > 115
                        bar_col = "#e8857a" if over else ("#7cb69b" if ok else "#e8a87a")
                        bar  = f"<div style='height:4px;background:#e8ddd6;border-radius:2px;margin-top:4px;'><div style='width:{bar_pct}%;height:4px;background:{bar_col};border-radius:2px;'></div></div>"
                        sub  = f"{pct}% of goal{'  ⚠️ over' if over else ''}"
                    else:
                        bar  = ""
                        sub  = unit
                    col.markdown(f"""
                    <div style='background:#fff8f5;border:1px solid #e8ddd6;border-radius:10px;padding:.7rem .8rem;'>
                      <div style='font-size:.75rem;color:#9e8880;'>{emoji} {label}</div>
                      <div style='font-size:1.3rem;font-weight:700;color:#2c1810;'>{val}<span style='font-size:.75rem;font-weight:400;color:#7a5c55;'> {unit}</span></div>
                      <div style='font-size:.7rem;color:#9e8880;'>{sub}</div>
                      {bar}
                    </div>""", unsafe_allow_html=True)

                nutr_card(nc1, "🔥", "Avg Calories", avg_cal, "kcal", cal_rda)
                nutr_card(nc2, "💪", "Avg Protein",  avg_prot, "g", prot_rda)
                nutr_card(nc3, "🩸", "Avg Iron",     avg_iron, "mg", iron_rda)
                nutr_card(nc4, "🌾", "Avg Fiber",    avg_fiber, "g", fiber_rda)

                st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

                # Calories over time
                if len(ndf_clean) >= 2:
                    import plotly.graph_objects as go
                    ndf_plot = ndf_clean.sort_values("log_date")
                    fig_n = go.Figure()
                    fig_n.add_trace(go.Bar(
                        x=ndf_plot["log_date"].astype(str),
                        y=ndf_plot["nutrition_calories"],
                        marker_color="#d4956a",
                        name="Calories",
                    ))
                    fig_n.add_hline(y=cal_rda, line_dash="dot",
                                    line_color="#9e8880", annotation_text=f"goal {cal_rda} kcal")
                    fig_n.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="DM Sans", color="#2c1810", size=11),
                        margin=dict(l=10, r=10, t=20, b=40), height=180,
                        xaxis=dict(type="category", tickangle=-25,
                                   tickfont=dict(color="#2c1810"), gridcolor="#e8ddd6"),
                        yaxis=dict(tickfont=dict(color="#2c1810"), gridcolor="#e8ddd6"),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_n, use_container_width=True, config={"displayModeBar": False})
                    st.caption("Estimated daily calories from your WhatsApp food logs")

                # Iron vs goal highlight
                if avg_iron > 0:
                    pct_iron = round((avg_iron / iron_rda) * 100)
                    if pct_iron < 80:
                        st.markdown(f"""
                        <div style='background:#fff3e0;border:1px solid #ffcc80;border-radius:8px;
                             padding:.7rem 1rem;font-size:.82rem;'>
                          🩸 <b>Iron tracking:</b> You're averaging {avg_iron}mg/day —
                          {pct_iron}% of the 18mg daily goal for women with endo.
                          Iron-rich Indian foods: rajma, palak, ragi, chana, til (sesame).
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;
                             padding:.7rem 1rem;font-size:.82rem;'>
                          🩸 <b>Iron:</b> Great — averaging {avg_iron}mg/day ({pct_iron}% of goal) ✅
                        </div>""", unsafe_allow_html=True)

        # ── Raw table ─────────────────────────────────────────────────────────────────
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        with st.expander("📋 View all entries"):
            col_map = {"log_date":"Date","pain_score":"Pain","mood_score":"Mood","energy_score":"Energy",
                       "steps":"Steps","meditation_minutes":"Meditation (min)","sleep_hours":"Sleep (hrs)",
                       "on_period":"Period","cycle_day":"Cycle Day","notes":"Notes"}
            avail = {k:v for k,v in col_map.items() if k in df.columns}
            disp  = df[list(avail.keys())].sort_values("log_date",ascending=False).rename(columns=avail).head(60)
            # log_date already a string
            st.markdown(html_table(disp), unsafe_allow_html=True)


with tab2:
    # ─────────────────────────────────────────────────────────────────────────
    # CYCLE TRACKER TAB
    # ─────────────────────────────────────────────────────────────────────────
    import calendar as cal_mod
    from datetime import date, timedelta

    st.markdown("""
    <div style='background:#ffffff;border:1px solid #e8ddd6;border-radius:10px;
         padding:1rem 1.4rem;margin-bottom:1rem;'>
      <p style='font-size:.75rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:0 0 .4rem 0;'>
        🩸 HOW TO LOG YOUR CYCLE
      </p>
      <span style='font-size:.82rem;'>WhatsApp: <b>"period day 1"</b> or <b>"period day 3"</b> in your daily message.
      The tracker builds your cycle history automatically.</span>
    </div>""", unsafe_allow_html=True)

    # ── Pull all logs (up to 6 months) for cycle analysis ────────────────────
    all_logs  = get_logs(days=180)
    all_df    = pd.DataFrame(all_logs) if all_logs else pd.DataFrame()

    if not all_df.empty and "on_period" in all_df.columns:
        all_df["log_date"] = pd.to_datetime(all_df["log_date"])
        all_df = all_df.sort_values("log_date")
        period_df = all_df[all_df["on_period"] == 1].copy()
    else:
        period_df = pd.DataFrame()

    # ── Cycle analysis ────────────────────────────────────────────────────────
    def analyse_cycles(period_df):
        """Find cycle start dates and calculate lengths."""
        if period_df.empty:
            return [], []
        dates = sorted(period_df["log_date"].dt.date.tolist())
        # Group consecutive period days into one period
        cycles = []
        current = [dates[0]]
        for d in dates[1:]:
            if (d - current[-1]).days <= 2:  # same period (gap ≤ 2 days)
                current.append(d)
            else:
                cycles.append(current)
                current = [d]
        cycles.append(current)
        # Start date = first day of each period
        starts = [c[0] for c in cycles]
        lengths = [(starts[i+1] - starts[i]).days for i in range(len(starts)-1)]
        return starts, lengths

    starts, lengths = analyse_cycles(period_df)
    avg_cycle  = round(sum(lengths)/len(lengths)) if lengths else 28
    last_start = starts[-1] if starts else None

    # ── Cycle stats cards ─────────────────────────────────────────────────────
    today = date.today()

    if last_start:
        days_since = (today - last_start).days
        next_period = last_start + timedelta(days=avg_cycle)
        days_to_next = (next_period - today).days
        ovulation_date = last_start + timedelta(days=avg_cycle - 14)
        days_to_ovul = (ovulation_date - today).days
        pms_start = next_period - timedelta(days=5)
        in_pms = pms_start <= today < next_period
        in_period = 0 <= days_since <= 7
        endo_risk = in_period or in_pms  # simplified risk flag
    else:
        days_since = None
        next_period = None
        days_to_next = None
        ovulation_date = None
        days_to_ovul = None
        in_pms = False
        in_period = False
        endo_risk = False

    # ── Status banner ─────────────────────────────────────────────────────────
    if in_period:
        banner_color = "#fce4ec"
        banner_border = "#e91e63"
        banner_text = f"🩸 <b>Currently on period</b> — Day {days_since + 1}"
        banner_note = "Rest well, stay warm, keep logging"
    elif in_pms:
        banner_color = "#fff3e0"
        banner_border = "#ff9800"
        banner_text = f"⚠️ <b>PMS window</b> — period expected in {days_to_next} days"
        banner_note = "Watch for bloating, mood changes, breast tenderness"
    elif days_to_next is not None and days_to_next <= 3:
        banner_color = "#fce4ec"
        banner_border = "#c0392b"
        banner_text = f"🔔 <b>Period due soon</b> — in {days_to_next} days"
        banner_note = "Prepare your heating pad, mefenamic acid, and herbal teas"
    elif days_to_ovul is not None and 0 <= days_to_ovul <= 2:
        banner_color = "#e8f5e9"
        banner_border = "#4caf50"
        banner_text = f"🥚 <b>Ovulation window</b> — today or in {days_to_ovul} days"
        banner_note = "Energy typically peaks around ovulation"
    else:
        banner_color = "#f3e5f5"
        banner_border = "#9c27b0"
        if days_to_next is not None:
            banner_text = f"💜 <b>Cycle day {days_since + 1}</b> — next period in {days_to_next} days"
        else:
            banner_text = "💜 <b>Log your period days to activate cycle tracking</b>"
        banner_note = "Send 'period day 1' on WhatsApp when your period starts"

    st.markdown(f"""
    <div style='background:{banner_color};border:1px solid {banner_border};border-left:4px solid {banner_border};
         border-radius:10px;padding:1rem 1.4rem;margin-bottom:1.2rem;'>
      <div style='font-size:.95rem;margin-bottom:.3rem;'>{banner_text}</div>
      <div style='font-size:.78rem;color:#5a3e35;font-style:italic;'>{banner_note}</div>
    </div>""", unsafe_allow_html=True)

    # ── 4 key stats ───────────────────────────────────────────────────────────
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("📅 Avg cycle length",
               f"{avg_cycle} days" if lengths else "—",
               help="Typical endometriosis cycle: 21–35 days")
    cc2.metric("🩸 Periods tracked",
               len(starts),
               help="Based on your logged period days")
    cc3.metric("📆 Next period",
               next_period.strftime("%b %d") if next_period else "—",
               delta=f"in {days_to_next}d" if days_to_next and days_to_next > 0 else ("today" if days_to_next == 0 else None))
    cc4.metric("🥚 Ovulation est.",
               ovulation_date.strftime("%b %d") if ovulation_date else "—",
               help="Estimated as cycle day " + str(avg_cycle - 14))

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    # ── Calendar view ─────────────────────────────────────────────────────────
    st.markdown('<p style="font-size:.82rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:0 0 .5rem 0;">CALENDAR</p>', unsafe_allow_html=True)

    # Build sets of special dates
    period_dates   = set(period_df["log_date"].dt.date.tolist()) if not period_df.empty else set()
    ovul_dates     = set()
    pms_dates      = set()
    flare_dates    = set()

    for s in starts:
        # Ovulation window: cycle_len - 14 ± 1 day
        for d in range(-1, 2):
            ovul_dates.add(s + timedelta(days=avg_cycle - 14 + d))
        # PMS window: 5 days before next period
        for d in range(5):
            pms_dates.add(s + timedelta(days=avg_cycle - 5 + d))
        # Endo flare risk: period days + 2 days after
        for d in range(9):
            flare_dates.add(s + timedelta(days=d))

    # Show current month calendar
    month_options = {date(today.year, m, 1).strftime("%B %Y"): (today.year, m) for m in range(1, 13)}
    selected_month_label = st.selectbox(
        "Select month", 
        options=list(month_options.keys()),
        index=today.month - 1,
    )
    yr, mo = month_options[selected_month_label]

    cal_days = cal_mod.monthcalendar(yr, mo)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Build HTML calendar
    html = """
    <style>
    .cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; max-width:560px; }
    .cal-header { text-align:center; font-size:.72rem; font-weight:600; color:#9e8880;
                  padding:.3rem 0; letter-spacing:.04em; }
    .cal-day { border-radius:8px; padding:.4rem .2rem; text-align:center;
               font-size:.82rem; font-weight:500; color:#2c1810;
               background:#f8f3ef; min-height:38px; display:flex;
               flex-direction:column; align-items:center; justify-content:center; }
    .cal-empty { background:transparent; }
    .cal-today { border:2px solid #9c27b0; font-weight:700; }
    .cal-period { background:#fce4ec; color:#c0392b; font-weight:700; }
    .cal-ovul   { background:#e8f5e9; color:#2e7d32; }
    .cal-pms    { background:#fff3e0; color:#e65100; }
    .cal-flare  { background:#fce4ec; }
    .cal-dot    { font-size:.5rem; margin-top:1px; }
    </style>
    <div class="cal-grid">
    """
    for d in day_names:
        html += f'<div class="cal-header">{d}</div>'

    for week in cal_days:
        for day_num in week:
            if day_num == 0:
                html += '<div class="cal-day cal-empty"></div>'
                continue
            d = date(yr, mo, day_num)
            classes = ["cal-day"]
            dots    = []
            if d == today:         classes.append("cal-today")
            if d in period_dates:  classes.append("cal-period"); dots.append("🩸")
            elif d in ovul_dates:  classes.append("cal-ovul");   dots.append("🥚")
            elif d in pms_dates:   classes.append("cal-pms");    dots.append("⚠️")
            elif d in flare_dates: classes.append("cal-flare");  dots.append("💜")
            dot_html = f'<div class="cal-dot">{"".join(dots)}</div>' if dots else ""
            html += f'<div class="{" ".join(classes)}">{day_num}{dot_html}</div>'

    html += '</div>'
    html += """
    <div style='margin-top:.8rem;display:flex;gap:1.2rem;flex-wrap:wrap;font-size:.75rem;'>
      <span>🩸 Period</span>
      <span>🥚 Ovulation</span>
      <span>⚠️ PMS window</span>
      <span>💜 Endo flare risk</span>
      <span style='border:2px solid #9c27b0;border-radius:4px;padding:0 4px;'>Today</span>
    </div>"""

    st.markdown(html, unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Cycle length chart ────────────────────────────────────────────────────
    if len(lengths) >= 1:
        st.markdown('<p style="font-size:.82rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:.8rem 0 .4rem 0;">CYCLE LENGTH HISTORY</p>', unsafe_allow_html=True)
        cycle_labels = [f"Cycle {i+1}" for i in range(len(lengths))]
        fig_cyc = go.Figure(go.Bar(
            x=cycle_labels, y=lengths,
            marker_color=["#f48fb1" if l < 25 or l > 35 else "#ce93d8" for l in lengths],
            hovertemplate="<b>%{x}</b>: %{y} days<extra></extra>",
            text=lengths, textposition="outside",
        ))
        fig_cyc.add_hline(y=avg_cycle, line_dash="dot", line_color="#9e8880",
                          annotation_text=f"Your avg: {avg_cycle}d", annotation_font_size=10)
        fig_cyc.add_hrect(y0=21, y1=35, fillcolor="rgba(200,230,200,0.15)", line_width=0)
        fig_cyc.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#2c1810", size=12),
            margin=dict(l=10, r=10, t=30, b=10),
            height=220,
            yaxis=dict(title="Days", range=[0, max(lengths)+8], gridcolor="#e8ddd6",
                       tickfont=dict(color="#2c1810")),
            xaxis=dict(gridcolor="#e8ddd6", tickfont=dict(color="#2c1810")),
            showlegend=False,
        )
        st.plotly_chart(fig_cyc, use_container_width=True, config={"displayModeBar": False})
        st.caption("Green band = typical range (21–35 days) · Pink bars = outside typical range")

    # ── Endo flare risk prediction ────────────────────────────────────────────
    st.markdown('<p style="font-size:.82rem;font-weight:600;color:#9e8880;letter-spacing:.06em;margin:.8rem 0 .4rem 0;">ENDO FLARE RISK — NEXT 30 DAYS</p>', unsafe_allow_html=True)

    if next_period:
        risk_rows = []
        for i in range(30):
            d = today + timedelta(days=i)
            if d in period_dates or (last_start and (d - last_start).days < 8):
                risk = "🔴 High"
            elif d in pms_dates:
                risk = "🟠 Moderate"
            elif d in ovul_dates:
                risk = "🟡 Watch"
            else:
                risk = "🟢 Low"
            risk_rows.append({"Date": d.strftime("%b %d"), "Phase": _phase(d, last_start, avg_cycle, next_period, period_dates, ovul_dates, pms_dates), "Risk": risk})

        risk_df = pd.DataFrame(risk_rows)

        # Show as colour-coded cards for next 14 days
        cols = st.columns(7)
        for i in range(14):
            d   = today + timedelta(days=i)
            row = risk_rows[i]
            col = cols[i % 7]
            bg  = {"🔴 High": "#fce4ec", "🟠 Moderate": "#fff3e0",
                   "🟡 Watch": "#fffde7", "🟢 Low": "#f1f8e9"}.get(row["Risk"], "#f8f3ef")
            col.markdown(f"""
            <div style='background:{bg};border-radius:8px;padding:.4rem .3rem;
                 text-align:center;font-size:.72rem;margin-bottom:4px;'>
              <div style='font-weight:600;'>{d.strftime("%b %d")}</div>
              <div style='font-size:.65rem;color:#5a3e35;'>{row["Phase"]}</div>
              <div>{row["Risk"].split()[0]}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("Log at least one period (send 'period day 1' on WhatsApp) to see flare risk predictions")

    # ── WhatsApp cycle notifications tip ─────────────────────────────────────
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='background:#f3e5f5;border:1px solid #ce93d8;border-radius:10px;
         padding:.9rem 1.2rem;font-size:.82rem;'>
      💡 <b>Tip:</b> Text <b>"weekly"</b> to your WhatsApp bot on PMS days —
      the AI report will include extra endometriosis-specific advice for that phase of your cycle.
    </div>""", unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: LOG HISTORY
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    try:
        from app.daily_log_db import get_insights, init_insight_log_table, delete_log
        init_insight_log_table()
        insight_logs = get_insights(days=90)
    except Exception as e:
        st.error(f"Could not load insights: {e}")
        insight_logs = []

    insight_by_date = {}
    for ins in insight_logs:
        d = str(ins.get("log_date", ""))[:10]
        insight_by_date.setdefault(d, []).append(ins)

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        hist_days = st.selectbox("Show last", [7, 14, 30, 60, 90], index=1, key="ht_hist_days")
    with fc2:
        hist_view = st.selectbox("View", ["Combined", "Daily Logs", "AI Replies"], key="ht_hist_view")
    with fc3:
        hist_search = st.text_input("🔍 Search", placeholder="pain, dal rice, yoga…", key="ht_hist_search")

    # Reload logs with filter
    try:
        from app.daily_log_db import get_logs
        hist_logs = get_logs(days=hist_days)
        hist_insights = get_insights(days=hist_days)
    except:
        hist_logs = []
        hist_insights = []

    if hist_search:
        q = hist_search.lower()
        hist_logs = [l for l in hist_logs if
            q in str(l.get("raw_message","")).lower() or
            q in str(l.get("meals","")).lower() or
            q in str(l.get("notes","")).lower()]
        hist_insights = [i for i in hist_insights if
            q in str(i.get("user_message","")).lower() or
            q in str(i.get("ai_reply","")).lower()]

    hist_insight_by_date = {}
    for ins in hist_insights:
        d = str(ins.get("log_date",""))[:10]
        hist_insight_by_date.setdefault(d, []).append(ins)

    CARD  = "background:#ffffff;border:1px solid #e8ddd6;border-radius:12px;padding:1rem 1.2rem;margin-bottom:.8rem;"
    UBOX  = "background:#f0f4ff;border-left:3px solid #90a4d4;border-radius:0 8px 8px 0;padding:.6rem .9rem;font-size:.83rem;color:#2c1810;white-space:pre-wrap;word-break:break-word;"
    AIBOX = "background:#f8f3ef;border-left:3px solid #c9a882;border-radius:0 8px 8px 0;padding:.6rem .9rem;font-size:.83rem;color:#2c1810;white-space:pre-wrap;word-break:break-word;"

    if not hist_logs and not hist_insights:
        st.info("No logs yet for this period. Send a WhatsApp message to start tracking!")
    
    # ── COMBINED VIEW ─────────────────────────────────────────────────────────
    elif hist_view == "Combined":
        for log in hist_logs:
            d = str(log.get("log_date",""))[:10]
            pain   = log.get("pain_score")
            mood   = log.get("mood_score")
            energy = log.get("energy_score")
            steps  = log.get("steps")

            metrics = []
            if pain   is not None: metrics.append(f"{'🔴' if pain>=7 else '🟡' if pain>=4 else '🟢'} Pain {pain}/10")
            if mood   is not None: metrics.append(f"😊 Mood {mood}/10")
            if energy is not None: metrics.append(f"⚡ Energy {energy}/10")
            if steps  is not None: metrics.append(f"👣 {int(steps):,}")

            cal  = log.get("nutrition_calories")
            nutr_str = f"🔥 {int(cal)} kcal" if cal else ""
            if nutr_str and log.get("nutrition_protein_g"):
                nutr_str += f"  💪 {log['nutrition_protein_g']:.0f}g protein"

            raw = log.get("raw_message","")
            if " | " in raw: raw = raw.split(" | ")[0]
            day_insights = hist_insight_by_date.get(d, [])
            is_today = (d == str(__import__("datetime").date.today()))

            with st.expander(f"**{d}** · {' · '.join(metrics[:3])}", expanded=is_today):
                left, right = st.columns([1, 1])
                with left:
                    st.markdown("**📝 You logged:**")
                    st.markdown(f"<div style='{UBOX}'>{raw[:400] if raw else '(no message saved)'}</div>", unsafe_allow_html=True)
                    if nutr_str: st.caption(nutr_str)
                    meals  = log.get("meals") or []
                    herbal = log.get("herbal_drinks") or []
                    if meals:  st.caption(f"🍽️ {', '.join(meals[:4])}")
                    if herbal: st.caption(f"🍵 {', '.join(herbal[:3])}")
                    if log.get("sleep_hours"): st.caption(f"😴 {log['sleep_hours']} hrs sleep")

                with right:
                    if day_insights:
                        for ins in day_insights:
                            itype = ins.get("insight_type","daily")
                            badge_bg = {"daily":"#e8f5e9","weekly":"#e3f2fd"}.get(itype,"#f8f3ef")
                            badge_co = {"daily":"#2e7d32","weekly":"#1565c0"}.get(itype,"#5a3e35")
                            st.markdown(
                                f"**🌿 AI reply** "
                                f"<span style='background:{badge_bg};color:{badge_co};font-size:.7rem;"
                                f"font-weight:600;padding:.1rem .5rem;border-radius:10px;'>{itype.upper()}</span>",
                                unsafe_allow_html=True
                            )
                            ai_clean = ins.get("ai_reply","").replace("*","").replace("_","")
                            st.markdown(f"<div style='{AIBOX}'>{ai_clean[:1200]}{'…' if len(ai_clean)>1200 else ''}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='color:#9e8880;font-size:.83rem;padding:.6rem;'>💬 No AI reply saved for this entry.</div>", unsafe_allow_html=True)

                # Delete
                if st.button("🗑️ Delete entry", key=f"ht_del_{d}", type="secondary"):
                    st.session_state[f"ht_confirm_{d}"] = True
                if st.session_state.get(f"ht_confirm_{d}"):
                    st.warning(f"Permanently delete **{d}**?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Yes delete", key=f"ht_yes_{d}", type="primary"):
                            delete_log(d)
                            st.session_state.pop(f"ht_confirm_{d}", None)
                            st.session_state["db_version"] = st.session_state.get("db_version", 0) + 1
                            st.success(f"Deleted {d}")
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancel", key=f"ht_cancel_{d}"):
                            st.session_state.pop(f"ht_confirm_{d}", None)
                            st.rerun()

    # ── DAILY LOGS TABLE ──────────────────────────────────────────────────────
    elif hist_view == "Daily Logs":
        if not hist_logs:
            st.info("No logs found.")
        else:
            rows = []
            for l in hist_logs:
                rows.append({
                    "Date":      l.get("log_date","")[:10],
                    "Pain":      l.get("pain_score"),
                    "Mood":      l.get("mood_score"),
                    "Energy":    l.get("energy_score"),
                    "Steps":     int(l["steps"]) if l.get("steps") else None,
                    "Sleep":     l.get("sleep_hours"),
                    "Exercise":  f"{l.get('exercise_type','').title()} {l.get('exercise_minutes','')}min".strip() if l.get("exercise_type") else "",
                    "Period":    "🩸" if l.get("on_period") else "",
                    "Calories":  int(l["nutrition_calories"]) if l.get("nutrition_calories") else None,
                    "Protein g": round(l["nutrition_protein_g"],1) if l.get("nutrition_protein_g") else None,
                    "Iron mg":   round(l["nutrition_iron_mg"],1) if l.get("nutrition_iron_mg") else None,
                })
            df_hist = pd.DataFrame(rows)
            st.markdown(html_table(df_hist), unsafe_allow_html=True)
            st.download_button("⬇️ Download CSV", df_hist.to_csv(index=False),
                               "health_log.csv", "text/csv")

            st.markdown("---")
            del_date = st.selectbox("🗑️ Delete entry", 
                ["— select —"] + [r["Date"] for r in rows], key="ht_del_select")
            if del_date != "— select —":
                st.warning(f"This permanently deletes **{del_date}** from the database.")
                if st.button("Confirm delete", key="ht_confirm_del", type="primary"):
                    delete_log(del_date)
                    st.session_state["db_version"] = st.session_state.get("db_version", 0) + 1
                    st.success(f"✅ Deleted {del_date}")
                    st.rerun()

    # ── AI REPLIES ────────────────────────────────────────────────────────────
    else:
        if not hist_insights:
            st.info("No AI replies yet. Send a WhatsApp health log to get your first insight!")
        else:
            for ins in hist_insights:
                itype    = ins.get("insight_type","daily")
                d        = str(ins.get("log_date",""))[:10]
                ts       = str(ins.get("created_at",""))[:16].replace("T"," ")
                ai_reply = ins.get("ai_reply","").replace("*","").replace("_","")
                badge_bg = {"daily":"#e8f5e9","weekly":"#e3f2fd"}.get(itype,"#f8f3ef")
                badge_co = {"daily":"#2e7d32","weekly":"#1565c0"}.get(itype,"#5a3e35")

                st.markdown(f"""
                <div style='{CARD}'>
                  <div style='font-weight:600;color:#2c1810;margin-bottom:.4rem;'>
                    {d}
                    <span style='background:{badge_bg};color:{badge_co};font-size:.7rem;
                          font-weight:600;padding:.1rem .5rem;border-radius:10px;margin-left:.4rem;'>{itype.upper()}</span>
                    <span style='font-size:.72rem;color:#9e8880;float:right;'>{ts}</span>
                  </div>
                  <div style='{AIBOX}'>{ai_reply[:600]}{'…' if len(ai_reply)>600 else ''}</div>
                </div>""", unsafe_allow_html=True)

            csv_ai = pd.DataFrame([{
                "Date": str(i.get("log_date",""))[:10],
                "Type": i.get("insight_type",""),
                "AI reply": i.get("ai_reply","")[:300],
            } for i in hist_insights]).to_csv(index=False)
            st.download_button("⬇️ Download AI logs CSV", csv_ai, "ai_log.csv", "text/csv")