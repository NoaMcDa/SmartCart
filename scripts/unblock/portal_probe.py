"""Probe the ten D13 transparency portals, fetch one Stores and one PriceFull file per chain,
and run every fetched file through the adapter, the quality gates and the loader (issues #32,
#53, #57, #60). What ``.github/workflows/portal-probe.yml`` runs.

    # 1. network: reachability, Cerberus login, downloads (no database)
    uv run --no-sync python scripts/unblock/portal_probe.py probe --out probe/
    # 2. database: the real Scheduler path (download tracking, adapter, gates, loader)
    DATABASE_URL=... uv run --no-sync python scripts/unblock/portal_probe.py gate \\
        --files probe/files --probe probe/probe.json --out probe-report.md --json-out probe.json

``gate`` without ``--probe`` takes any directory laid out as ``<slug>/<portal filename>``, so
``--files services/ingest/tests/fixtures`` runs the synthetic fixtures through the same path
(that is how this script is tested without portal access; those files are past the stale-date
limit, so the gate column shows the gate working).

Only the legally mandated transparency portals are contacted, and downloads go through the
pinned upstream scraper via ``smartcart_ingest.adapters.fetch_fixtures``, never a chain's online
store. Downloaded files are untrusted data: they are read only by the chain adapters, inside
the same Scheduler path the VPS uses (no bypass of the gates). The probe is a measurement: it
exits 0 whatever the portals answer, and non-zero only when the script itself cannot run.
"""

from __future__ import annotations

import argparse
import ftplib
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from _common import REPO, git_sha, md_escape, write_text

ISRAEL = ZoneInfo("Asia/Jerusalem")
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
CERBERUS_HOST = "url.retail.publishedprices.co.il"
KINDS = ("stores", "price_full")


@dataclass(frozen=True)
class Portal:
    slug: str
    name: str
    url: str
    ftp_user: str | None = None  # Cerberus: FTP over TLS, empty password (upstream scrapers)


# The ten D13 chains. URLs and Cerberus users are the ones il_supermarket_scarper 1.0.15 uses
# (scrappers/*.py), the same hosts as infra/smoke/check_portals.sh.
PORTALS: tuple[Portal, ...] = (
    Portal("shufersal", "Shufersal", "https://prices.shufersal.co.il/"),
    Portal("ramilevy", "Rami Levy", f"https://{CERBERUS_HOST}/", "RamiLevi"),
    Portal("victory", "Victory", "https://laibcatalog.co.il/"),
    Portal("mega", "Yeinot Bitan and Carrefour", "https://prices.carrefour.co.il/"),
    Portal("hazihinam", "Hazi Hinam", "https://shop.hazi-hinam.co.il/Prices"),
    Portal("tivtaam", "Tiv Taam", f"https://{CERBERUS_HOST}/", "TivTaam"),
    Portal("osherad", "Osher Ad", f"https://{CERBERUS_HOST}/", "osherad"),
    Portal("yohananof", "Yohananof", f"https://{CERBERUS_HOST}/", "yohananof"),
    Portal("machsanei_hashuk", "Machsanei Hashuk", "https://laibcatalog.co.il/"),
    Portal("king_store", "King Store", "http://kingstore.binaprojects.com/"),
)
BY_SLUG = {p.slug: p for p in PORTALS}


# --- network probes ---------------------------------------------------------------------------------


def classify(code: int) -> str:
    """Same buckets as check_portals.sh."""
    if code == 0:
        return "UNREACHABLE"
    if code in (403, 429):
        return "BLOCKED?"
    if 200 <= code < 400:
        return "OK"
    if code >= 500:
        return "ERROR"
    return "REACHABLE"


def http_status(url: str, timeout: float) -> int:
    """HTTP status of ``url`` (0 when the connection fails). HEAD first, then a one-byte GET,
    because some portals answer HEAD with 403, 405 or 501."""

    def once(method: str) -> int:
        headers = {"User-Agent": UA}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed URLs
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except (urllib.error.URLError, OSError, ValueError):
            return 0

    code = once("HEAD")
    if code in (0, 403, 405, 501):
        code = once("GET")
    return code


