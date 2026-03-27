#!/bin/bash
# Railway: Streamlit on $PORT (public), FastAPI on 8000 (internal)
# Local:   bash start.sh local

set -e
MODE=${1:-"railway"}

echo "🌸 Starting Endo Tracker ($MODE mode)..."

if [ "$MODE" = "railway" ]; then
    # Start FastAPI on internal port 8000
    echo "▶ FastAPI on :8000 (internal)"
    uvicorn app.api:app --host 0.0.0.0 --port 8000 --workers 1 &
    FASTAPI_PID=$!

    sleep 8

    # Streamlit on Railway's public $PORT
    STREAMLIT_PORT=${PORT:-8501}
    echo "▶ Streamlit on :$STREAMLIT_PORT (public)"
    streamlit run streamlit_app.py \
        --server.port $STREAMLIT_PORT \
        --server.address 0.0.0.0 \
        --server.headless true \
        --server.enableCORS false &
    STREAMLIT_PID=$!

    echo "✅ Streamlit public at Railway URL"
    echo "✅ FastAPI internal at :8000"
    wait -n $FASTAPI_PID $STREAMLIT_PID

else
    # Local mode
    echo "▶ FastAPI on :8000"
    uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload &
    FASTAPI_PID=$!

    sleep 5

    echo "▶ Streamlit on :8501"
    streamlit run streamlit_app.py \
        --server.port 8501 --server.address 0.0.0.0 \
        --server.headless true &
    STREAMLIT_PID=$!

    echo "▶ Monitoring on :8502"
    streamlit run monitoring_dashboard.py \
        --server.port 8502 --server.address 0.0.0.0 \
        --server.headless true &
    MONITOR_PID=$!

    echo ""
    echo "════════════════════════════════════════"
    echo "  Main app:    http://localhost:8501"
    echo "  FastAPI:     http://localhost:8000"
    echo "  Monitoring:  http://localhost:8502"
    echo "════════════════════════════════════════"
    wait -n $FASTAPI_PID $STREAMLIT_PID $MONITOR_PID
fi
