#!/usr/bin/env bash
# Aurora — single-command launcher.
#
# Usage:
#   ./start.sh                # boot full stack: Neo4j + backend + frontend (dev)
#   ./start.sh prod           # boot full stack: Neo4j + backend + frontend (prod build + preview)
#   ./start.sh backend        # boot backend only (Flask :5001)
#   ./start.sh frontend       # boot frontend only (vite dev :3000)
#   ./start.sh prewarm        # warm Ollama (gemma4:e2b + e4b) — run T-30min before recording
#   ./start.sh check          # health check: curl every endpoint, report green/red
#   ./start.sh stop           # kill any backend / frontend / docker containers we started
#   ./start.sh clean          # nuke .pyc, dist/, node_modules/.vite, /tmp logs
#
# Environment overrides (all optional):
#   FLASK_PORT=5001        backend port
#   VITE_PORT=3000         frontend dev port (override in vite.config.js for prod)
#   AURORA_LOG_DIR=/tmp    where to write per-process logs
#   AURORA_NO_DOCKER=1     skip Neo4j docker step (use when you already have one running)
#   AURORA_NO_OLLAMA=1     don't try to start ollama; assume it's already running
#
# Logs are written to $AURORA_LOG_DIR/aurora-{backend,frontend,prewarm}.log
# PIDs are written to $AURORA_LOG_DIR/aurora-{backend,frontend}.pid

set -euo pipefail

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

LOG_DIR="${AURORA_LOG_DIR:-/tmp}"
BACKEND_PORT="${FLASK_PORT:-5001}"
FRONTEND_DEV_PORT="${VITE_PORT:-3000}"
FRONTEND_PROD_PORT=4173  # vite preview default
BACKEND_LOG="$LOG_DIR/aurora-backend.log"
FRONTEND_LOG="$LOG_DIR/aurora-frontend.log"
PREWARM_LOG="$LOG_DIR/aurora-prewarm.log"
BACKEND_PID="$LOG_DIR/aurora-backend.pid"
FRONTEND_PID="$LOG_DIR/aurora-frontend.pid"

# Color output (gracefully degrades on dumb terminals)
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
  C_GREEN=$(tput setaf 2); C_RED=$(tput setaf 1); C_YELLOW=$(tput setaf 3)
  C_BLUE=$(tput setaf 4); C_DIM=$(tput dim); C_RESET=$(tput sgr0); C_BOLD=$(tput bold)
else
  C_GREEN=""; C_RED=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_RESET=""; C_BOLD=""
fi