def ftp_login(host: str, user: str, timeout: float) -> str:
    """``ok`` when an FTP-over-TLS login as ``user`` (empty password) succeeds, the way the
    upstream Cerberus engine logs in; otherwise ``failed: <reason>``. Lists nothing."""
    try:
        ftp = ftplib.FTP_TLS(host, timeout=timeout, context=ssl.create_default_context())
        try:
            ftp.login(user, "")
            ftp.prot_p()
        finally:
            try:
                ftp.quit()
            except (ftplib.Error, OSError):
                ftp.close()
    except (ftplib.Error, OSError, EOFError) as exc:
        return f"failed: {type(exc).__name__}: {str(exc)[:120]}"
    return "ok"


def fetch_one(slug: str, kind: str, work: Path, files: Path, timeout: float) -> dict:
    """One file of ``kind`` for the chain through ``fetch_fixtures`` in a subprocess (so a hung
    portal is killed), moved to ``files/<slug>/``. Returns the manifest entry."""
    out = work / f"{slug}-{kind}"
    shutil.rmtree(out, ignore_errors=True)
    cmd = [sys.executable, "-m", "smartcart_ingest.adapters.fetch_fixtures", slug,
           "--kind", kind, "--out", str(out), "--timeout", str(timeout)]  # fmt: skip
    started = time.monotonic()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60, cwd=REPO)
        log = (res.stdout + res.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return {"kind": kind, "error": f"timed out after {timeout + 60:.0f}s"}
    entry: dict = {"kind": kind, "error": "no manifest written"}
    manifest = out / "manifest.json"
    if manifest.exists():
        entries = json.loads(manifest.read_text(encoding="utf-8")).get(slug) or []
        entry = entries[0] if entries else entry
    entry["seconds"] = round(time.monotonic() - started, 1)
    if "file" in entry:
        src = out / slug / entry["file"]
        dest = files / slug
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), dest / entry["file"])
    elif "error" in entry:
        entry["log_tail"] = log[-600:]
    return entry


