#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Start Aurora backend in demo-stable configuration:
#   - FLASK_DEBUG=False  (no werkzeug auto-reloader → no zombie restarts)
#   - port 5001          (canonical; matches frontend axios baseURL)
#   - Mac mini Ollama    (gemma4:e4b at 192.168.68.50:11434)
#
# Usage:  ./start-aurora-demo.sh
# Stop:   pkill -f "python3 run.py" (or Ctrl-C)
#
# Why this script exists: running run.py with FLASK_DEBUG=True (the default)
# spawns werkzeug's auto-reloader, which forks a child process. When the
# parent gets a SIGPIPE on its stdout (e.g. when a tail | head pipeline
# closes), the parent dies but the child can keep its python procs alive
# without the listening socket — leaving the demo broken with zombie
# processes and no clear failure signal.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/backend"

# Free the port if a previous run left something behind.
PORT=5001
if lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT} busy — killing existing listener" >&2
  pkill -f "python3 run.py" 2>/dev/null || true
  sleep 1
fi

echo "Starting Aurora backend on :${PORT} pointed at Mac mini Ollama (gemma4:e4b)..."
exec env \
  FLASK_PORT="${PORT}" \
  FLASK_DEBUG=False \
  LLM_BASE_URL="${LLM_BASE_URL:-http://192.168.68.50:11434/v1}" \
  LLM_MODEL_NAME="${LLM_MODEL_NAME:-gemma4:e4b}" \
  python3 run.py
