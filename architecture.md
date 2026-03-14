┌─────────────────────────────────────────────────────────────┐
│                    Railway Services                          │
│                                                             │
│  Service 1: FastAPI                Service 2: Streamlit     │
│  ┌─────────────────────┐          ┌─────────────────────┐  │
│  │ POST /auth/register  │          │ / → Login page       │  │
│  │ POST /auth/otp/send  │          │ /dashboard → Health  │  │
│  │ POST /auth/otp/verify│          │ /research  → RAG AI  │  │
│  │ POST /whatsapp/webhook│         │ /monitor   → RAG Mon │  │
│  │ POST /chat           │          │                      │  │
│  │ GET  /me/logs        │          │ JWT cookie auth      │  │
│  │ GET  /me/insights    │          │ user_id from token   │  │
│  └─────────────────────┘          └─────────────────────┘  │
│           │                                  │               │
│  ┌────────▼──────────────────────────────────▼───────────┐  │
│  │                  PostgreSQL (Railway)                  │  │
│  │                                                        │  │
│  │  users(id, phone, name, created_at, is_active)        │  │
│  │  otp_codes(phone, code, expires_at)                   │  │
│  │  daily_log(user_id, log_date, pain, mood, ...)        │  │
│  │  insight_log(user_id, log_date, ai_reply, ...)        │  │
│  │  parse_log(user_id, log_date, source, ...)            │  │
│  │  chat_sessions(user_id, session_id, messages, ...)    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                             │
│  Service 3: ChromaDB Volume                                 │
│  (shared RAG index — same PDFs for all users)              │
└─────────────────────────────────────────────────────────────┘
         ▲                    ▲                  ▲
         │                    │                  │
┌────────┴──────┐   ┌─────────┴──────┐  ┌───────┴────────┐
│ Meta WhatsApp │   │  OpenRouter    │  │   Cohere       │
│ Cloud API     │   │  LLaMA 3.2     │  │   Reranker     │
│ (free)        │   │  (per call)    │  │   (RAG)        │
└───────────────┘   └────────────────┘  └────────────────┘

# Terminal 1 — Ollama (LLM)
ollama serve

# Terminal 2 — FastAPI
uvicorn app.api:app --reload --port 8000

# Terminal 3 — Streamlit main app
streamlit run streamlit_app.py

# Terminal 4 — Monitoring dashboard (admin)
streamlit run monitoring_dashboard.py --server.port 8502

# Terminal 5 — ngrok (WhatsApp webhook)
ngrok http 8000