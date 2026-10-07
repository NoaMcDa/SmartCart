#!/usr/bin/env bash
# Stop what scripts/demo/up.sh started: the API and, when up.sh started it, the throwaway
# Postgres cluster (its data directory is deleted). A database given through DATABASE_URL is left
# alone. --keep-db stops only the API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export SMARTCART_DEMO_DIR="${SMARTCART_DEMO_DIR:-${TMPDIR:-/tmp}/smartcart-demo}"
KEEP_DB=0
[[ "${1:-}" == "--keep-db" ]] && KEEP_DB=1

PID_FILE="$SMARTCART_DEMO_DIR/api.pid"
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    for _ in $(seq 1 50); do kill -0 "$PID" 2>/dev/null || break; sleep 0.1; done
    kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
    echo "API stopped (pid $PID)"
  fi
  rm -f "$PID_FILE"
fi

if [[ "$KEEP_DB" == "0" && "$(cat "$SMARTCART_DEMO_DIR/db-source" 2>/dev/null)" == "throwaway" ]]; then
  python3 scripts/demo/pg.py stop
  echo "throwaway Postgres stopped and deleted"
fi
if [[ "$KEEP_DB" == "0" ]]; then
  rm -rf "$SMARTCART_DEMO_DIR"
fi
