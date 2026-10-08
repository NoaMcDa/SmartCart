#!/usr/bin/env bash
# Phase 0 exit dry run (issue #60): load the real and the synthetic transparency fixtures through
# the real Scheduler path into throwaway databases with the clock replayed, run the exit report
# generator over each window, and write docs/phase-0-exit-dry-run.md.
#
# THIS IS NOT THE EXIT VALIDATION. The exit needs 14 consecutive nightly loads on the VPS; the
# generated file says so and lists what cannot pass yet. See scripts/exit_dry_run/dry_run.py.
#
#   scripts/exit_dry_run/run.sh [--out FILE] [--keep]     # from anywhere; takes about 15 seconds
#
# Environment (all optional):
#   DATABASE_URL            a Postgres SERVER to use (the script creates and drops the databases
#                           exit_dry_run_real and exit_dry_run_synthetic on it; it needs CREATE
#                           DATABASE, PostGIS and pgvector available). Without it a throwaway
#                           cluster is started and stopped, like scripts/demo/up.sh does.
#   SMARTCART_DRY_RUN_DIR   state directory of the throwaway cluster
#                           (default ${TMPDIR:-/tmp}/smartcart-exit-dry-run; as root it must lie
#                           under a directory the postgres user can traverse, such as /tmp)
#   DRY_RUN_PG_PORT         port of the throwaway cluster (default 54339)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

step() { printf '\n==> %s\n' "$*"; }

started_cluster=0
cleanup() {
  if [[ "$started_cluster" == 1 ]]; then
    step "Stopping the throwaway Postgres"
    SMARTCART_DEMO_DIR="$SMARTCART_DRY_RUN_DIR" python3 scripts/demo/pg.py stop >/dev/null || true
  fi
}
trap cleanup EXIT

step "Database server"
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "using the server in DATABASE_URL (databases exit_dry_run_real and exit_dry_run_synthetic are created and dropped there)"
else
  export SMARTCART_DRY_RUN_DIR="${SMARTCART_DRY_RUN_DIR:-${TMPDIR:-/tmp}/smartcart-exit-dry-run}"
  # scripts/demo/pg.py is the demo's throwaway cluster; this run gets its own directory and port.
  DATABASE_URL="$(SMARTCART_DEMO_DIR="$SMARTCART_DRY_RUN_DIR" DEMO_PG_PORT="${DRY_RUN_PG_PORT:-54339}" \
    python3 scripts/demo/pg.py start)"
  started_cluster=1
  echo "throwaway cluster: $DATABASE_URL"
fi
export DATABASE_URL

step "Load the fixtures, run the report, write the dry run"
uv run --quiet python scripts/exit_dry_run/dry_run.py "$@"