ok()    { echo "${C_GREEN}✓${C_RESET} $1"; }
warn()  { echo "${C_YELLOW}!${C_RESET} $1"; }
err()   { echo "${C_RED}✗${C_RESET} $1" >&2; }
info()  { echo "${C_BLUE}→${C_RESET} $1"; }
title() { echo ""; echo "${C_BOLD}=== $1 ===${C_RESET}"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

require() {
  local name="$1" how="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    err "$name not found. Install via: $how"
    exit 1
  fi
}

preflight() {
  title "Preflight"
  require python3 "https://www.python.org/downloads/  (or pyenv)"
  require node "https://nodejs.org/  (or nvm)"
  require npm "ships with node"

  if [ -z "${AURORA_NO_DOCKER:-}" ]; then
    if ! command -v docker >/dev/null 2>&1; then
      warn "docker not found — Neo4j won't be started. Set AURORA_NO_DOCKER=1 to silence this."
      AURORA_NO_DOCKER=1
    fi
  fi

  if [ -z "${AURORA_NO_OLLAMA:-}" ]; then
    if ! command -v ollama >/dev/null 2>&1; then
      warn "ollama not found — LLM-backed runs will fall back to synth. Set AURORA_NO_OLLAMA=1 to silence."
      AURORA_NO_OLLAMA=1
    fi
  fi

  ok "preflight done"
}

# ---------------------------------------------------------------------------
# Health-check helpers
# ---------------------------------------------------------------------------

is_port_open() {
  local port="$1"
  (echo > "/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
}

wait_for_port() {
  local port="$1" name="$2" timeout="${3:-30}"
  local i=0
  while [ $i -lt "$timeout" ]; do
    if is_port_open "$port"; then
      ok "$name listening on :$port"
      return 0
    fi
    sleep 1
    i=$((i+1))
  done
  err "$name failed to start on :$port within ${timeout}s — see log"
  return 1
}

# ---------------------------------------------------------------------------
# Component starters
# ---------------------------------------------------------------------------

start_neo4j() {
  if [ -n "${AURORA_NO_DOCKER:-}" ]; then
    info "skipping Neo4j (AURORA_NO_DOCKER set)"
    return 0
  fi
  title "Neo4j"
  if docker ps --format '{{.Names}}' | grep -q '^aurora-neo4j$'; then
    ok "Neo4j container 'aurora-neo4j' already running"
  else
    info "starting Neo4j via docker compose..."
    docker compose up -d neo4j >/dev/null 2>&1 || {
      warn "docker compose failed — backend will run without graph storage"
      return 0
    }
    ok "Neo4j started"
  fi
}

start_backend() {
  title "Backend"
  if [ -f "$BACKEND_PID" ] && kill -0 "$(cat "$BACKEND_PID")" 2>/dev/null; then
    ok "backend already running (PID $(cat "$BACKEND_PID"))"
    return 0
  fi
  info "booting Flask on :$BACKEND_PORT (log: $BACKEND_LOG)"
  ( cd "$REPO_ROOT/backend" && \
    FLASK_PORT="$BACKEND_PORT" python3 run.py > "$BACKEND_LOG" 2>&1 ) &
  echo $! > "$BACKEND_PID"
  wait_for_port "$BACKEND_PORT" "Flask backend" 20 || {
    err "see $BACKEND_LOG"
    tail -20 "$BACKEND_LOG"
    return 1
  }
}

start_frontend_dev() {
  title "Frontend (dev)"
  if [ -f "$FRONTEND_PID" ] && kill -0 "$(cat "$FRONTEND_PID")" 2>/dev/null; then
    ok "frontend already running (PID $(cat "$FRONTEND_PID"))"
    return 0
  fi
  if [ ! -d "$REPO_ROOT/frontend/node_modules" ]; then
    info "installing npm deps (first run only)..."
    ( cd "$REPO_ROOT/frontend" && npm install >/dev/null 2>&1 )
  fi
  info "booting vite dev on :$FRONTEND_DEV_PORT (log: $FRONTEND_LOG)"
  ( cd "$REPO_ROOT/frontend" && npm run dev > "$FRONTEND_LOG" 2>&1 ) &
  echo $! > "$FRONTEND_PID"
  wait_for_port "$FRONTEND_DEV_PORT" "Vite dev" 30 || {
    err "see $FRONTEND_LOG"
    tail -20 "$FRONTEND_LOG"
    return 1
  }
}

start_frontend_prod() {
  title "Frontend (prod)"
  if [ -f "$FRONTEND_PID" ] && kill -0 "$(cat "$FRONTEND_PID")" 2>/dev/null; then
    ok "frontend already running (PID $(cat "$FRONTEND_PID"))"
    return 0
  fi
  if [ ! -d "$REPO_ROOT/frontend/node_modules" ]; then
    info "installing npm deps..."
    ( cd "$REPO_ROOT/frontend" && npm install >/dev/null 2>&1 )
  fi
  info "building prod bundle..."
  ( cd "$REPO_ROOT/frontend" && npm run build > "$FRONTEND_LOG" 2>&1 ) || {
    err "prod build failed — see $FRONTEND_LOG"
    tail -20 "$FRONTEND_LOG"
    return 1
  }
  ok "build complete"
  info "booting vite preview on :$FRONTEND_PROD_PORT"
  ( cd "$REPO_ROOT/frontend" && npm run preview >> "$FRONTEND_LOG" 2>&1 ) &
  echo $! > "$FRONTEND_PID"
  wait_for_port "$FRONTEND_PROD_PORT" "Vite preview" 15 || {
    err "see $FRONTEND_LOG"
    return 1
  }
}

prewarm() {
  title "Prewarm Ollama"
  if [ -n "${AURORA_NO_OLLAMA:-}" ]; then
    warn "AURORA_NO_OLLAMA set — skipping"
    return 0
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    warn "ollama not on PATH — skipping"
    return 0
  fi
  if ! ollama list 2>/dev/null | grep -q 'gemma4:e2b'; then
    warn "gemma4:e2b not pulled. Run: ollama pull gemma4:e2b"
  fi
  if ! ollama list 2>/dev/null | grep -q 'gemma4:e4b'; then
    warn "gemma4:e4b not pulled. Run: ollama pull gemma4:e4b"
  fi
  info "running prewarm (this loads weights into RAM, ~30-60s)..."
  python3 "$REPO_ROOT/backend/scripts/prewarm_ollama.py" > "$PREWARM_LOG" 2>&1 || {
    warn "prewarm exited non-zero — see $PREWARM_LOG"
    return 0
  }
  ok "prewarm done — Gemma 4 ready"
}

stop_all() {
  title "Stopping Aurora"
  for pidf in "$BACKEND_PID" "$FRONTEND_PID"; do
    if [ -f "$pidf" ]; then
      pid=$(cat "$pidf")
      if kill -0 "$pid" 2>/dev/null; then
        info "killing PID $pid ($(basename "$pidf"))"
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
      fi
      rm -f "$pidf"
    fi
  done
  # Belt-and-suspenders: kill any rogue python run.py / vite that survived
  pkill -f "python.*backend/run.py" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  ok "stopped (Neo4j container left running — use 'docker compose down' to stop it)"
}

clean_all() {
  title "Cleaning"
  find "$REPO_ROOT/backend" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  rm -rf "$REPO_ROOT/frontend/dist" "$REPO_ROOT/frontend/node_modules/.vite" 2>/dev/null || true
  rm -f "$BACKEND_LOG" "$FRONTEND_LOG" "$PREWARM_LOG"
  ok "cleaned: __pycache__, dist/, .vite, logs"
}

# ---------------------------------------------------------------------------
# Health check (curl every endpoint, report)
# ---------------------------------------------------------------------------

health_check() {
  title "Health check"
  local fail=0

  # Backend health endpoint
  if ! is_port_open "$BACKEND_PORT"; then
    err "backend not listening on :$BACKEND_PORT"
    fail=1
  else
    local hc
    hc=$(curl -fsS "http://localhost:$BACKEND_PORT/health" 2>/dev/null || echo '{}')
    if echo "$hc" | grep -qE '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      ok "backend /health: $(echo "$hc")"
    else
      err "backend /health unhealthy: $hc"
      fail=1
    fi
  fi

  # Scenarios list
  local scn
  scn=$(curl -fsS "http://localhost:$BACKEND_PORT/api/scenario/list" 2>/dev/null || echo '{}')
  local count
  count=$(echo "$scn" | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get("data",{}).get("scenarios",[])))' 2>/dev/null || echo 0)
  if [ "$count" -ge 6 ]; then
    ok "scenarios listed: $count"
  else
    err "expected ≥6 scenarios, got $count"
    fail=1
  fi

  # Quick MC smoke on the LA scenario (synth-only, ≤1s)
  local mc
  mc=$(curl -fsS -X POST -H 'Content-Type: application/json' \
    -d '{"intervention_ids":[],"n_trials":1,"n_population_agents":20,"duration_hours":6,"use_llm":false}' \
    "http://localhost:$BACKEND_PORT/api/scenario/la-puente-hills-m72-ref/run_mc" 2>/dev/null || echo '{}')
  if echo "$mc" | grep -qE '"success"[[:space:]]*:[[:space:]]*true'; then
    ok "LA M7.2 MC smoke: 200"
  else
    err "MC smoke failed"
    fail=1
  fi

  # Frontend
  if is_port_open "$FRONTEND_DEV_PORT"; then
    ok "frontend dev on :$FRONTEND_DEV_PORT"
  elif is_port_open "$FRONTEND_PROD_PORT"; then
    ok "frontend prod preview on :$FRONTEND_PROD_PORT"
  else
    warn "no frontend running — try ./start.sh frontend"
  fi

  # Ollama (if enabled)
  if [ -z "${AURORA_NO_OLLAMA:-}" ] && command -v ollama >/dev/null 2>&1; then
    if ollama list 2>/dev/null | grep -q gemma4; then
      ok "Ollama has gemma4 models pulled"
    else
      warn "Ollama running but no gemma4 models — LLM path will 404"
    fi
  fi

  echo ""
  if [ $fail -eq 0 ]; then
    echo "${C_GREEN}${C_BOLD}All systems green.${C_RESET}  Open http://localhost:${FRONTEND_DEV_PORT}/aurora?seed=demo"
  else
    echo "${C_RED}${C_BOLD}$fail check(s) failed.${C_RESET}  See $LOG_DIR/aurora-*.log"
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

mode="${1:-dev}"

case "$mode" in
  dev|"")
    preflight
    start_neo4j
    start_backend
    start_frontend_dev
    health_check
    echo ""
    info "${C_DIM}Logs: $LOG_DIR/aurora-{backend,frontend}.log${C_RESET}"
    info "${C_DIM}Stop with:  ./start.sh stop${C_RESET}"
    ;;
  prod)
    preflight
    start_neo4j
    start_backend
    start_frontend_prod
    health_check
    echo ""
    info "${C_DIM}Production preview at http://localhost:$FRONTEND_PROD_PORT/aurora?seed=demo${C_RESET}"
    ;;
  backend)
    preflight
    start_backend
    ;;
  frontend)
    preflight
    start_frontend_dev
    ;;
  prewarm)
    preflight
    prewarm
    ;;
  check|health)
    health_check
    ;;
  stop|kill)
    stop_all
    ;;
  clean)
    clean_all
    ;;
  -h|--help|help)
    sed -n '2,25p' "$0"
    ;;
  *)
    err "unknown mode: $mode"
    echo "Try: ./start.sh help"
    exit 2
    ;;
esac
