#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh — runs all services
# Local:   bash start.sh
# Railway: only FastAPI + Streamlit (monitoring runs separately)
# ─────────────────────────────────────────────────────────────────────────────

set -e
MODE=${1:-"railway"}  # "local" or "railway"

echo "🌸 Starting Endo Tracker ($MODE mode)..."

# ── FastAPI on port 8000 ──────────────────────────────────────────────────────
echo "▶ Starting FastAPI on :8000"
uvicorn app.api:app --host 0.0.0.0 --port 8000 --workers 1 &
FASTAPI_PID=$!

sleep 5  # wait for FastAPI to be ready

# ── Main Streamlit app on Railway PORT (or 8501 locally) ─────────────────────
STREAMLIT_PORT=${PORT:-8501}
echo "▶ Starting Streamlit (main app) on :$STREAMLIT_PORT"
streamlit run streamlit_app.py \
    --server.port $STREAMLIT_PORT \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false &
STREAMLIT_PID=$!

# ── Monitoring dashboard on 8502 (local only — separate Railway service) ──────
if [ "$MODE" = "local" ]; then
    echo "▶ Starting Monitoring Dashboard on :8502"
    streamlit run monitoring_dashboard.py \
        --server.port 8502 \
        --server.address 0.0.0.0 \
        --server.headless true &
    MONITOR_PID=$!
    echo ""
    echo "════════════════════════════════════════"
    echo "✅ All services running:"
    echo "   Main app:    http://localhost:8501"
    echo "   FastAPI:     http://localhost:8000"
    echo "   Monitoring:  http://localhost:8502"
    echo "════════════════════════════════════════"
    wait -n $FASTAPI_PID $STREAMLIT_PID $MONITOR_PID
else
    echo ""
    echo "════════════════════════════════════════"
    echo "✅ Railway services running:"
    echo "   Main app:    :$STREAMLIT_PORT"
    echo "   FastAPI:     :8000"
    echo "════════════════════════════════════════"
    wait -n $FASTAPI_PID $STREAMLIT_PID
fi