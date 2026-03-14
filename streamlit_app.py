"""
streamlit_app.py — Endo Research AI
Clean warm theme, CSS injected via components.v1.html into page <head>
"""
import uuid, requests, os, zipfile, io as _io
import streamlit as st
import streamlit.components.v1 as components

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Endometriosis Research AI",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject CSS via components — bypasses Streamlit sanitizer entirely ─────────
components.html("""
<script>
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

  /* Hide Streamlit's auto-generated multipage nav at top of sidebar */
  [data-testid="stSidebarNav"] { display: none !important; }

  html, body, [data-testid="stAppViewContainer"] { background: #fdf6f0 !important; }
  section[data-testid="stMain"] > div { background: #fdf6f0 !important; }
  section[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e8ddd6 !important; }
  header[data-testid="stHeader"] { background: #fdf6f0 !important; }
  [data-testid="stBottom"], [data-testid="stBottom"] > div,
  [data-testid="stBottom"] > div > div { background: #fdf6f0 !important; }

  html, body, p, div, span, label, h1, h2, h3 {
    font-family: 'DM Sans', sans-serif !important;
    color: #2c1810 !important;
  }

  /* Sidebar buttons */
  .stButton > button {
    background: #ffffff !important;
    color: #2c1810 !important;
    border: 1px solid #e8ddd6 !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    text-align: left !important;
    transition: all 0.15s !important;
  }
  .stButton > button:hover {
    border-color: #c0392b !important;
    color: #c0392b !important;
    background: #fff5f5 !important;
  }

  /* Download buttons */
  [data-testid="stDownloadButton"] button {
    background: #ffffff !important;
    color: #2c1810 !important;
    border: 1px solid #e8ddd6 !important;
    border-radius: 8px !important;
    font-size: 0.83rem !important;
    width: 100% !important;
  }

  /* File uploader */
  [data-testid="stFileUploader"] {
    background: #ffffff !important;
    border: 1.5px dashed #e8ddd6 !important;
    border-radius: 10px !important;
  }
  [data-testid="stFileUploader"] section { background: #ffffff !important; }
  [data-testid="stFileUploaderDropzoneInstructions"] div span { color: #9e8880 !important; }
  [data-testid="stFileUploader"] button {
    background: #ffffff !important;
    color: #2c1810 !important;
    border: 1px solid #e8ddd6 !important;
  }

  /* Expanders */
  [data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e8ddd6 !important;
    border-radius: 8px !important;
  }

  /* Select box + text input */
  [data-testid="stSelectbox"] > div > div,
  [data-testid="stTextInput"] input {
    background: #ffffff !important;
    color: #2c1810 !important;
    border: 1px solid #e8ddd6 !important;
  }

  /* Chat input — full override including container */
  [data-testid="stChatInput"] { background: #ffffff !important; }
  [data-testid="stChatInput"] > div { background: #ffffff !important; }
  [data-testid="stChatInputContainer"] { background: #ffffff !important; }
  [data-testid="stChatInputContainer"] > div { background: #ffffff !important; }
  [data-testid="stChatInput"] textarea {
    background: #ffffff !important;
    color: #2c1810 !important;
    border: 1px solid #e8ddd6 !important;
    border-radius: 24px !important;
    font-family: 'DM Sans', sans-serif !important;
  }
  /* Bottom bar that contains chat input */
  [data-testid="stBottom"] { background: #fdf6f0 !important; }
  [data-testid="stBottom"] > div { background: #fdf6f0 !important; }
  [data-testid="stBottom"] > div > div { background: #fdf6f0 !important; }
  [data-testid="stBottom"] > div > div > div { background: #fdf6f0 !important; }
  /* The dark overlay behind chat input */
  .stChatFloatingInputContainer { background: #fdf6f0 !important; }
  section[data-testid="stMain"] [data-testid="stBottom"] {
    background: #fdf6f0 !important;
    border-top: 1px solid #e8ddd6 !important;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #fdf6f0; }
  ::-webkit-scrollbar-thumb { background: #e8ddd6; border-radius: 2px; }
  /* Sidebar session row — main button */
  [data-testid="stSidebar"] .stButton > button {
    font-size: .78rem !important;
    padding: .3rem .6rem !important;
    text-align: left !important;
    border-radius: 6px !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    color: #5a3e35 !important;
    height: 2rem !important;
    min-height: 0 !important;
    line-height: 1.2 !important;
  }
  [data-testid="stSidebar"] .stButton > button:hover {
    background: #f0e8e0 !important;
    border-color: #e8ddd6 !important;
    color: #2c1810 !important;
  }
`;
const style = document.createElement('style');
style.textContent = css;
// Inject into parent frame (the actual Streamlit page)
window.parent.document.head.appendChild(style);
</script>
""", height=0)

