"""The daily record of the runner exit window (issue #60): schema, validation and small helpers.

One JSON document per Israel date, written by ``run_day.py`` and appended to the data branch by
``store.py``. Standard library only, no database, no network, so the schema and everything that
reads records (``store.py``, ``report.py``) can be tested offline.

The record says what one nightly rehearsal did, per D13 chain and per file kind (Stores,
PriceFull, PromoFull): whether the portal produced a file, whether the file went through the real
Scheduler path (adapter, quality gates, loader, with the real clock) and what became of it, with
the gate reasons, the publication time in Israel time, row counts and durations. It also records
the runner's IP country, because a GitHub runner is not an Israeli IP and some portals refuse it
(that is part of the measurement, not a defect of the record).

Labels follow ``docs/README.md``: every number in a record is **measured** on that run. Nothing in
a record is an estimate.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

SCHEMA_VERSION = 1
RECORD_KIND = "exit-window-day"
LABEL = "runner rehearsal, not the VPS window"
KINDS = ("stores", "price_full", "promo_full")
FULL_KINDS = ("price_full", "promo_full")
SOURCES = ("portal", "fixtures", "files")
CLOCKS = ("real", "fixed")
STATUS_NOT_DOWNLOADED = "not_downloaded"
STATUS_NOT_TRACKED = "not_tracked"
# file_tracking.status values (supabase/migrations schema_v1) plus the two this record adds.
STATUSES = frozenset(
    {
        "seen",
        "downloaded",
        "held",
        "loading",
        "loaded",
        "quarantined",
        "failed",
        STATUS_NOT_DOWNLOADED,
        STATUS_NOT_TRACKED,
    }
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class RecordError(ValueError):
    """The record does not follow the schema."""


# --- schema ----------------------------------------------------------------------------------


def _need(cond: bool, where: str, what: str) -> None:
    if not cond:
        raise RecordError(f"{where}: {what}")


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def _is_iso(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        datetime.fromisoformat(v)
    except ValueError:
        return False
    return True


def _opt(v: Any, check: Callable[[Any], bool], where: str, what: str) -> None:
    _need(v is None or check(v), where, what)


def _validate_file(f: Any, where: str) -> None:
    _need(isinstance(f, dict), where, "must be an object")
    _need(_is_bool(f.get("downloaded")), where, "downloaded must be a boolean")
    _opt(f.get("listed"), _is_bool, where, "listed must be a boolean or null")
    for key in ("loaded", "quarantined", "failed"):
        _need(_is_bool(f.get(key)), where, f"{key} must be a boolean")
    _need(f.get("status") in STATUSES, where, f"status must be one of {sorted(STATUSES)}")
    _need(
        isinstance(f.get("gates"), list) and all(_is_str(g) for g in f["gates"]),
        where,
        "gates must be a list of strings",
    )
    for key in ("download_error", "reason", "schema", "parse_error", "file"):
        _opt(f.get(key), _is_str, where, f"{key} must be a string or null")
    for key in ("bytes", "stores", "items", "prices", "promos"):
        _opt(f.get(key), lambda v: _is_int(v) and v >= 0, where, f"{key} must be an integer >= 0")
    for key in ("download_seconds", "load_seconds", "age_hours"):
        _opt(f.get(key), _is_num, where, f"{key} must be a number or null")
    _opt(f.get("published_at"), _is_iso, where, "published_at must be an ISO time or null")
    # The booleans must agree with the status, so a reader can trust either.
    _need(f["loaded"] == (f["status"] == "loaded"), where, "loaded disagrees with status")
    _need(f["quarantined"] == (f["status"] == "quarantined"), where, "quarantined disagrees")
    _need(f["failed"] == (f["status"] == "failed"), where, "failed disagrees with status")
    _need(
        f["downloaded"] == (f["status"] != STATUS_NOT_DOWNLOADED),
        where,
        "downloaded disagrees with status",
    )
    if f["status"] == STATUS_NOT_DOWNLOADED:
        _need(f.get("file") is None, where, "a file that was not downloaded has no file name")


def _validate_chain(c: Any, where: str) -> None:
    _need(isinstance(c, dict), where, "must be an object")
    _need(_is_str(c.get("name")) and bool(c["name"]), where, "name must be a string")
    _need(
        isinstance(c.get("chain_ids"), list) and bool(c["chain_ids"]),
        where,
        "chain_ids must be a non-empty list",
    )
    portal = c.get("portal")
    _need(isinstance(portal, dict), where, "portal must be an object")
    _need(_is_int(portal.get("http_status")), where, "portal.http_status must be an integer")
    for key in ("reachable", "login"):
        _need(_is_str(portal.get(key)), where, f"portal.{key} must be a string")
    files = c.get("files")
    _need(isinstance(files, dict) and set(files) == set(KINDS), where, f"files needs {KINDS}")
    for kind in KINDS:
        _validate_file(files[kind], f"{where}.files.{kind}")
    for key in ("listed", "downloaded", "loaded", "quarantined", "failed"):
        _need(_is_int(c.get(key)) and 0 <= c[key] <= len(KINDS), where, f"{key} must be 0..3")
    for key in ("downloaded", "loaded", "quarantined", "failed"):
        want = sum(1 for k in KINDS if files[k][key])
        _need(c[key] == want, where, f"{key} disagrees with the files")
    _need(_is_bool(c.get("full_loaded")), where, "full_loaded must be a boolean")
    _need(
        c["full_loaded"] == any(files[k]["loaded"] for k in FULL_KINDS),
        where,
        "full_loaded disagrees with the files",
    )
    _opt(c.get("failure"), _is_str, where, "failure must be a string or null")
    _need((c["failure"] is None) == c["full_loaded"], where, "failure is set iff not full_loaded")
    _need(
        isinstance(c.get("download_errors"), list)
        and all(_is_str(e) for e in c["download_errors"]),
        where,
        "download_errors must be a list of strings",
    )
    stores = c.get("stores")
    _need(isinstance(stores, dict), where, "stores must be an object")
    for key in ("physical", "with_coordinates"):
        _need(_is_int(stores.get(key)) and stores[key] >= 0, where, f"stores.{key} must be >= 0")
    promos = c.get("promos_by_reward")
    _need(
        isinstance(promos, dict) and all(_is_int(n) and n >= 0 for n in promos.values()),
        where,
        "promos_by_reward must map reward type to a count",
    )


def validate_record(rec: Any) -> dict:
    """Return ``rec`` if it follows the schema; raise ``RecordError`` naming the first problem.

    Records come from the data branch, which a person could edit, and are summarised into a job
    summary, so everything the report prints is type-checked here."""
    _need(isinstance(rec, dict), "record", "must be an object")
    _need(
        rec.get("schema_version") == SCHEMA_VERSION,
        "record",
        f"schema_version must be {SCHEMA_VERSION}",
    )
    _need(rec.get("kind") == RECORD_KIND, "record", f"kind must be {RECORD_KIND!r}")
    d = rec.get("date")
    _need(_is_str(d) and bool(DATE_RE.match(d)), "record", "date must be YYYY-MM-DD")
    try:
        date.fromisoformat(d)
    except ValueError as exc:
        raise RecordError(f"record: date is not a calendar date: {d}") from exc
    run = rec.get("run")
    _need(isinstance(run, dict), "run", "must be an object")
    _need(run.get("source") in SOURCES, "run", f"source must be one of {SOURCES}")
    _need(run.get("clock") in CLOCKS, "run", f"clock must be one of {CLOCKS}")
    for key in ("started_at", "finished_at"):
        _need(_is_iso(run.get(key)), "run", f"{key} must be an ISO time")
    for key in ("duration_seconds", "download_seconds", "load_seconds"):
        _need(_is_num(run.get(key)) and run[key] >= 0, "run", f"{key} must be a number >= 0")
    _need(_is_str(run.get("runner_ip_country")), "run", "runner_ip_country must be a string")
    for key in ("event", "ref", "commit", "run_id", "run_url"):
        _opt(run.get(key), _is_str, "run", f"{key} must be a string or null")
    chains = rec.get("chains")
    _need(isinstance(chains, dict) and bool(chains), "record", "chains must be a non-empty object")
    for slug, chain in chains.items():
        _need(_is_str(slug) and bool(_SLUG_RE.match(slug)), "chains", f"bad slug {slug!r}")
        _validate_chain(chain, f"chains.{slug}")
    alerts = rec.get("alerts")
    _need(isinstance(alerts, list), "record", "alerts must be a list")
    for a in alerts:
        _need(
            isinstance(a, dict) and all(_is_str(a.get(k)) for k in ("chain_id", "kind")),
            "alerts",
            "each alert needs chain_id and kind",
        )
    return rec


# --- building --------------------------------------------------------------------------------


def empty_file(error: str | None = None, listed: bool | None = None) -> dict:
    """A file entry for a kind the portal produced nothing for."""
    return {
        "listed": listed,
        "downloaded": False,
        "download_seconds": None,
        "download_error": error,
        "file": None,
        "bytes": None,
        "published_at": None,
        "age_hours": None,
        "status": STATUS_NOT_DOWNLOADED,
        "loaded": False,
        "quarantined": False,
        "failed": False,
        "gates": [],
        "reason": None,
        "schema": None,
        "parse_error": None,
        "stores": None,
        "items": None,
        "prices": None,
        "promos": None,
        "load_seconds": None,
    }


def download_error_listed(error: str | None) -> bool | None:
    """Whether the portal listed a file, as far as the download error tells.

    The pinned upstream scraper does not separate "nothing listed" from "listed but not
    downloadable": ``no file downloaded`` covers both, and is recorded as ``False``. A timeout or
    an exception says nothing about the listing and is recorded as ``None`` (unknown)."""
    if error and error.startswith("no file downloaded"):
        return False
    return None


def chain_failure(files: dict[str, dict], portal: dict) -> str | None:
    """Why the chain has no loaded full file today (None when one loaded).

    A portal that did not answer from the runner is named first: that is what a runner IP changes,
    and it is a different finding from a chain whose portal answered but listed nothing."""
    if any(files[k]["loaded"] for k in FULL_KINDS):
        return None
    parts: list[str] = []
    for kind in FULL_KINDS:
        f = files[kind]
        if f["status"] == STATUS_NOT_DOWNLOADED:
            parts.append(f"{kind}: not downloaded ({f['download_error'] or 'no file'})")
        elif f["quarantined"]:
            parts.append(f"{kind}: quarantined ({','.join(f['gates']) or 'no gate recorded'})")
        elif f["failed"]:
            parts.append(f"{kind}: failed ({f['reason'] or 'no reason recorded'})")
        else:
            parts.append(f"{kind}: {f['status']}")
    prefix = ""
    if portal.get("reachable") in ("UNREACHABLE", "BLOCKED?") and not any(
        files[k]["downloaded"] for k in KINDS
    ):
        prefix = (
            f"portal {portal['reachable'].lower()} from the runner (http {portal['http_status']}); "
        )
    return (prefix + "; ".join(parts))[:600]


def finish_chain(
    name: str,
    chain_ids: list[str],
    portal: dict,
    files: dict[str, dict],
    stores: dict[str, int],
    promos_by_reward: dict[str, int],
) -> dict:
    """Assemble a chain entry and derive its counters, ``full_loaded`` and ``failure``."""
    return {
        "name": name,
        "chain_ids": list(chain_ids),
        "portal": portal,
        "files": files,
        "listed": sum(1 for k in KINDS if files[k]["listed"] or files[k]["downloaded"]),
        "downloaded": sum(1 for k in KINDS if files[k]["downloaded"]),
        "loaded": sum(1 for k in KINDS if files[k]["loaded"]),
        "quarantined": sum(1 for k in KINDS if files[k]["quarantined"]),
        "failed": sum(1 for k in KINDS if files[k]["failed"]),
        "full_loaded": any(files[k]["loaded"] for k in FULL_KINDS),
        "failure": chain_failure(files, portal),
        "download_errors": [
            f"{k}: {files[k]['download_error']}" for k in KINDS if files[k]["download_error"]
        ],
        "stores": stores,
        "promos_by_reward": promos_by_reward,
    }


def render_day_summary(rec: dict) -> str:
    """A short Markdown table of one record, for the job summary of the run that wrote it."""
    run = rec["run"]
    lines = [
        f"## Exit window record for {rec['date']} ({LABEL})",
        "",
        f"Runner IP country: **{run['runner_ip_country']}**. Source: {run['source']}, clock: "
        f"{run['clock']}. Started {run['started_at']}, {run['duration_seconds']:.0f} s "
        f"(downloads {run['download_seconds']:.0f} s, loads {run['load_seconds']:.0f} s).",
        "",
        "| Chain | Portal | Stores | PriceFull | PromoFull | Full file loaded |",
        "|---|---|---|---|---|---|",
    ]

    def cell(f: dict) -> str:
        if f["status"] == STATUS_NOT_DOWNLOADED:
            return "no file"
        gates = f" ({', '.join(f['gates'])})" if f["gates"] else ""
        return f"{f['status']}{gates}"

    for c in rec["chains"].values():
        files = c["files"]
        portal = f"{c['portal']['reachable']} ({c['portal']['http_status']})"
        lines.append(
            f"| {c['name']} | {portal} | {cell(files['stores'])} | {cell(files['price_full'])} "
            f"| {cell(files['promo_full'])} | {'yes' if c['full_loaded'] else 'NO'} |"
        )
    ok = sum(1 for c in rec["chains"].values() if c["full_loaded"])
    lines += ["", f"{ok} of {len(rec['chains'])} chains had a loaded full file."]
    return "\n".join(lines) + "\n"
