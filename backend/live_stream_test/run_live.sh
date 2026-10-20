#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "==================================================="
echo "  CS472 Mocap - MediaPipe Live Stream Studio (Linux)"
echo "==================================================="
echo ""

cd "$REPO_DIR"

# 1. Resolve or create Python virtual environment
PYTHON_BIN=""
if [ -f "$REPO_DIR/backend/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"
elif [ -f "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/.venv/bin/python"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[1/2] Virtual environment not found. Setting up backend/.venv..."
    if command -v uv >/dev/null 2>&1; then
        echo "Using uv to create virtual environment..."
        uv venv --python 3.12 "$REPO_DIR/backend/.venv" || uv venv "$REPO_DIR/backend/.venv"
        PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        echo "Using python3 -m venv to create virtual environment..."
        python3 -m venv "$REPO_DIR/backend/.venv"
        PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"
    else
        echo "Error: Python 3 is not installed or not in PATH."
        exit 1
    fi
fi

echo "[1/2] Using Python: $PYTHON_BIN"

# Check required python packages
if ! "$PYTHON_BIN" -c "import websockets, cv2, mediapipe, fastapi, uvicorn" >/dev/null 2>&1; then
    echo "Installing live stream dependencies..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install -r "$REPO_DIR/backend/live_stream_test/requirements.txt" --python "$PYTHON_BIN"
    else
        "$PYTHON_BIN" -m pip install -r "$REPO_DIR/backend/live_stream_test/requirements.txt"
    fi
fi

# 2. Launch Electron Live Studio
echo "[2/2] Launching Electron Live Studio..."
cd "$REPO_DIR/desktop"

if [ -f "$REPO_DIR/desktop/node_modules/.bin/electron" ]; then
    "$REPO_DIR/desktop/node_modules/.bin/electron" "$REPO_DIR/backend/live_stream_test/gui"
elif command -v electron >/dev/null 2>&1; then
    electron "$REPO_DIR/backend/live_stream_test/gui"
else
    npx electron "$REPO_DIR/backend/live_stream_test/gui"
fi
