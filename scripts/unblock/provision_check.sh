#!/usr/bin/env bash
# Run one provisioning smoke test when its secret is present, else say what to set (issues #14
# and #22). What .github/workflows/provision-check.yml runs; works the same on a laptop.
#
#   scripts/unblock/provision_check.sh db       # SUPABASE_DB_URL -> infra/smoke/db_smoke.sql
#   scripts/unblock/provision_check.sh vps      # VPS_SSH_HOST + VPS_SSH_KEY -> check_israeli_ip.sh
#                                               #   and check_portals.sh, run on the VPS over ssh
#   scripts/unblock/provision_check.sh bucket   # S3_* -> infra/smoke/bucket_roundtrip.py
#
# Environment:
#   db:     SUPABASE_DB_URL (the postgres user's connection string; from a GitHub runner use the
#           session pooler string, runners have no IPv6). APPLY_MIGRATIONS=1 also runs
#           `smartcart-ingest migrate` against it (idempotent; off by default).
#   vps:    VPS_SSH_HOST, VPS_SSH_KEY (private key text); optional VPS_SSH_USER (default admin,
#           the user docs/infra-provisioning.md section 5.2 creates), VPS_SSH_PORT (22),
#           VPS_SSH_KNOWN_HOSTS (the host's known_hosts line; without it the key is learned on
#           first use with ssh-keyscan and its fingerprint printed).
#   bucket: S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY; optional S3_ENDPOINT_URL (R2),
#           S3_REGION, S3_KEY_PREFIX, SMOKE_REQUIRE_DELETE.
#   SUMMARY_OUT=<file> appends a Markdown section (the workflow uses $GITHUB_STEP_SUMMARY).
#
# Exit codes: 0 passed, or not configured (the message says what to set); 1 a smoke test failed;
#             2 usage error. Secrets are never echoed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUMMARY_OUT="${SUMMARY_OUT:-}"

say() {
  printf '%s\n' "$*"
  if [[ -n "$SUMMARY_OUT" ]]; then printf '%s\n' "$*" >>"$SUMMARY_OUT"; fi
}

not_set() {
  # $1 check name, $2 what to set
  say "NOT SET: $1 skipped. $2"
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::notice title=$1 not configured::$2"; fi
  exit 0
}

missing() {
  # Echo the names of the empty variables among the arguments.
  local out=() name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then out+=("$name"); fi
  done
  echo "${out[*]:-}"
}

check_db() {
  say "### Database (issue #14)"
  local miss
  miss="$(missing SUPABASE_DB_URL)"
  [[ -z "$miss" ]] || not_set "database smoke" "Set the SUPABASE_DB_URL repository secret to the postgres user's connection string (session pooler; GitHub runners have no IPv6). scripts/unblock/supabase_provision.py prints it."
  command -v psql >/dev/null || { say "FAIL: psql is not installed"; exit 1; }
  local out
  out="$(mktemp)"
  if psql "$SUPABASE_DB_URL" -X -v ON_ERROR_STOP=1 -f "$ROOT/infra/smoke/db_smoke.sql" >"$out" 2>&1 \
    && grep -q "smoke ok" "$out"; then
    say "PASS: db_smoke.sql ended with 'smoke ok' (extensions, PostGIS distance, pgvector distance)."
    status=0
  else
    say "FAIL: db_smoke.sql did not reach 'smoke ok'."
    status=1
  fi
  say ""
  say '```'
  say "$(cat "$out")"
  say '```'
  rm -f "$out"
  if [[ "$status" -eq 0 && "${APPLY_MIGRATIONS:-0}" == "1" ]]; then
    say ""
    if (cd "$ROOT" && DATABASE_URL="$SUPABASE_DB_URL" uv run --no-sync smartcart-ingest migrate); then
      say "PASS: smartcart-ingest migrate applied every pending migration."
    else
      say "FAIL: smartcart-ingest migrate failed (see the log)."
      status=1
    fi
  fi
  exit "$status"
}

