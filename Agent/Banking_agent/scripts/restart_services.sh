#!/bin/bash
# Restart gRPC server and Streamlit for Banking Agent.
# Run from BFSI directory: bash Banking_agent/scripts/restart_services.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BANKING_DIR="$(dirname "$SCRIPT_DIR")"
BFSI_DIR="$(dirname "$BANKING_DIR")"
# Prefer .venv_312 (Python 3.12), fall back to .venv_new
if [ -d "${BFSI_DIR}/.venv_312" ]; then
    VENV="${BFSI_DIR}/.venv_312"
else
    VENV="${BFSI_DIR}/.venv_new"
fi
GRPC_PORT="${GRPC_PORT:-50051}"

cd "$BFSI_DIR"

# Activate venv if it exists
if [ -d "$VENV" ]; then
    source "$VENV/bin/activate"
fi

# Kill existing processes on gRPC port and Streamlit
echo "Stopping existing processes..."
pkill -f "run_grpc.py.*$GRPC_PORT" 2>/dev/null || true
pkill -f "streamlit run.*Banking_agent/streamlit" 2>/dev/null || true
sleep 2

# Set env for gRPC
export PYTHONPATH="${BFSI_DIR}:${PYTHONPATH}"
export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-${BFSI_DIR}/vertex-gemini-agent.json}"

echo "Starting gRPC server on port $GRPC_PORT..."
python "$BANKING_DIR/run_grpc.py" --port "$GRPC_PORT" &
GRPC_PID=$!

echo "Starting Streamlit..."
streamlit run "$BANKING_DIR/streamlit.py" &
STREAMLIT_PID=$!

echo ""
echo "Services started:"
echo "  gRPC:     PID $GRPC_PID (port $GRPC_PORT)"
echo "  Streamlit: PID $STREAMLIT_PID (usually http://localhost:8501)"
echo ""
echo "Full application logs: tail -f $BANKING_DIR/../logs/app.log"
echo "Verbose (DEBUG): LOG_LEVEL=DEBUG before running"
echo ""
echo "Press Ctrl+C to stop both."

wait
