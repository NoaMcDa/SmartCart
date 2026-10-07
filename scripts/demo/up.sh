#!/usr/bin/env bash
# SmartCart full-stack demo on synthetic data: Postgres, migrations, catalog seed, the chains'
# synthetic transparency files through the real loader and quality gates, the matching pipeline,
# the nightly precompute, and the API. See docs/fullstack.md.
#
#   scripts/demo/up.sh            # from the repo root; re-running is safe (idempotent)
#   scripts/demo/down.sh          # stop the API and the throwaway Postgres
#
# Environment (all optional):
#   DATABASE_URL        use this database instead of starting a throwaway cluster (CI does)
#   SMARTCART_DEMO_DIR  state directory (default ${TMPDIR:-/tmp}/smartcart-demo)
#   DEMO_PG_PORT        port of the throwaway cluster (default 54329)
#   DEMO_API_PORT       API port (default 8000)
#   DEMO_WEB_ORIGINS    extra CORS origins, comma separated
#   SUPABASE_JWT_SECRET JWT secret the API verifies with (default: the demo secret in demo_user.py)
#   DEMO_STRICT_COUNTS  1: fail when a pipeline count differs from scripts/demo/expected_counts.json
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export SMARTCART_DEMO_DIR="${SMARTCART_DEMO_DIR:-${TMPDIR:-/tmp}/smartcart-demo}"
API_PORT="${DEMO_API_PORT:-8000}"
mkdir -p "$SMARTCART_DEMO_DIR"
LOG_DIR="$SMARTCART_DEMO_DIR/logs"
mkdir -p "$LOG_DIR"

step() { printf '\n==> %s\n' "$*"; }
py() { uv run --quiet python "$@"; }

step "Database"
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "using DATABASE_URL from the environment"
  echo "external" >"$SMARTCART_DEMO_DIR/db-source"
else
  DATABASE_URL="$(python3 scripts/demo/pg.py start)"
  echo "throwaway cluster: $DATABASE_URL"
  echo "throwaway" >"$SMARTCART_DEMO_DIR/db-source"
fi
export DATABASE_URL

step "Migrations (smartcart-ingest migrate)"
if ! uv run --quiet smartcart-ingest migrate >"$LOG_DIR/migrate.log" 2>&1; then
  cat "$LOG_DIR/migrate.log" >&2
  exit 1
fi
echo "$(grep -c '^applied ' "$LOG_DIR/migrate.log" || true) migrations applied now (log: $LOG_DIR/migrate.log)"

step "Catalog seed (taxonomy, product type rules, canonicals)"
uv run --quiet smartcart-catalog seed

step "Ingestion: synthetic fixtures for every chain, through the gates"
if ! py scripts/demo/load_fixtures.py >"$SMARTCART_DEMO_DIR/load.json" 2>"$LOG_DIR/load.log"; then
  tail -n 40 "$LOG_DIR/load.log" >&2
  exit 1
fi
py - "$SMARTCART_DEMO_DIR/load.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("file_tracking:", d["file_tracking"])
print("rows:", d["rows"])
print("new alerts this run:", len(d["alerts"]))
PY
AS_OF="$(py -c 'import json, sys; print(json.load(open(sys.argv[1]))["as_of_utc"])' "$SMARTCART_DEMO_DIR/load.json")"

step "Catalog: normalize, rule extraction, hash embeddings, rule judge"
uv run --quiet smartcart-catalog normalize --show 0
uv run --quiet smartcart-catalog extract --extractor rule
uv run --quiet smartcart-catalog embed --target all --embedder hash
uv run --quiet smartcart-catalog judge --judge rule

step "Review queue: the demo answer key stands in for the human reviewer"
py scripts/demo/review.py

step "Precompute effective prices as of $AS_OF UTC (the replayed clock)"
# --as-of takes a time without a zone; PGTZ makes the session read it as UTC on any server.
PGTZ=UTC uv run --quiet smartcart-api precompute --as-of "$AS_OF" 2>>"$LOG_DIR/precompute.log"