run_remote() {
  # $1 script path; runs it on the VPS through ssh, streamed on stdin. Echoes the exit code.
  local script="$1" code=0
  ssh -i "$KEY_FILE" -p "${VPS_SSH_PORT:-22}" -o BatchMode=yes -o ConnectTimeout=20 \
    -o UserKnownHostsFile="$KNOWN_HOSTS" -o StrictHostKeyChecking=yes \
    "${VPS_SSH_USER:-admin}@${VPS_SSH_HOST}" 'bash -s' <"$script" >"$WORK/remote.out" 2>&1 || code=$?
  echo "$code"
}

check_vps() {
  say "### Israeli-IP VPS (issue #22)"
  local miss
  miss="$(missing VPS_SSH_HOST VPS_SSH_KEY)"
  [[ -z "$miss" ]] || not_set "VPS smoke" "Set the repository secrets ${miss// /, } (and optionally VPS_SSH_USER, VPS_SSH_PORT, VPS_SSH_KNOWN_HOSTS) after creating the VPS (docs/infra-provisioning.md section 5)."
  WORK="$(mktemp -d)"
  trap 'rm -rf "$WORK"' EXIT
  KEY_FILE="$WORK/key"
  KNOWN_HOSTS="$WORK/known_hosts"
  (umask 077 && printf '%s\n' "$VPS_SSH_KEY" >"$KEY_FILE")
  if [[ -n "${VPS_SSH_KNOWN_HOSTS:-}" ]]; then
    printf '%s\n' "$VPS_SSH_KNOWN_HOSTS" >"$KNOWN_HOSTS"
  else
    ssh-keyscan -p "${VPS_SSH_PORT:-22}" -T 20 "$VPS_SSH_HOST" >"$KNOWN_HOSTS" 2>/dev/null || true
    if [[ ! -s "$KNOWN_HOSTS" ]]; then
      say "FAIL: no ssh host key from ${VPS_SSH_HOST}:${VPS_SSH_PORT:-22} (host down or port closed)."
      exit 1
    fi
    say "Host key learned on first use (set VPS_SSH_KNOWN_HOSTS to pin it):"
    say '```'
    say "$(ssh-keygen -lf "$KNOWN_HOSTS")"
    say '```'
  fi
  local status=0 ip_code portals_code
  ip_code="$(run_remote "$ROOT/infra/smoke/check_israeli_ip.sh")"
  say ""
  say "check_israeli_ip.sh on the VPS: exit ${ip_code} (0 PASS, 1 not Israeli, 2 inconclusive, 255 ssh failed)"
  say '```'
  say "$(cat "$WORK/remote.out")"
  say '```'
  [[ "$ip_code" == "0" || "$ip_code" == "2" ]] || status=1
  portals_code="$(run_remote "$ROOT/infra/smoke/check_portals.sh")"
  say ""
  say "check_portals.sh on the VPS: exit ${portals_code} (0 PASS, 1 a failure, 2 inconclusive: laibcatalog listing empty before about 08:00 Israel time)"
  say '```'
  say "$(cat "$WORK/remote.out")"
  say '```'
  [[ "$portals_code" == "0" || "$portals_code" == "2" ]] || status=1
  exit "$status"
}

check_bucket() {
  say "### Object storage (issue #22)"
  local miss
  miss="$(missing S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY)"
  [[ -z "$miss" ]] || not_set "bucket round trip" "Set the repository secrets ${miss// /, } (and S3_ENDPOINT_URL for R2, or S3_REGION for S3) with the ingest-writer token (docs/infra-provisioning.md section 6.1)."
  local out status=0
  out="$(mktemp)"
  (cd "$ROOT" && uv run infra/smoke/bucket_roundtrip.py) >"$out" 2>&1 || status=$?
  if [[ "$status" -eq 0 ]]; then say "PASS: upload and read-back worked."; else say "FAIL: bucket_roundtrip.py exit ${status}."; fi
  say '```'
  say "$(cat "$out")"
  say '```'
  rm -f "$out"
  [[ "$status" -eq 0 ]] || exit 1
  exit 0
}

case "${1:-}" in
  db) check_db ;;
  vps) check_vps ;;
  bucket) check_bucket ;;
  *)
    echo "usage: $0 db|vps|bucket" >&2
    exit 2
    ;;
esac
