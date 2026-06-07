#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-localhost}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
BACKEND_CORS_ORIGINS="${BACKEND_CORS_ORIGINS:-*}"
export VITE_API_BASE_URL
export BACKEND_CORS_ORIGINS

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\033[1;34m[dev]\033[0m %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing command: %s\n' "$1" >&2
    exit 1
  fi
}

cleanup() {
  log "stopping dev servers"
  terminate_tree "$FRONTEND_PID"
  terminate_tree "$BACKEND_PID"
}

terminate_tree() {
  local pid="${1:-}"
  local children
  if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
    return
  fi

  children="$(pgrep -P "$pid" 2>/dev/null || true)"
  for child in $children; do
    terminate_tree "$child"
  done

  kill "$pid" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

require_command uv
require_command pnpm
require_command node

node "$ROOT_DIR/scripts/ensure-backend-env.mjs"

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  log "backend virtualenv not found; running uv sync"
  (cd "$BACKEND_DIR" && uv sync)
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "frontend node_modules not found; running pnpm install"
  (cd "$FRONTEND_DIR" && pnpm install)
fi

log "backend  http://${BACKEND_HOST}:${BACKEND_PORT}"
(
  cd "$BACKEND_DIR"
  uv run fastapi dev app/main.py --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

log "frontend http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd "$FRONTEND_DIR"
  pnpm dev --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

log "press Ctrl+C to stop both servers"
while true; do
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    wait "$BACKEND_PID" || exit $?
    exit 0
  fi
  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    wait "$FRONTEND_PID" || exit $?
    exit 0
  fi
  sleep 1
done