def probe(out: Path, slugs: Sequence[str], timeout: float, skip_downloads: bool) -> dict:
    files = out / "files"
    work = out / "work"
    files.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runner": os.environ.get("RUNNER_NAME") or os.uname().nodename,
        "chains": {},
    }
    ftp_cache: dict[str, str] = {}
    for slug in slugs:
        portal = BY_SLUG[slug]
        code = http_status(portal.url, timeout=20)
        row: dict = {
            "name": portal.name,
            "portal_url": portal.url,
            "http_status": code,
            "reachable": classify(code),
            "login": "n/a",
            "downloads": {},
        }
        if portal.ftp_user:
            if portal.ftp_user not in ftp_cache:
                ftp_cache[portal.ftp_user] = ftp_login(CERBERUS_HOST, portal.ftp_user, timeout=30)
            row["login"] = ftp_cache[portal.ftp_user]
        print(f"{slug:18} http {code:<3} {row['reachable']:<11} login {row['login']}", flush=True)
        if not skip_downloads:
            for kind in KINDS:
                row["downloads"][kind] = fetch_one(slug, kind, work, files, timeout)
                print(f"  {kind:10} {json.dumps(row['downloads'][kind])[:300]}", flush=True)
        result["chains"][slug] = row
    shutil.rmtree(work, ignore_errors=True)
    result["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


# --- gates: the real Scheduler path -------------------------------------------------------------------


@dataclass
class _OneFile:
    chain_id: str
    name: str
    kind: str
    data: bytes


class OneFileFetcher:
    """A portal that lists exactly the one file being processed (cf. scripts/demo)."""

    def __init__(self) -> None:
        self.current: _OneFile | None = None

    def list_files(self, chain_id, kinds=None, since=None):  # noqa: ANN001 - Fetcher protocol
        from smartcart_ingest.download import RemoteFile

        f = self.current
        if f is None or f.chain_id != chain_id or (kinds and f.kind not in kinds):
            return []
        return [RemoteFile(chain_id=chain_id, name=f.name, kind=f.kind)]  # type: ignore[arg-type]

    def fetch(self, remote) -> bytes:  # noqa: ANN001
        assert self.current is not None and remote.name == self.current.name
        return self.current.data


class _Sink:
    def __init__(self) -> None:
        self.alerts: list = []

    def send(self, alert) -> None:  # noqa: ANN001
        self.alerts.append(alert)


def pick_files(files: Path, slug: str, adapter) -> dict[str, Path]:  # noqa: ANN001
    """The newest Stores and PriceFull file under ``files/<slug>`` (by the adapter's filename
    parser; names it does not recognise are ignored)."""
    best: dict[str, tuple[datetime, Path]] = {}
    folder = files / slug
    if not folder.is_dir():
        return {}
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        try:
            info = adapter.parse_filename(path.name)
        except Exception:  # noqa: BLE001 - not a portal file (expected.json, a README)
            continue
        if info.kind not in KINDS:
            continue
        when = info.published_at or datetime.min.replace(tzinfo=ISRAEL)
        if info.kind not in best or when > best[info.kind][0]:
            best[info.kind] = (when, path)
    return {k: v[1] for k, v in best.items()}


def parse_summary(adapter, path: Path) -> dict:  # noqa: ANN001
    """What the adapter reads from the file, outside any database. Errors are reported."""
    data = path.read_bytes()
    try:
        parsed = adapter.parse(adapter.raw_file_for(path.name, data), data)
    except Exception as exc:  # noqa: BLE001 - an adapter failure is a result here
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return {
        "schema": parsed.raw.schema_version,
        "stores": len(parsed.stores),
        "online_stores": sum(1 for s in parsed.stores if s.channel == "online"),
        "items": len(parsed.items),
        "prices": len(parsed.prices),
    }


def _logs_to_stderr() -> None:
    """Pipeline logs (structlog) at warning level on stderr, so stdout carries the report."""
    import logging

    import structlog

    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=lambda *a: structlog.PrintLogger(file=sys.stderr),
    )


def gate(files: Path, slugs: Sequence[str], now: datetime | None) -> dict:
    """Run each chain's picked files through ``Scheduler.run_full`` (Stores first), with the
    real clock unless ``now`` is given, and read the outcome back from ``file_tracking``."""
    import hashlib
    import tempfile

    from smartcart_ingest import db as dbmod
    from smartcart_ingest.adapters import REGISTRY
    from smartcart_ingest.alerts import Alerter
    from smartcart_ingest.rawstore import LocalRawStore
    from smartcart_ingest.scheduler import Scheduler
    from smartcart_ingest.settings import load_settings

    _logs_to_stderr()
    adapters = {getattr(cls, "slug", None): cls for cls in REGISTRY.values()}
    fetcher = OneFileFetcher()
    sink = _Sink()
    out: dict = {}
    clock = (lambda: now) if now else (lambda: datetime.now(tz=ISRAEL))
    raw_dir = Path(tempfile.mkdtemp(prefix="portal-probe-raw-"))
    try:
        with dbmod.connect(autocommit=True) as conn:
            conn.execute("SET TIME ZONE 'UTC'")
            sched = Scheduler(conn, fetcher, LocalRawStore(raw_dir), Alerter([sink]),
                              load_settings(), now=clock, sleep=lambda s: None)  # fmt: skip
            for slug in slugs:
                cls = adapters.get(slug)
                if cls is None:
                    out[slug] = {"error": "no adapter registered"}
                    continue
                adapter = cls()
                results: dict = {}
                for kind, path in sorted(pick_files(files, slug, adapter).items(),
                                         key=lambda kv: KINDS.index(kv[0])):  # fmt: skip
                    data = path.read_bytes()
                    info = adapter.parse_filename(path.name)
                    entry = {
                        "file": path.name,
                        "bytes": len(data),
                        "published_at": (
                            info.published_at.isoformat(timespec="minutes")
                            if info.published_at
                            else None
                        ),
                        "parse": parse_summary(adapter, path),
                    }
                    fetcher.current = _OneFile(adapter.chain_id, path.name, kind, data)
                    report = sched.run_full([adapter.chain_id]).chains[0]
                    fetcher.current = None
                    row = conn.execute(
                        "SELECT id, status, reason, schema_version FROM file_tracking"
                        " WHERE sha256 = %s",
                        (hashlib.sha256(data).hexdigest(),),
                    ).fetchone()
                    if row is None:
                        entry["gate"] = {"status": "not tracked", "error": report.error}
                    else:
                        gates = [g for (g,) in conn.execute(
                            "SELECT gate FROM quarantine_events WHERE file_id = %s ORDER BY id",
                            (row[0],),
                        ).fetchall()]  # fmt: skip
                        entry["gate"] = {"status": row[1], "reason": row[2], "gates": gates,
                                         "schema": row[3]}  # fmt: skip
                    results[kind] = entry
                out[slug] = results
    finally:
        shutil.rmtree(raw_dir, ignore_errors=True)
    return {"files": out, "alerts": [{"chain_id": a.chain_id, "kind": a.kind,
                                      "message": a.message[:300]} for a in sink.alerts]}  # fmt: skip


