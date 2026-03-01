"""
streamlit_app.py — Ask Anything About Endometriosis
"""

import uuid
import requests
import streamlit as st
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Endo Research AI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@600;700&display=swap');

section[data-testid="stMain"] {background:#0d1117 !important;}
section[data-testid="stSidebar"] {background:#161b22 !important; border-right:1px solid #30363d !important;}
header[data-testid="stHeader"] {background:transparent !important;}
div[data-testid="stMainBlockContainer"] {background:#0d1117 !important;}

html, body, p, div, span, label, li {
    font-family:'Inter',sans-serif !important;
    color:#e6edf3 !important;
}

.app-title {
    font-family:'Sora',sans-serif !important;
    font-size:1.9rem;
    font-weight:700;
    background:linear-gradient(135deg,#58a6ff,#bc8cff);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    background-clip:text;
    margin-bottom:0.2rem;
}
.app-sub {color:#8b949e !important;font-size:0.85rem;margin-bottom:1rem;}

.user-wrap {display:flex;justify-content:flex-end;margin:0.8rem 0 0.4rem 0;}
.user-bubble {
    background:#1f6feb;color:#fff !important;
    padding:0.75rem 1.1rem;
    border-radius:18px 18px 4px 18px;
    max-width:75%;font-size:0.92rem;line-height:1.6;
    box-shadow:0 2px 10px rgba(31,111,235,0.35);
    word-wrap:break-word;
}
.bot-wrap {display:flex;justify-content:flex-start;margin:0.4rem 0 0.4rem 0;}
.bot-bubble {
    background:#1c2128;color:#e6edf3 !important;
    padding:1rem 1.2rem;
    border-radius:4px 18px 18px 18px;
    max-width:85%;font-size:0.92rem;line-height:1.7;
    border:1px solid #30363d;
    box-shadow:0 2px 8px rgba(0,0,0,0.25);
    word-wrap:break-word;
}
.meta-row {display:flex;align-items:center;gap:0.4rem;margin:0.3rem 0;flex-wrap:wrap;}
.badge {
    display:inline-flex;align-items:center;
    font-size:0.7rem;font-weight:600;
    padding:0.15rem 0.55rem;border-radius:20px;
    letter-spacing:0.03em;text-transform:uppercase;
}
.b-green {background:rgba(63,185,80,0.15);color:#3fb950 !important;border:1px solid rgba(63,185,80,0.3);}
.b-orange{background:rgba(240,136,62,0.15);color:#f0883e !important;border:1px solid rgba(240,136,62,0.3);}
.b-red   {background:rgba(248,81,73,0.15); color:#f85149 !important;border:1px solid rgba(248,81,73,0.3);}
.b-blue  {background:rgba(88,166,255,0.15);color:#58a6ff !important;border:1px solid rgba(88,166,255,0.3);}

.cite-card {
    background:#161b22;border:1px solid #30363d;
    border-left:3px solid #bc8cff;
    border-radius:8px;padding:0.75rem 1rem;margin:0.4rem 0;
}
.cite-title {font-weight:600;color:#58a6ff !important;font-size:0.85rem;margin-bottom:0.2rem;}
.cite-meta  {color:#6e7681 !important;font-size:0.75rem;margin-bottom:0.35rem;}
.cite-text  {color:#8b949e !important;font-size:0.8rem;line-height:1.5;font-style:italic;
             border-top:1px solid #30363d;padding-top:0.35rem;}

.welcome {
    background:#1c2128;border:1px solid #30363d;border-radius:12px;
    padding:1.5rem 2rem;margin-bottom:1.5rem;
}
.welcome h3 {font-family:'Sora',sans-serif !important;color:#58a6ff !important;
             font-size:1.1rem;margin:0 0 0.5rem 0;}
.welcome p  {color:#8b949e !important;font-size:0.88rem;line-height:1.6;margin:0;}

.stat-box {
    background:#1c2128;border:1px solid #30363d;border-radius:8px;
    padding:0.6rem 0.8rem;margin:0.3rem 0;font-size:0.82rem;
}
.stat-val {font-size:1.1rem;font-weight:600;color:#58a6ff !important;}

.sess-btn {
    background:#1c2128 !important;border:1px solid #30363d !important;
    border-radius:6px !important;color:#e6edf3 !important;
    font-size:0.8rem !important;text-align:left !important;
    padding:0.4rem 0.6rem !important;margin:0.2rem 0 !important;
    width:100% !important;
}
.sess-btn:hover {border-color:#58a6ff !important;color:#58a6ff !important;}

div[data-testid="stChatInput"] {background:#161b22 !important;border-top:1px solid #30363d !important;}
div[data-testid="stChatInput"] textarea {
    background:#1c2128 !important;color:#e6edf3 !important;
    border:1px solid #30363d !important;border-radius:10px !important;
    font-family:'Inter',sans-serif !important;font-size:0.92rem !important;
    caret-color:#58a6ff !important;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color:#58a6ff !important;
    box-shadow:0 0 0 2px rgba(88,166,255,0.2) !important;
}
div[data-testid="stChatInput"] textarea::placeholder {color:#6e7681 !important;}

div[data-testid="stExpander"] {
    background:#1c2128 !important;border:1px solid #30363d !important;border-radius:8px !important;
}

.stButton > button {
    background:#1c2128 !important;color:#e6edf3 !important;
    border:1px solid #30363d !important;border-radius:8px !important;
    font-family:'Inter',sans-serif !important;font-size:0.82rem !important;
    font-weight:500 !important;width:100% !important;text-align:left !important;
    transition:all 0.2s !important;
}
.stButton > button:hover {
    background:#21262d !important;border-color:#58a6ff !important;color:#58a6ff !important;
}

::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:#0d1117;}
::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px;}
</style>
""", unsafe_allow_html=True)


# ── Imports ───────────────────────────────────────────────────────────────────
from app.monitor_db import (
    save_chat_message, load_chat_history,
    get_all_sessions, log_feedback as db_log_feedback
)


# ── State ─────────────────────────────────────────────────────────────────────
params = st.query_params
if "session_id" not in st.session_state:
    if "sid" in params:
        st.session_state.session_id = params["sid"]
    else:
        new_sid = str(uuid.uuid4())
        st.session_state.session_id = new_sid
        st.query_params["sid"] = new_sid

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.session_id)

if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = set()


# ── API Helpers ───────────────────────────────────────────────────────────────
def check_health():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def ask_question(question, session_id):
    r = requests.post(
        f"{API_BASE_URL}/chat",
        json={"question": question, "session_id": session_id},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()

def get_sources_list():
    try:
        r = requests.get(f"{API_BASE_URL}/sources", timeout=5)
        return r.json() if r.status_code == 200 else {"sources": [], "total": 0}
    except Exception:
        return {"sources": [], "total": 0}

def trigger_ingestion():
    try:
        r = requests.post(f"{API_BASE_URL}/ingest", timeout=10)
        return r.json()
    except Exception as e:
        return {"message": str(e)}

def submit_feedback(session_id, score):
    try:
        requests.post(
            f"{API_BASE_URL}/feedback",
            json={"session_id": session_id, "score": score},
            timeout=5,
        )
        db_log_feedback(session_id, score)
    except Exception:
        pass


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔬 Endo Research AI")
    st.markdown("---")

    health = check_health()

    if health and health.get("rag_chain_ready"):
        st.success("● System Online", icon=None)
    elif health:
        st.warning("● Initializing...")
    else:
        st.error("● API Offline")

    if health:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-val">{health.get("doc_count",0):,}</div><div>chunks</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-val">{len(st.session_state.messages)//2}</div><div>Q&As</div></div>', unsafe_allow_html=True)
        st.caption(f"Model: `{health.get('model','N/A')}`")

    st.markdown("---")

    # ── Papers section ──────────────────────────────────────────────────────
    st.markdown("**📚 Reference Research Papers**")
    import os, zipfile, io as _io
    pdf_dir = "./data/pdfs"
    os.makedirs(pdf_dir, exist_ok=True)
    local_pdfs = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]

    if local_pdfs:
        st.caption(f"{len(local_pdfs)} paper(s) in library")
        with st.expander("📄 View all papers", expanded=False):
            for pdf in sorted(local_pdfs):
                name = pdf.replace("_", " ").replace("-", " ").replace(".pdf", "").title()
                st.markdown(f"<small style='color:#8b949e'>• {name}</small>", unsafe_allow_html=True)

        # ── Download ZIP ─────────────────────────────────────────────────────
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for pdf in local_pdfs:
                zf.write(os.path.join(pdf_dir, pdf), pdf)
        buf.seek(0)
        st.download_button(
            label="⬇️ Download All Papers (.zip)",
            data=buf,
            file_name="endometriosis_papers.zip",
            mime="application/zip",
            use_container_width=True,
        )
    else:
        st.caption("No papers in library yet.")
        st.info("Upload PDFs below to get started.")

    # ── Upload new PDFs ──────────────────────────────────────────────────────
    st.markdown("**➕ Add Research Papers**")
    uploaded_files = st.file_uploader(
        "Upload PDF(s)",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader",
        label_visibility="collapsed",
        help="Upload one or more research paper PDFs. They will be indexed automatically.",
    )
    if uploaded_files:
        newly_saved = []
        for uf in uploaded_files:
            save_path = os.path.join(pdf_dir, uf.name)
            if not os.path.exists(save_path):
                with open(save_path, "wb") as f_out:
                    f_out.write(uf.read())
                newly_saved.append(uf.name)
            else:
                st.caption(f"Already exists: {uf.name}")
        if newly_saved:
            st.success(f"Saved {len(newly_saved)} new PDF(s): {', '.join(newly_saved)}")
            st.info("Click **Re-index Documents** below to make them searchable.")

    st.markdown("---")
    st.markdown("**⚙️ Controls**")
    if st.button("🔄 Re-index Documents"):
        with st.spinner("Indexing in background…"):
            result = trigger_ingestion()
        st.success(result.get("message", "Re-indexing started!"))
    if st.button("➕ New Chat"):
        new_sid = str(uuid.uuid4())
        st.session_state.session_id = new_sid
        st.session_state.messages = []
        st.query_params["sid"] = new_sid
        st.rerun()

    st.markdown("---")
    st.markdown("**💡 Example Questions**")
    examples = [
        "What causes endometriosis?",
        "How does it affect fertility?",
        "What treatments reduce pain?",
        "Role of estrogen in progression?",
        "Are there genetic risk factors?",
    ]
    for q in examples:
        if st.button(q, key=f"ex_{q[:15]}"):
            st.session_state.pending_question = q
            st.rerun()

    st.markdown("---")
    st.markdown("**🕓 Past Sessions**")
    try:
        sessions = get_all_sessions()
        if sessions:
            for s in sessions[:6]:
                sid = s["session_id"]
                first_q = s["first_question"] or "New session"
                preview = (first_q[:30] + "…") if len(first_q) > 30 else first_q
                is_cur = "● " if sid == st.session_state.session_id else ""
                if st.button(f"{is_cur}{preview}", key=f"sess_{sid[:8]}"):
                    st.session_state.session_id = sid
                    st.session_state.messages = load_chat_history(sid)
                    st.query_params["sid"] = sid
                    st.rerun()
        else:
            st.caption("No past sessions yet.")
    except Exception:
        st.caption("Sessions unavailable.")

    st.markdown("---")
    st.caption("LLaMA 3.2 · ChromaDB · BM25 · Cohere")


# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="app-title">Ask Anything About Endometriosis</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">Research-backed answers with citations · Hybrid RAG + LLaMA 3.2 · Peer-reviewed papers</div>', unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown("""
    <div class="welcome">
        <h3>👋 Welcome to the Endometriosis Research Assistant</h3>
        <p>Ask any question about endometriosis and get detailed, cited answers sourced
        directly from peer-reviewed research papers. Every answer includes the exact paper
        name and page number. Use the example questions in the sidebar to get started.</p>
    </div>
    """, unsafe_allow_html=True)


# ── Render messages ────────────────────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        st.markdown(f"""
        <div class="user-wrap">
            <div class="user-bubble">👤 &nbsp;{msg["content"]}</div>
        </div>""", unsafe_allow_html=True)
    else:
        data   = msg.get("data", {})
        answer = msg["content"]
        sources    = data.get("sources", [])
        confidence = data.get("confidence", 0.0)

        st.markdown(f"""
        <div class="bot-wrap">
            <div class="bot-bubble">🔬 &nbsp;{answer}</div>
        </div>""", unsafe_allow_html=True)

        conf_pct = int(confidence * 100)
        bc = "b-green" if confidence >= 0.7 else ("b-orange" if confidence >= 0.4 else "b-red")
        st.markdown(f"""
        <div class="meta-row">
            <span class="badge {bc}">● Confidence {conf_pct}%</span>
            <span class="badge b-blue">📎 {len(sources)} source(s)</span>
        </div>""", unsafe_allow_html=True)

        if sources:
            with st.expander(f"📄 View {len(sources)} cited source(s)", expanded=False):
                for s in sources:
                    score = s.get("rerank_score", "N/A")
                    score_str = f"{float(score):.1%}" if isinstance(score, (int, float)) else str(score)
                    st.markdown(f"""
                    <div class="cite-card">
                        <div class="cite-title">{s['paper_title']}</div>
                        <div class="cite-meta">📄 Page {s['page']} &nbsp;·&nbsp; Relevance: {score_str} &nbsp;·&nbsp; {s['source_file']}</div>
                        <div class="cite-text">{s['excerpt']}</div>
                    </div>""", unsafe_allow_html=True)

        msg_key = f"fb_{i}"
        if msg_key not in st.session_state.feedback_submitted:
            c1, c2, c3 = st.columns([1, 1, 10])
            with c1:
                if st.button("👍", key=f"up_{i}"):
                    submit_feedback(st.session_state.session_id, 1.0)
                    st.session_state.feedback_submitted.add(msg_key)
                    st.rerun()
            with c2:
                if st.button("👎", key=f"dn_{i}"):
                    submit_feedback(st.session_state.session_id, 0.0)
                    st.session_state.feedback_submitted.add(msg_key)
                    st.rerun()
        else:
            st.caption("✓ Feedback recorded")

        st.markdown("<hr style='border:none;border-top:1px solid #30363d;margin:0.6rem 0;opacity:0.5;'>", unsafe_allow_html=True)


# ── Sidebar example question ───────────────────────────────────────────────────
if "pending_question" in st.session_state:
    pending = st.session_state.pop("pending_question")
    save_chat_message(st.session_state.session_id, "user", pending)
    st.session_state.messages.append({"role": "user", "content": pending})
    with st.spinner("🧠 Searching research papers and generating answer…"):
        try:
            result = ask_question(pending, st.session_state.session_id)
            save_chat_message(st.session_state.session_id, "assistant", result["answer"], result)
            st.session_state.messages.append({"role": "assistant", "content": result["answer"], "data": result})
        except Exception as e:
            err = f"⚠️ Error: {e}"
            save_chat_message(st.session_state.session_id, "assistant", err)
            st.session_state.messages.append({"role": "assistant", "content": err, "data": {}})
    st.rerun()


# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask anything about endometriosis…"):
    save_chat_message(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("🧠 Searching research papers and generating answer…"):
        try:
            if not health or not health.get("rag_chain_ready"):
                raise Exception("RAG system not ready. Make sure the API is running.")
            result = ask_question(prompt, st.session_state.session_id)
            save_chat_message(st.session_state.session_id, "assistant", result["answer"], result)
            st.session_state.messages.append({"role": "assistant", "content": result["answer"], "data": result})
        except requests.exceptions.ConnectionError:
            err = "⚠️ Cannot connect to API. Make sure `python -m app.api` is running."
            save_chat_message(st.session_state.session_id, "assistant", err)
            st.session_state.messages.append({"role": "assistant", "content": err, "data": {}})
        except Exception as e:
            err = f"⚠️ Error: {str(e)}"
            save_chat_message(st.session_state.session_id, "assistant", err)
            st.session_state.messages.append({"role": "assistant", "content": err, "data": {}})
    st.rerun()