# ── Imports ───────────────────────────────────────────────────────────────────
from app.monitor_db import save_chat_message, load_chat_history, get_all_sessions, log_feedback as db_log_feedback

# ── Session state ─────────────────────────────────────────────────────────────
params = st.query_params
if "session_id" not in st.session_state:
    sid = params.get("sid") or str(uuid.uuid4())
    st.session_state.session_id = sid
    st.query_params["sid"] = sid
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.session_id)
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = set()

# ── Helpers ───────────────────────────────────────────────────────────────────
def check_health():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=3)
        return r.json() if r.status_code == 200 else None
    except: return None

def ask_question(q, sid):
    r = requests.post(f"{API_BASE_URL}/chat",
        json={"question": q, "session_id": sid}, timeout=180)
    r.raise_for_status(); return r.json()

def trigger_ingestion():
    try:
        r = requests.post(f"{API_BASE_URL}/ingest", timeout=10)
        return r.json()
    except Exception as e: return {"message": str(e)}

def submit_feedback(sid, score):
    try:
        requests.post(f"{API_BASE_URL}/feedback",
            json={"session_id": sid, "score": score}, timeout=5)
        db_log_feedback(sid, score)
    except: pass

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Small brand heading
    st.markdown('<p style="font-size:.95rem;font-weight:700;margin:0;padding:.2rem 0;">🌸 EndoResearch AI</p>', unsafe_allow_html=True)

    # ── Page navigation ───────────────────────────────────────────────────────
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        st.page_link("streamlit_app.py", label="🔬 Research AI", use_container_width=True)
    with nav_col2:
        st.page_link("pages/My_Health_Tracker.py", label="💜 Health Tracker", use_container_width=True)

    st.markdown("---")

    health = check_health()
    if health and health.get("rag_chain_ready"):
        st.markdown('<p style="font-size:.78rem;color:#2e7d32;font-weight:600;margin:0;">● Online</p>', unsafe_allow_html=True)
    elif health:
        st.markdown('<p style="font-size:.78rem;color:#e65100;font-weight:600;margin:0;">● Initializing…</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="font-size:.78rem;color:#c62828;font-weight:600;margin:0;">● API Offline</p>', unsafe_allow_html=True)

    if health:
        doc_count = f"{health.get('doc_count',0):,}"
        qas = len(st.session_state.messages)//2
        engine = "LangGraph" if health.get("pipeline")=="LangGraph" else "RAG"
        st.markdown(f'''<div style="display:flex;gap:0;margin:.4rem 0;">
            <div style="flex:1;text-align:center;">
                <div style="font-size:.75rem;color:#9e8880;">Chunks</div>
                <div style="font-size:.9rem;font-weight:700;">{doc_count}</div>
            </div>
            <div style="flex:1;text-align:center;">
                <div style="font-size:.75rem;color:#9e8880;">Q&As</div>
                <div style="font-size:.9rem;font-weight:700;">{qas}</div>
            </div>
            <div style="flex:1;text-align:center;">
                <div style="font-size:.7rem;color:#9e8880;">Pipeline</div>
                <div style="font-size:.78rem;font-weight:700;">{engine}</div>
            </div>
        </div>''', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .4rem 0;">📚 Research Library</p>', unsafe_allow_html=True)
    pdf_dir = "./data/pdfs"
    os.makedirs(pdf_dir, exist_ok=True)
    local_pdfs = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    if local_pdfs:
        st.caption(f"{len(local_pdfs)} paper(s) indexed")
        with st.expander("View papers"):
            for p in sorted(local_pdfs):
                st.caption(f"• {p.replace('_',' ').replace('-',' ').replace('.pdf','').title()}")
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
            for p in local_pdfs: zf.write(os.path.join(pdf_dir,p), p)
        buf.seek(0)
        st.download_button("⬇️ Download All Papers", data=buf,
            file_name="papers.zip", mime="application/zip", use_container_width=True)
    else:
        st.caption("No papers yet — upload below.")

    uploaded = st.file_uploader("➕ Upload PDF(s)", type=["pdf"],
        accept_multiple_files=True, key="pdf_uploader")
    if uploaded:
        saved = []
        for uf in uploaded:
            sp = os.path.join(pdf_dir, uf.name)
            if not os.path.exists(sp):
                with open(sp,"wb") as fo: fo.write(uf.read())
                saved.append(uf.name)
        if saved: st.success(f"Saved {len(saved)} PDF(s) — click Re-index below")

    st.markdown("---")
    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .4rem 0;">⚙️ Controls</p>', unsafe_allow_html=True)
    if st.button("🔄 Re-index Documents", use_container_width=True):
        with st.spinner("Indexing…"): r = trigger_ingestion()
        st.success(r.get("message","Started!"))
    if st.button("➕ New Chat", use_container_width=True):
        new_sid = str(uuid.uuid4())
        st.session_state.session_id = new_sid
        st.session_state.messages   = []
        st.query_params["sid"]       = new_sid
        st.rerun()

    st.markdown("---")
    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .4rem 0;">💡 Try asking</p>', unsafe_allow_html=True)
    for q in ["What causes endometriosis?","How does it affect fertility?",
              "What treatments reduce pain?","Role of estrogen?","Genetic risk factors?"]:
        if st.button(q, key=f"ex_{q[:15]}", use_container_width=True):
            st.session_state.pending_q = q; st.rerun()

    st.markdown("---")
    st.markdown('<p style="font-size:.82rem;font-weight:600;margin:0 0 .4rem 0;">🕓 Past Chats</p>', unsafe_allow_html=True)
    try:
        sessions = get_all_sessions()
        if sessions:
            hidden  = st.session_state.get("hidden_sessions", set())
            visible = [s for s in sessions if s["session_id"] not in hidden]
            if visible:
                for s in visible[:8]:
                    sid        = s["session_id"]
                    is_current = sid == st.session_state.session_id
                    fq         = s["first_question"] or "New session"
                    preview    = (fq[:26]+"…" if len(fq)>26 else fq)
                    weight     = "600" if is_current else "400"
                    color      = "#2c1810" if is_current else "#7a5c50"
                    dot        = "● " if is_current else "○ "
                    # Session title is the button, ✕ sits beside it
                    c1, c2 = st.columns([10, 1])
                    with c1:
                        if st.button(f"{dot}{preview}", key=f"sess_{sid[:8]}", use_container_width=True):
                            st.session_state.session_id = sid
                            st.session_state.messages   = load_chat_history(sid)
                            st.query_params["sid"]       = sid
                            st.rerun()
                    with c2:
                        if st.button("✕", key=f"del_{sid[:8]}", use_container_width=True):
                            if "hidden_sessions" not in st.session_state:
                                st.session_state.hidden_sessions = set()
                            st.session_state.hidden_sessions.add(sid)
                            if is_current:
                                st.session_state.messages = []
                            st.rerun()
            else:
                st.caption("All chats removed.")
        else:
            st.caption("No past chats yet.")
    except Exception as e:
        st.caption(f"Sessions error: {e}")
    st.markdown("---")
    st.caption("LLaMA 3.2 · LangGraph · BGE · Cohere")

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:1.2rem 0 1rem 0;border-bottom:1px solid #e8ddd6;margin-bottom:1.2rem;'>
  <div style='font-size:2.2rem;margin-bottom:.4rem;'>🔬</div>
  <div style='font-family:Lora,serif;font-size:1.7rem;font-weight:700;color:#2c1810;'>Endometriosis Research AI</div>
  <div style='color:#9e8880;font-size:.85rem;margin-top:.3rem;'>Research-backed answers · Peer-reviewed papers · LangGraph</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.messages:
    st.info("👋 **Welcome!** Ask any question about endometriosis and get cited answers from peer-reviewed research papers. Use the example questions in the sidebar to get started.")

# ── Render messages ───────────────────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        data        = msg.get("data", {})
        sources     = data.get("sources", [])
        confidence  = data.get("confidence", 0.0)
        answer_type = data.get("answer_type", "rag")
        conf_pct    = int(confidence * 100)

        with st.chat_message("assistant", avatar="🌸"):
            st.markdown(msg["content"])

            # Badges row
            # All badges in one line — no columns, no wrapping
            if answer_type == "web":
                type_badge = '<span style="background:#fff3cd;color:#856404;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:12px;white-space:nowrap;">🌐 Web</span>'
            elif answer_type == "none":
                type_badge = '<span style="background:#f8d7da;color:#721c24;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:12px;white-space:nowrap;">⚠️ Not Found</span>'
            else:
                type_badge = '<span style="background:#fce4ec;color:#880e4f;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:12px;white-space:nowrap;">📄 Papers</span>'
            color  = "#d4edda" if confidence>=0.7 else ("#fff3cd" if confidence>=0.4 else "#f8d7da")
            tcolor = "#155724" if confidence>=0.7 else ("#856404" if confidence>=0.4 else "#721c24")
            conf_badge  = f'<span style="background:{color};color:{tcolor};font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:12px;white-space:nowrap;">✦ {conf_pct}% confidence</span>'
            src_badge   = f'<span style="background:#e3f2fd;color:#0d47a1;font-size:.72rem;font-weight:600;padding:.2rem .7rem;border-radius:12px;white-space:nowrap;">📎 {len(sources)} source(s)</span>'
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin:.4rem 0;">{type_badge}{conf_badge}{src_badge}</div>', unsafe_allow_html=True)

            # Sources expander
            if sources:
                with st.expander(f"📄 View {len(sources)} cited source(s)"):
                    for s in sources:
                        sc = s.get("rerank_score","N/A")
                        sc_str = f"{float(sc):.1%}" if isinstance(sc,(int,float)) else str(sc)
                        st.markdown(f"""<div style='background:#fdf6f0;border:1px solid #e8ddd6;border-left:3px solid #c0392b;
                            border-radius:8px;padding:.7rem .9rem;margin:.3rem 0;font-size:.83rem;'>
                            <div style='font-weight:600;color:#833ab4;margin-bottom:.2rem;'>{s['paper_title']}</div>
                            <div style='color:#9e8880;font-size:.75rem;'>📄 Page {s['page']} · Relevance: {sc_str}</div>
                            <div style='color:#9e8880;font-size:.78rem;border-top:1px solid #e8ddd6;padding-top:.35rem;
                            margin-top:.35rem;font-style:italic;'>{s['excerpt']}</div>
                        </div>""", unsafe_allow_html=True)

            # Feedback — native streamlit, small
            fb_key = f"fb_{i}"
            if fb_key not in st.session_state.feedback_given:
                st.caption("Was this helpful?")
                fb1, fb2, _ = st.columns([0.05, 0.05, 0.9])
                with fb1:
                    if st.button("👍", key=f"up_{i}"):
                        submit_feedback(st.session_state.session_id, 1.0)
                        st.session_state.feedback_given.add(fb_key); st.rerun()
                with fb2:
                    if st.button("👎", key=f"dn_{i}"):
                        submit_feedback(st.session_state.session_id, 0.0)
                        st.session_state.feedback_given.add(fb_key); st.rerun()
            else:
                st.caption("✓ Thanks!")

# ── Pending question (sidebar examples) ──────────────────────────────────────
if "pending_q" in st.session_state:
    pending = st.session_state.pop("pending_q")
    save_chat_message(st.session_state.session_id, "user", pending)
    st.session_state.messages.append({"role":"user","content":pending})
    with st.spinner("🌸 Searching research papers…"):
        try:
            result = ask_question(pending, st.session_state.session_id)
            save_chat_message(st.session_state.session_id,"assistant",result["answer"],result)
            st.session_state.messages.append({"role":"assistant","content":result["answer"],"data":result})
        except Exception as e:
            err = f"⚠️ Error: {e}"
            save_chat_message(st.session_state.session_id,"assistant",err)
            st.session_state.messages.append({"role":"assistant","content":err,"data":{}})
    st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask anything about endometriosis…"):
    save_chat_message(st.session_state.session_id,"user",prompt)
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.spinner("🌸 Searching research papers and generating answer…"):
        try:
            if not health or not health.get("rag_chain_ready"):
                raise Exception("RAG system not ready. Start the API first.")
            result = ask_question(prompt, st.session_state.session_id)
            save_chat_message(st.session_state.session_id,"assistant",result["answer"],result)
            st.session_state.messages.append({"role":"assistant","content":result["answer"],"data":result})
        except requests.exceptions.ConnectionError:
            err = "⚠️ Cannot connect to API. Run `python -m app.api` first."
            save_chat_message(st.session_state.session_id,"assistant",err)
            st.session_state.messages.append({"role":"assistant","content":err,"data":{}})
        except Exception as e:
            err = f"⚠️ Error: {str(e)}"
            save_chat_message(st.session_state.session_id,"assistant",err)
            st.session_state.messages.append({"role":"assistant","content":err,"data":{}})
    st.rerun()