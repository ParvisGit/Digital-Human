#!/bin/bash
# Create Python 3.12 venv for Banking Agent (required for langgraph-checkpoint-redis).
# Run from BFSI directory: bash Banking_agent/scripts/setup_venv_312.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BANKING_DIR="$(dirname "$SCRIPT_DIR")"
BFSI_DIR="$(dirname "$BANKING_DIR")"
VENV_DIR="$BFSI_DIR/.venv_312"

# Find Python 3.12 or 3.13
PYTHON=""
for p in python3.12 python3.13; do
    if command -v $p &>/dev/null; then
        PYTHON=$p
        break
    fi
done

# Homebrew path
if [ -z "$PYTHON" ] && [ -f "/opt/homebrew/opt/python@3.12/bin/python3.12" ]; then
    PYTHON="/opt/homebrew/opt/python@3.12/bin/python3.12"
elif [ -z "$PYTHON" ] && [ -f "/opt/homebrew/opt/python@3.13/bin/python3.13" ]; then
    PYTHON="/opt/homebrew/opt/python@3.13/bin/python3.13"
fi

if [ -z "$PYTHON" ]; then
    echo "Python 3.12 or 3.13 not found. Install with:"
    echo "  brew install python@3.12"
    echo "  # or download from https://www.python.org/downloads/"
    exit 1
fi

echo "Using: $PYTHON ($($PYTHON --version))"
echo "Creating venv at $VENV_DIR"

rm -rf "$VENV_DIR"
$PYTHON -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$BANKING_DIR/requirement.txt"
pip install langgraph-checkpoint-redis

echo ""
echo "Done. Activate with:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or use .venv_312 when running gRPC/Streamlit:"
echo "  source .venv_312/bin/activate && python Banking_agent/run_grpc.py --port 50051"
