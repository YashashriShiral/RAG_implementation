"""
pages/Log_History.py — redirects to Health Tracker > Log History tab
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Log History", page_icon="📋", layout="wide")

components.html("""
<script>
const css = `
  html, body, [data-testid="stAppViewContainer"] { background: #fdf6f0 !important; }
  section[data-testid="stMain"] > div { background: #fdf6f0 !important; }
  header[data-testid="stHeader"] { background: #fdf6f0 !important; }
  html, body, p, div, span { font-family: 'DM Sans', sans-serif !important; color: #2c1810 !important; }
`;
const style = document.createElement('style');
style.textContent = css;
window.parent.document.head.appendChild(style);
</script>
""", height=0)

n1, n2, n3 = st.columns(3)
with n1: st.page_link("streamlit_app.py",           label="🔬 Research AI",   use_container_width=True)
with n2: st.page_link("pages/My_Health_Tracker.py", label="💜 Health Tracker", use_container_width=True)
with n3: st.page_link("pages/Log_History.py",       label="📋 Log History",   use_container_width=True)

st.markdown("""
<div style='text-align:center;padding:3rem 1rem;'>
  <div style='font-size:2rem;margin-bottom:1rem;'>📋</div>
  <div style='font-size:1.3rem;font-weight:700;color:#2c1810;margin-bottom:.5rem;'>Log History has moved!</div>
  <div style='color:#7a5c55;font-size:.9rem;margin-bottom:1.5rem;'>
    It's now inside <b>Health Tracker → Log History tab</b> for a better experience.
  </div>
</div>
""", unsafe_allow_html=True)

st.page_link("pages/My_Health_Tracker.py", label="→ Go to Health Tracker", use_container_width=False)