# --- report --------------------------------------------------------------------------------------------


def _size(n: int | None) -> str:
    if n is None:
        return "-"
    if n < 1024:
        return f"{n} B"
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"


def _download_cell(entry: dict | None, gated: dict | None) -> str:
    if gated:
        return f"`{gated['file']}` {_size(gated['bytes'])}, {gated.get('published_at') or '?'}"
    if entry and entry.get("error"):
        return "no: " + str(entry["error"])[:80]
    return "-"


def _parsed_cell(kind: str, gated: dict | None) -> str:
    if not gated:
        return ""
    p = gated["parse"]
    if "error" in p:
        return f"{'Stores' if kind == 'stores' else 'PriceFull'}: parse error"
    if kind == "stores":
        return f"{p['stores']} stores ({p['online_stores']} online)"
    return f"{p['items']} items, {p['prices']} prices"


def _gate_cell(gated: dict | None) -> str:
    if not gated:
        return ""
    g = gated["gate"]
    status = g.get("status", "?")
    if status == "quarantined" and g.get("gates"):
        return f"quarantined ({', '.join(g['gates'])})"
    if status == "failed":
        return f"failed ({str(g.get('reason') or '')[:60]})"
    return status


def render(probe_result: dict | None, gate_result: dict, slugs: Sequence[str]) -> str:
    chains = (probe_result or {}).get("chains", {})
    files = gate_result["files"]
    lines = [
        "## Transparency portal probe",
        "",
        (
            f"From a GitHub-hosted runner (`{probe_result.get('runner')}`, not an Israeli IP), "
            f"{probe_result.get('started_at')} to {probe_result.get('finished_at')} UTC. "
            "A portal that answers here but blocks cloud ranges elsewhere, or the reverse, is "
            "exactly what this measures; the VPS (#22) is still the production path."
            if probe_result
            else "Offline run: files from a local directory, no portal contacted."
        ),
        "",
        "| chain | portal reachable | login | Stores file | PriceFull file | parsed | gate result"
        " (Stores; PriceFull) | schema |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for slug in slugs:
        c = chains.get(slug, {})
        g = files.get(slug, {}) if isinstance(files.get(slug), dict) else {}
        st, pf = g.get("stores"), g.get("price_full")
        downloads = c.get("downloads", {})
        reach = f"{c['reachable']} ({c['http_status']})" if c else "not probed"
        # The adapter's own reading first: a quarantined Stores file keeps schema 'unknown'.
        schemas = sorted({x["parse"].get("schema") or x["gate"].get("schema") or "?"
                          for x in (st, pf) if x})  # fmt: skip
        parsed = "; ".join(
            x for x in (_parsed_cell("stores", st), _parsed_cell("price_full", pf)) if x
        )
        gates = "; ".join(x for x in (_gate_cell(st), _gate_cell(pf)) if x)
        cells = [
            BY_SLUG[slug].name if slug in BY_SLUG else slug,
            reach,
            c.get("login", "n/a") if c else "-",
            _download_cell(downloads.get("stores"), st),
            _download_cell(downloads.get("price_full"), pf),
            parsed or "-",
            gates or "-",
            ", ".join(schemas) or "-",
        ]
        lines.append("| " + " | ".join(md_escape(x) for x in cells) + " |")
    lines += [
        "",
        "Gate result is the `file_tracking` status after the real Scheduler path (adapter, quality "
        "gates, loader) in a throwaway Postgres: `loaded`, `quarantined (<gates>)` or `failed`. "
        "A PriceFull of a store with no earlier load cannot trip the item-count or price-jump "
        "gates; stale date and zero price still apply. Schema is what the adapter detected "
        "(`v2` relies on the provisional marker, #57).",
        "",
    ]
    errors = [
        (slug, kind, d)
        for slug in slugs
        for kind, d in chains.get(slug, {}).get("downloads", {}).items()
        if d.get("error")
    ]
    if errors:
        lines += [f"<details><summary>Download errors ({len(errors)})</summary>", ""]
        for slug, kind, d in errors:
            tail = [ln for ln in str(d.get("log_tail", "")).splitlines() if ln.strip()][-2:]
            lines.append(f"- `{slug}` {kind}: {md_escape(d['error'])}"
                         + (f" — `{md_escape(' / '.join(tail))[:300]}`" if tail else ""))  # fmt: skip
        lines += ["", "</details>", ""]
    alerts = gate_result.get("alerts") or []
    if alerts:
        lines += ["<details><summary>Alerts raised during the gate run "
                  f"({len(alerts)})</summary>", ""]  # fmt: skip
        lines += [f"- `{a['chain_id']}` {a['kind']}: {md_escape(a['message'])}" for a in alerts]
        lines += ["", "</details>", ""]
    lines.append(f"Commit `{git_sha()}`.")
    return "\n".join(lines) + "\n"


# --- main ----------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="reachability, login and downloads (network, no database)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--chain", action="append", choices=list(BY_SLUG), help="default: all ten")
    p.add_argument("--timeout", type=float, default=180, help="seconds per download")
    p.add_argument("--skip-downloads", action="store_true")
    g = sub.add_parser("gate", help="run the files through the adapters and gates (database)")
    g.add_argument("--files", type=Path, required=True, help="directory of <slug>/<file>")
    g.add_argument("--probe", type=Path, default=None, help="probe.json from the probe step")
    g.add_argument("--chain", action="append", choices=list(BY_SLUG), help="default: all ten")
    g.add_argument("--now", default=None,
                   help="ISO time for the gates' clock (tests only; default: the real clock)")  # fmt: skip
    g.add_argument("--out", type=Path, default=None, help="Markdown table (default stdout)")
    g.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args(argv)
    slugs = args.chain or [p.slug for p in PORTALS]

    if args.cmd == "probe":
        probe(args.out, slugs, args.timeout, args.skip_downloads)
        return 0

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ISRAEL)
    probe_result = None
    if args.probe and args.probe.exists():
        probe_result = json.loads(args.probe.read_text(encoding="utf-8"))
    result = gate(args.files, slugs, now)
    write_text(args.out, render(probe_result, result, slugs))
    if args.json_out:
        write_text(args.json_out, json.dumps({"probe": probe_result, **result},
                                             ensure_ascii=False, indent=2) + "\n")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
