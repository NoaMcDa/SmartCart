"""Create the Supabase project from one management token and print the connection strings the
runbook needs (issue #14, the one-secret path in docs/infra-provisioning.md section 9).

    export SUPABASE_ACCESS_TOKEN=...          # supabase.com, Account, Access Tokens
    python3 scripts/unblock/supabase_provision.py --org-id <org id> --dry-run   # requests only
    python3 scripts/unblock/supabase_provision.py --org-id <org id> [--region eu-central-1]
    python3 scripts/unblock/supabase_provision.py --ref <project ref>    # existing project

Steps: ``POST /v1/projects`` (name, organization, region, database password), poll
``GET /v1/projects/{ref}`` until the status is ``ACTIVE_HEALTHY``, enable postgis, vector and
pg_trgm in the ``extensions`` schema through ``POST /v1/projects/{ref}/database/query``, and read
the pooler strings from ``GET /v1/projects/{ref}/config/database/pooler``. Standard library only.

The endpoint paths and fields are from the Supabase Management API as the author knows it and are
**unverified** here (this environment cannot reach api.supabase.com): ``--dry-run`` prints every
request so they can be checked against the current API reference before the first real run.
Nothing is written to disk. The database password comes from ``$SUPABASE_DB_PASSWORD`` or is
generated and printed once; put it in the password manager, never in the repo. The printed
connection strings carry ``<password>`` in its place.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

API = "https://api.supabase.com"
EXTENSIONS_SQL = (
    "create extension if not exists postgis with schema extensions; "
    "create extension if not exists vector with schema extensions; "
    "create extension if not exists pg_trgm with schema extensions; "
    "select extname, extversion from pg_extension "
    "where extname in ('postgis', 'vector', 'pg_trgm') order by 1;"
)
READY = "ACTIVE_HEALTHY"
FAILED = {"INIT_FAILED", "REMOVED", "RESTORE_FAILED", "PAUSE_FAILED"}

Transport = Callable[[str, str, dict[str, Any] | None], Any]


def http_transport(token: str) -> Transport:
    def call(method: str, path: str, body: dict[str, Any] | None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed host
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise SystemExit(f"{method} {path}: HTTP {exc.code}: {detail}") from exc
        return json.loads(raw) if raw else None

    return call


def redact(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if body is None:
        return None
    return {k: ("<redacted>" if k == "db_pass" else v) for k, v in body.items()}


def dry_run_transport(out=sys.stdout) -> Transport:  # noqa: ANN001
    """Print each request and answer with a plausible response, so the whole flow is shown."""

    def call(method: str, path: str, body: dict[str, Any] | None) -> Any:
        shown = json.dumps(redact(body), ensure_ascii=False) if body is not None else ""
        print(f"{method} {API}{path} {shown}".rstrip(), file=out)
        if method == "POST" and path == "/v1/projects":
            return {"id": "<ref>", "ref": "<ref>", "status": "COMING_UP"}
        if method == "GET" and path.endswith("/config/database/pooler"):
            return [{"pool_mode": "session", "connection_string": "postgresql://postgres.<ref>:"
                     "[YOUR-PASSWORD]@<pooler host>:5432/postgres"}]  # fmt: skip
        if method == "GET":
            return {"status": READY}
        return []

    return call


def wait_ready(
    call: Transport, ref: str, timeout: float, poll: float, sleep: Callable[[float], None]
) -> str:
    waited = 0.0
    while True:
        status = (call("GET", f"/v1/projects/{ref}", None) or {}).get("status", "?")
        print(f"project {ref}: {status}", file=sys.stderr)
        if status == READY:
            return status
        if status in FAILED:
            raise SystemExit(f"project {ref} ended in {status}")
        if waited >= timeout:
            raise SystemExit(f"project {ref} not ready after {waited:.0f}s (last status {status})")
        sleep(poll)
        waited += poll


def connection_strings(ref: str, pooler: Any) -> dict[str, str]:
    """Direct and pooler strings with ``<password>`` in place of the password."""
    out = {
        "DATABASE_URL_DIRECT (direct; IPv6 unless the IPv4 add-on is on)": (
            f"postgresql://postgres:<password>@db.{ref}.supabase.co:5432/postgres?sslmode=require"
        )
    }
    for entry in pooler if isinstance(pooler, list) else [pooler] if pooler else []:
        conn = entry.get("connection_string") if isinstance(entry, dict) else None
        if conn:
            mode = entry.get("pool_mode", "?")
            conn = conn.replace("[YOUR-PASSWORD]", "<password>")
            if "sslmode=" not in conn:
                conn += ("&" if "?" in conn else "?") + "sslmode=require"
            out[f"pooler, {mode} mode"] = conn
    return out


def provision(
    call: Transport,
    *,
    org_id: str | None,
    ref: str | None,
    name: str,
    region: str,
    password: str,
    timeout: float = 900,
    poll: float = 15,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if ref is None:
        if not org_id:
            raise SystemExit("--org-id is required to create a project (or pass --ref)")
        created = call("POST", "/v1/projects", {"name": name, "organization_id": org_id,
                                                "region": region, "db_pass": password})  # fmt: skip
        ref = created.get("ref") or created.get("id")
        if not ref:
            raise SystemExit(f"no project ref in the response: {created}")
    wait_ready(call, ref, timeout, poll, sleep)
    extensions = call("POST", f"/v1/projects/{ref}/database/query", {"query": EXTENSIONS_SQL})
    pooler = call("GET", f"/v1/projects/{ref}/config/database/pooler", None)
    return {"ref": ref, "extensions": extensions, "connections": connection_strings(ref, pooler)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--org-id", default=os.environ.get("SUPABASE_ORG_ID"),
                    help="organization id (or $SUPABASE_ORG_ID)")  # fmt: skip
    ap.add_argument("--ref", default=None, help="use this existing project instead of creating one")
    ap.add_argument("--name", default="smartcart")
    ap.add_argument("--region", default="eu-central-1",
                    help="no Israeli region exists; Frankfurt is the working choice (estimate)")  # fmt: skip
    ap.add_argument("--timeout", type=float, default=900, help="seconds to wait for the project")
    ap.add_argument("--dry-run", action="store_true", help="print the requests, call nothing")
    args = ap.parse_args(argv)

    password = os.environ.get("SUPABASE_DB_PASSWORD") or ""
    generated = False
    if args.dry_run:
        call = dry_run_transport()
        password = password or "<generated>"
    else:
        token = os.environ.get("SUPABASE_ACCESS_TOKEN")
        if not token:
            print("SUPABASE_ACCESS_TOKEN is not set (supabase.com, Account, Access Tokens)",
                  file=sys.stderr)  # fmt: skip
            return 2
        call = http_transport(token)
        if not password and args.ref is None:
            password = secrets.token_urlsafe(32)
            generated = True

    result = provision(call, org_id=args.org_id, ref=args.ref, name=args.name,
                       region=args.region, password=password, timeout=args.timeout,
                       sleep=(lambda s: None) if args.dry_run else time.sleep)  # fmt: skip
    print(f"\nproject ref: {result['ref']}")
    print(f"extensions:  {json.dumps(result['extensions'], ensure_ascii=False)}")
    print("connection strings (replace <password>; keep them in the password manager):")
    for label, conn in result["connections"].items():
        print(f"  {label}:\n    {conn}")
    print("\nNext: set the repository secret SUPABASE_DB_URL to the session pooler string (with the"
          " password) and run the 'Provision check' workflow; docs/infra-provisioning.md section 9.")  # fmt: skip
    if generated:
        print("\nGenerated database password (shown once; store it in the password manager now):",
              file=sys.stderr)  # fmt: skip
        print(password, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