step "Demo user"
export SUPABASE_JWT_SECRET="${SUPABASE_JWT_SECRET:-$(py -c 'import sys; sys.path.insert(0, "scripts/demo"); import demo_user; print(demo_user.DEMO_JWT_SECRET)')}"
py scripts/demo/demo_user.py ensure

step "Pipeline counts"
COUNT_ARGS=(--expect scripts/demo/expected_counts.json)
if ! py scripts/demo/counts.py "${COUNT_ARGS[@]}" >"$SMARTCART_DEMO_DIR/counts.json"; then
  if [[ "${DEMO_STRICT_COUNTS:-0}" == "1" ]]; then
    cat "$SMARTCART_DEMO_DIR/counts.json"
    echo "pipeline counts differ from scripts/demo/expected_counts.json (DEMO_STRICT_COUNTS=1)" >&2
    exit 1
  fi
  echo "warning: pipeline counts differ from scripts/demo/expected_counts.json (see above)" >&2
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "::warning::demo pipeline counts differ from scripts/demo/expected_counts.json; update it if the change is intended"
  fi
fi
cat "$SMARTCART_DEMO_DIR/counts.json"

step "API on port $API_PORT"
PID_FILE="$SMARTCART_DEMO_DIR/api.pid"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "stopping the previous API (pid $(cat "$PID_FILE"))"
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
  for _ in $(seq 1 50); do kill -0 "$(cat "$PID_FILE")" 2>/dev/null || break; sleep 0.1; done
fi
if curl -fsS "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
  echo "port $API_PORT is already serving something else; stop it or set DEMO_API_PORT" >&2
  exit 1
fi
ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3200,http://127.0.0.1:3200"
if [[ -n "${DEMO_WEB_ORIGINS:-}" ]]; then ORIGINS="$ORIGINS,$DEMO_WEB_ORIGINS"; fi
# The API's own .venv entry point, so the pid is the server's and down.sh can stop it.
API_BIN="$ROOT/.venv/bin/smartcart-api"
[[ -x "$API_BIN" ]] || uv sync --quiet
API_CORS_ORIGINS="$ORIGINS" API_PUBLIC_WEB_URL="http://localhost:3200" \
  nohup "$API_BIN" serve --host 127.0.0.1 --port "$API_PORT" >"$LOG_DIR/api.log" 2>&1 &
echo $! >"$PID_FILE"
for _ in $(seq 1 100); do
  if curl -fsS "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then break; fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "the API exited; last lines of $LOG_DIR/api.log:" >&2
    tail -n 30 "$LOG_DIR/api.log" >&2
    exit 1
  fi
  sleep 0.2
done
curl -fsS "http://127.0.0.1:$API_PORT/health"
echo

ENV_FILE="$SMARTCART_DEMO_DIR/env"
cat >"$ENV_FILE" <<EOF
export DATABASE_URL='$DATABASE_URL'
export SUPABASE_JWT_SECRET='$SUPABASE_JWT_SECRET'
export DEMO_API_BASE_URL='http://127.0.0.1:$API_PORT'
export NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:$API_PORT'
export NEXT_PUBLIC_API_MOCK=0
EOF

step "Ready"
cat <<EOF
API:        http://127.0.0.1:$API_PORT  (docs at /docs, log $LOG_DIR/api.log)
State:      $SMARTCART_DEMO_DIR
Env file:   $ENV_FILE

The web app against this API (NEXT_PUBLIC_* are inlined at build time):
  export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$API_PORT
  export NEXT_PUBLIC_API_MOCK=0
  cd apps/web && npm run build && npm start      # or: npm run dev

Checks:
  uv run python scripts/demo/smoke.py
  (cd apps/web && npm run e2e:fullstack)
EOF
