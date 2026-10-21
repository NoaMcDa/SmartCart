"""``smartcart-ingest`` command line (entry point declared in pyproject.toml).

Commands match the systemd units in ``infra/vps``:

* ``smartcart-ingest migrate``                          apply pending SQL migrations
* ``smartcart-ingest run --mode full [--chain ID ...]``  daily full sync (06:00 and 08:30)
* ``smartcart-ingest run --mode late [--chain ID ...]``  late full files (11:30 and 15:30), only
                                                        the chains still missing some today
* ``smartcart-ingest run --mode delta [--chain ID ...]`` hourly deltas for the main chains
* ``smartcart-ingest status``                           file_tracking counts by chain and status

``run`` exits 1 when a chain could not run (portal down after backoff, no adapter) or a file
failed to parse or load; quarantines are not errors. It exits 75 without doing anything when
another run holds the database lock. Alerts carry the details either way.
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from typing import Annotated

import psycopg
import structlog
import typer

from smartcart_ingest import db as dbmod
from smartcart_ingest import tracking
from smartcart_ingest.alerts import build_alerter
from smartcart_ingest.download import Fetcher, ScraperFetcher, quiet_upstream_loggers
from smartcart_ingest.rawstore import RawStore, rawstore_from_settings
from smartcart_ingest.scheduler import D13_CHAINS, RunLocked, RunReport, Scheduler
from smartcart_ingest.settings import Settings, load_settings

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SmartCart ingestion worker.")
log = structlog.get_logger("smartcart_ingest.cli")


EXIT_LOCKED = 75


class Mode(StrEnum):
    full = "full"
    late = "late"
    delta = "delta"


# --- seams the tests replace -------------------------------------------------------------------


@contextmanager
def open_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    """Autocommit, so each tracking update is durable on its own and every load is exactly one
    transaction (``conn.transaction()``)."""
    with dbmod.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        yield conn


def build_fetcher(settings: Settings) -> Fetcher:
    return ScraperFetcher()


def build_rawstore(settings: Settings) -> RawStore:
    return rawstore_from_settings(settings)


def register_adapters() -> list[str]:
    """Import every module under ``smartcart_ingest.adapters`` so the chains register."""
    import smartcart_ingest.adapters as pkg

    names = []
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name != "base":
            importlib.import_module(f"{pkg.__name__}.{mod.name}")
            names.append(mod.name)
    return names


# --- commands ----------------------------------------------------------------------------------


def _stderr_logger(*args: object) -> structlog.PrintLogger:
    # Looked up on every call, so a redirected sys.stderr (tests, CliRunner) is honoured.
    return structlog.PrintLogger(file=sys.stderr)


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    quiet_upstream_loggers(level)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.KeyValueRenderer(key_order=["timestamp", "level", "event"]),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=_stderr_logger,
        cache_logger_on_first_use=False,
    )


@app.command()
def migrate() -> None:
    """Apply pending migrations from supabase/migrations."""
    settings = load_settings()
    with dbmod.connect(settings.database_url, autocommit=True) as conn:
        applied = dbmod.migrate(conn)
    if applied:
        for name in applied:
            typer.echo(f"applied {name}")
    else:
        typer.echo("no pending migrations")


def _print_report(report: RunReport) -> None:
    for c in report.chains:
        typer.echo(json.dumps({"mode": report.mode, **c.as_dict()}, ensure_ascii=False))


def _mark_late_loads(settings: Settings, report: RunReport) -> None:
    """Leave a marker file when a late pass loaded a PriceFull or PromoFull: the late precompute
    unit (infra/vps/smartcart-precompute-late.service) runs only while it exists, so a day on
    which nothing arrived late does not pay for a second precompute. The unit removes it after a
    successful precompute. A marker that cannot be written is logged, never fatal: the
    next 09:30 precompute still prices whatever is loaded."""
    marker = settings.late_load_marker
    loaded = sum(c.loaded_full for c in report.chains)
    if marker is None or not loaded:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{loaded} full files loaded late\n", encoding="utf-8")
    except OSError as exc:
        log.error("could not write the late-load marker", path=str(marker), error=str(exc))


@app.command()
def run(
    mode: Annotated[
        Mode,
        typer.Option(
            "--mode",
            help="full: Stores, PriceFull, PromoFull. late: PriceFull and PromoFull of the chains"
            " that have not loaded all of today's. delta: Price, Promo.",
        ),
    ],
    chain: Annotated[
        list[str] | None,
        typer.Option(
            "--chain",
            help="Chain id, repeatable. Default: the D13 chains (full), those still missing"
            " full files today (late) or the due main chains (delta).",
        ),
    ] = None,
) -> None:
    """Download, gate and load transparency files."""
    settings = load_settings()
    register_adapters()
    from smartcart_ingest.adapters.base import REGISTRY

    fetcher = build_fetcher(settings)
    rawstore = build_rawstore(settings)
    alerter = build_alerter(settings.alert_webhook_url)
    chains = list(chain) if chain else None
    try:
        with open_connection(settings) as conn:
            sched = Scheduler(conn, fetcher, rawstore, alerter, settings)
            if chains is None:
                wanted = (
                    sched.due_delta_chains()
                    if mode is Mode.delta
                    else [c.chain_id for c in D13_CHAINS]
                )
                chains = [c for c in wanted if c in REGISTRY]
                missing = [c for c in wanted if c not in REGISTRY]
                if missing:
                    log.warning("no adapter registered yet, skipping", chains=missing)
                if mode is Mode.late:
                    chains = sched.pending_full_chains(chains)
                    log.info("late pass", chains=chains)
            if mode is Mode.full:
                report = sched.run_full(chains)
            elif mode is Mode.late:
                report = sched.run_late(chains)
            else:
                report = sched.run_delta(chains)
    except RunLocked as exc:
        # Not an error of this run, but not a success either: nothing was ingested. 75 is
        # EX_TEMPFAIL ("try again"), so a timer shows the skipped tick as failed.
        typer.echo(f"skipped: {exc}", err=True)
        raise typer.Exit(code=EXIT_LOCKED) from exc
    finally:
        close = getattr(fetcher, "close", None)
        if callable(close):
            close()
    _print_report(report)
    if mode is Mode.late:
        _mark_late_loads(settings, report)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Print file_tracking counts by chain and status, and quarantined files per chain."""
    settings = load_settings()
    with open_connection(settings) as conn:
        counts = tracking.status_counts(conn)
        quarantined = tracking.quarantine_counts(conn)
    if not counts:
        typer.echo("no files tracked")
        return
    typer.echo(f"{'chain':<16} {'status':<12} {'files':>7}")
    for chain_id, st, n in counts:
        typer.echo(f"{chain_id:<16} {st:<12} {n:>7}")
    if quarantined:
        typer.echo("")
        typer.echo(f"{'chain':<16} {'quarantined':>11} {'last 24h':>9}")
        for chain_id, total, recent in quarantined:
            typer.echo(f"{chain_id:<16} {total:>11} {recent:>9}")


@app.command("clubs-report")
def clubs_report(
    only_unmapped: Annotated[
        bool, typer.Option("--unmapped", help="Only texts with a name the club table lacks.")
    ] = False,
) -> None:
    """List the ClubID texts of the loaded club promotions, the rule each resolves to and the club
    names the table (adapters/chain_clubs.json) does not know: those match nobody yet."""
    from smartcart_ingest.clubs_report import club_texts

    settings = load_settings()
    with open_connection(settings) as conn:
        rows = club_texts(conn)
    if only_unmapped:
        rows = [r for r in rows if r.unmapped]
    if not rows:
        typer.echo("no club promotions" if not only_unmapped else "every club text is mapped")
        return
    for r in rows:
        typer.echo(f"{r.chain_id}\t{r.promos}\t{r.text[:200]}")
        typer.echo(f"\t-> {r.rule}")
        if r.unmapped:
            typer.echo(f"\tunmapped: {' | '.join(r.unmapped)[:200]}")


if __name__ == "__main__":  # pragma: no cover
    app()
