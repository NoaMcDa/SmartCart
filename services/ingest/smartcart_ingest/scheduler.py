"""Full and delta ingestion jobs (issues #37, #42, #49).

The systemd timers in ``infra/vps`` are the production trigger: the full unit runs
``smartcart-ingest run --mode full`` at 06:00 and 08:30 Israel time, the delta unit runs
``smartcart-ingest run --mode delta`` every hour at :20. This module decides what each tick does.

* ``run_full``: for each chain, list today's Stores, PriceFull and PromoFull files, download and
  process them, then retry the chain's held deltas (their full file may just have loaded).
* ``run_delta``: for each main chain (D13) whose interval is due, retry held deltas, then list
  today's Price and Promo files and process them. A delta whose store has no loaded full file of
  the same kind for that day (Israel time) is ``held``, never applied early.

Every file goes through the same path: download (hash idempotency), hold check, parse, quality
gates, load. Portal calls are retried with exponential backoff and full jitter; after
``PORTAL_MAX_ATTEMPTS`` the chain is skipped for this tick and a ``portal_failure`` alert fires.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dtime
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

import psycopg
import structlog

from smartcart_ingest import loader, quality, tracking
from smartcart_ingest.adapters.base import AdapterError, ChainAdapter, UnknownSchemaError
from smartcart_ingest.alerts import Alerter
from smartcart_ingest.download import Fetcher, PortalError, download, order_for_processing
from smartcart_ingest.models import FileKind, ParsedFile, RawFile
from smartcart_ingest.rawstore import RawStore
from smartcart_ingest.settings import Settings, Thresholds

ISRAEL = ZoneInfo("Asia/Jerusalem")
log = structlog.get_logger("smartcart_ingest.scheduler")
T = TypeVar("T")

FULL_KINDS: tuple[FileKind, ...] = ("stores", "price_full", "promo_full")
DELTA_KINDS: tuple[FileKind, ...] = ("price", "promo")


# --- D13 chain list ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainSchedule:
    chain_id: str
    name: str
    portal: str
    delta_interval_minutes: int | None  # None: daily full sync only

    @property
    def has_deltas(self) -> bool:
        return self.delta_interval_minutes is not None


# Chains 1-6 of D13 are "main" and get hourly deltas; 7-10 get the daily full sync only.
D13_CHAINS: tuple[ChainSchedule, ...] = (
    ChainSchedule("7290027600007", "Shufersal", "shufersal", 60),
    ChainSchedule("7290058140886", "Rami Levy", "cerberus", 60),
    ChainSchedule("7290696200003", "Victory", "laibcatalog", 60),
    ChainSchedule("7290055700007", "Yeinot Bitan and Carrefour", "publishprice", 60),
    ChainSchedule("7290700100008", "Hazi Hinam", "web", 60),
    ChainSchedule("7290873255550", "Tiv Taam", "cerberus", 60),
    ChainSchedule("7290103152017", "Osher Ad", "cerberus", None),
    ChainSchedule("7290803800003", "Yohananof", "cerberus", None),
    ChainSchedule("7290661400001", "Machsanei Hashuk", "laibcatalog", None),
    ChainSchedule("7290058108879", "King Store", "bina", None),
)
MAIN_CHAIN_IDS: tuple[str, ...] = tuple(c.chain_id for c in D13_CHAINS if c.has_deltas)


def chain_schedules(settings: Settings | None = None) -> dict[str, ChainSchedule]:
    """D13 defaults with ``DELTA_INTERVAL_MINUTES`` overrides (0 or less turns deltas off)."""
    out = {c.chain_id: c for c in D13_CHAINS}
    for chain_id, minutes in (settings.delta_interval_minutes if settings else {}).items():
        base = out.get(chain_id, ChainSchedule(chain_id, chain_id, "other", None))
        out[chain_id] = ChainSchedule(
            base.chain_id, base.name, base.portal, minutes if minutes > 0 else None
        )
    return out


def is_delta_due(schedule: ChainSchedule, now: datetime) -> bool:
    """The delta timer ticks hourly. An interval of 60 minutes or less runs on every tick; a
    longer one runs on ticks whose hour count (since the epoch) is a multiple of interval/60."""
    if schedule.delta_interval_minutes is None:
        return False
    if schedule.delta_interval_minutes <= 60:
        return True
    every = max(1, round(schedule.delta_interval_minutes / 60))
    return int(now.timestamp() // 3600) % every == 0


def spread_order(schedules: Sequence[ChainSchedule]) -> list[ChainSchedule]:
    """Interleave chains that share a portal engine (D13: the Cerberus chains share one host)
    so consecutive requests in a tick go to different portals. Runs are sequential, so chains on
    the same engine never hit it at the same time."""
    groups: dict[str, list[ChainSchedule]] = {}
    for s in schedules:
        groups.setdefault(s.portal, []).append(s)
    out: list[ChainSchedule] = []
    queues = sorted(groups.values(), key=len, reverse=True)
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


# --- backoff -----------------------------------------------------------------------------------


class PortalUnavailable(RuntimeError):
    def __init__(self, chain_id: str, attempts: int, last: BaseException) -> None:
        self.chain_id = chain_id
        self.attempts = attempts
        self.last = last
        super().__init__(f"[{chain_id}] portal failed {attempts} times; last error: {last}")


@dataclass
class Backoff:
    """Exponential backoff with full jitter: before retry ``n`` (1-based) wait
    ``uniform(0, min(cap, base * 2**(n-1)))`` seconds. Gives up after ``max_attempts`` calls."""

    max_attempts: int = 5
    base: float = 2.0
    cap: float = 120.0
    sleep: Callable[[float], None] = time.sleep
    rng: Callable[[], float] = random.random
    retry_on: tuple[type[BaseException], ...] = (PortalError, OSError, TimeoutError)

    def delay(self, retry: int) -> float:
        return self.rng() * min(self.cap, self.base * (2 ** (retry - 1)))

    def call(self, chain_id: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        last: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except self.retry_on as exc:
                last = exc
                if attempt == self.max_attempts:
                    break
                wait = self.delay(attempt)
                log.warning(
                    "portal error, backing off",
                    chain_id=chain_id,
                    attempt=attempt,
                    wait_seconds=round(wait, 2),
                    error=str(exc),
                )
                self.sleep(wait)
        assert last is not None
        raise PortalUnavailable(chain_id, self.max_attempts, last)


# --- reports -----------------------------------------------------------------------------------


@dataclass
class ChainReport:
    chain_id: str
    listed: int = 0
    downloaded: int = 0
    skipped: int = 0
    loaded: int = 0
    held: int = 0
    quarantined: int = 0
    failed: int = 0
    unrecognized: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RunReport:
    mode: str
    chains: list[ChainReport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """False when a chain could not run (portal down, no adapter) or a load failed."""
        return all(c.error is None and c.failed == 0 for c in self.chains)


# --- the jobs ----------------------------------------------------------------------------------


def _now_israel() -> datetime:
    return datetime.now(tz=ISRAEL)


class Scheduler:
    def __init__(
        self,
        conn: psycopg.Connection,
        fetcher: Fetcher,
        rawstore: RawStore,
        alerter: Alerter,
        settings: Settings,
        adapter_for: Callable[[str], ChainAdapter] | None = None,
        now: Callable[[], datetime] = _now_israel,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        from smartcart_ingest.adapters.base import get_adapter

        self.conn = conn
        self.fetcher = fetcher
        self.rawstore = rawstore
        self.alert = alerter
        self.settings = settings
        self.adapter_for = adapter_for or get_adapter
        self.now = now
        self.backoff = Backoff(
            max_attempts=settings.portal_max_attempts,
            base=settings.portal_backoff_base_seconds,
            cap=settings.portal_backoff_cap_seconds,
            sleep=sleep,
            rng=rng,
        )
        self.schedules = chain_schedules(settings)

    # -- public jobs --

    def run_full(self, chains: Iterable[str]) -> RunReport:
        report = RunReport("full")
        self.ensure_partitions_ahead()
        for chain_id in self._ordered(chains):
            report.chains.append(self._run_chain(chain_id, FULL_KINDS))
        return report

    def run_delta(self, chains: Iterable[str] | None = None) -> RunReport:
        """Explicit ``chains`` run regardless of interval; by default the due main chains."""
        report = RunReport("delta")
        if chains is None:
            chosen = self.due_delta_chains()
        else:
            chosen = list(chains)
            for chain_id in chosen:
                sched = self.schedules.get(chain_id)
                if sched is None or not sched.has_deltas:
                    log.warning("delta run for a chain without a delta schedule", chain_id=chain_id)
        for chain_id in self._ordered(chosen):
            report.chains.append(self._run_chain(chain_id, DELTA_KINDS))
        return report

    def ensure_partitions_ahead(self) -> None:
        """Keep monthly price partitions two months ahead (supabase/README.md). The loader also
        creates any partition it needs, so this is housekeeping, not a precondition."""
        self.conn.execute(
            "SELECT ensure_price_partitions(%s::date, (%s::date + interval '2 months')::date)",
            (self.now().date(), self.now().date()),
        )

    def due_delta_chains(self) -> list[str]:
        """Chains with a delta schedule whose interval is due at this tick."""
        now = self.now()
        return [s.chain_id for s in self.schedules.values() if is_delta_due(s, now)]

    # -- internals --

    def _ordered(self, chains: Iterable[str]) -> list[str]:
        scheds = [
            self.schedules.get(c, ChainSchedule(c, c, "other", None)) for c in dict.fromkeys(chains)
        ]
        return [s.chain_id for s in spread_order(scheds)]

    def _run_chain(self, chain_id: str, kinds: Sequence[FileKind]) -> ChainReport:
        rep = ChainReport(chain_id)
        try:
            adapter = self.adapter_for(chain_id)
        except KeyError as exc:
            rep.error = f"no adapter: {exc}"
            log.error("no adapter registered", chain_id=chain_id)
            return rep

        recovered = tracking.recover_interrupted(self.conn, chain_id)
        if recovered:
            log.warning("recovered interrupted loads", chain_id=chain_id, files=recovered)
        processed: set[int] = set()

        if kinds == DELTA_KINDS:
            self._process_open(chain_id, adapter, rep, processed)

        now = self.now()
        since = datetime.combine(now.astimezone(ISRAEL).date(), dtime(0), tzinfo=ISRAEL)
        try:
            remote = self.backoff.call(chain_id, self.fetcher.list_files, chain_id, kinds, since)
        except PortalUnavailable as exc:
            self._portal_down(rep, exc)
            return rep
        rep.listed = len(remote)
        if not remote:
            log.warning("portal listed no files", chain_id=chain_id, kinds=list(kinds))

        for rf in order_for_processing(remote, adapter):
            try:
                res = self.backoff.call(
                    chain_id,
                    download,
                    self.conn,
                    self.fetcher,
                    self.rawstore,
                    rf,
                    adapter,
                    self.now(),
                )
            except PortalUnavailable as exc:
                self._portal_down(rep, exc)
                return rep
            except AdapterError as exc:  # detect_kind did not recognise the filename
                rep.unrecognized += 1
                log.warning("unrecognized file", chain_id=chain_id, file=rf.name, error=str(exc))
                continue
            if res.outcome == "skipped":
                rep.skipped += 1
                continue
            if res.outcome == "new":
                rep.downloaded += 1
            processed.add(res.file.id)
            self.process(res.file, adapter, rep, data=res.data)

        # Held deltas whose full file loaded in this run, and anything an earlier run left.
        self._process_open(chain_id, adapter, rep, processed)
        log.info("chain done", **rep.as_dict())
        return rep

    def _process_open(
        self, chain_id: str, adapter: ChainAdapter, rep: ChainReport, processed: set[int]
    ) -> None:
        for f in tracking.open_files(self.conn, chain_id):
            if f.id in processed:
                continue
            processed.add(f.id)
            self.process(f, adapter, rep)

    def _portal_down(self, rep: ChainReport, exc: PortalUnavailable) -> None:
        rep.error = str(exc)
        self.alert(
            rep.chain_id,
            "portal_failure",
            f"portal still failing after {exc.attempts} attempts: {exc.last}",
            attempts=exc.attempts,
        )

    def _fail(
        self,
        f: tracking.TrackedFile,
        rep: ChainReport,
        reason: str,
        kind: str,
        previous: str,
    ) -> str:
        tracking.mark_failed(self.conn, f.id, reason)
        rep.failed += 1
        if reason != previous:
            self.alert(
                f.chain_id,
                kind,  # type: ignore[arg-type]
                f"{f.kind} file {f.path} (store {f.store_code}): {reason}",
                file_id=f.id,
                store_code=f.store_code,
            )
        else:
            log.info("same failure as before, not alerting again", file_id=f.id)
        return "failed"

    def _soft_warnings(self, parsed: ParsedFile, thresholds: Thresholds, file_id: int) -> None:
        """Record and alert the soft quality warnings; they never stop the load."""
        raw = parsed.raw
        found = quality.warnings(self.conn, parsed, thresholds, now=self.now())
        for w in quality.record_warnings(self.conn, raw.chain_id, file_id, found, now=self.now()):
            self.alert(
                raw.chain_id,
                "quality_warning",
                f"{w.warning}: {raw.kind} file {raw.path} (store {raw.store_code}): {w.detail}",
                file_id=file_id,
                store_code=w.store_code,
                warning=w.warning,
            )

    def process(
        self,
        f: tracking.TrackedFile,
        adapter: ChainAdapter,
        rep: ChainReport,
        data: bytes | None = None,
    ) -> str:
        """Hold check, parse, gates and load for one tracked file. Returns the new status."""
        if f.status not in {"downloaded", "held", "failed"}:
            return f.status
        previous_failure = (
            f.reason if f.status == "failed" else tracking.strip_retry(f.reason)
        ) or ""
        raw = f.to_raw()

        if f.is_delta:
            if raw.store_code is None:
                return self._fail(
                    f, rep, "delta file without a store code", "parse_failure", previous_failure
                )
            full_kind = tracking.full_kind_for(raw.kind)
            day = tracking.israel_day(raw.published_at)
            if not tracking.is_full_loaded(self.conn, raw.chain_id, raw.store_code, day, full_kind):
                reason = f"waiting for {full_kind} of store {raw.store_code} for {day.isoformat()}"
                if f.status != "held" or f.reason != reason:
                    tracking.mark_held(self.conn, f.id, reason)
                rep.held += 1
                log.info("delta held", file_id=f.id, chain_id=f.chain_id, reason=reason)
                return "held"

        f = tracking.mark_loading(self.conn, f.id)
        try:
            payload = data if data is not None else self.rawstore.get(raw.path)
            parsed = adapter.parse(raw, payload)
        except UnknownSchemaError as exc:
            return self._fail(f, rep, f"unknown schema: {exc}", "unknown_schema", previous_failure)
        except AdapterError as exc:
            return self._fail(f, rep, f"parse failed: {exc}", "parse_failure", previous_failure)
        except Exception as exc:  # an adapter bug or an unreadable archive is still a failure
            return self._fail(
                f,
                rep,
                f"parse failed: {type(exc).__name__}: {exc}",
                "parse_failure",
                previous_failure,
            )
        parsed = _with_tracked_raw(parsed, raw)

        thresholds = self.settings.thresholds_for(raw.chain_id)
        failures = quality.check(self.conn, parsed, thresholds, now=self.now(), file_id=f.id)
        if failures:
            quality.quarantine(self.conn, f.id, failures, parsed.raw.schema_version)
            rep.quarantined += 1
            self.alert(
                raw.chain_id,
                "quarantine",
                f"{raw.kind} file {raw.path} (store {raw.store_code}) quarantined: "
                + "; ".join(f"{x.gate}: {x.detail}" for x in failures),
                file_id=f.id,
                store_code=raw.store_code,
                gates=[x.gate for x in failures],
            )
            return "quarantined"

        self._soft_warnings(parsed, thresholds, f.id)
        try:
            loader.load(self.conn, parsed, adapter)
        except loader.LoadError as exc:
            rep.failed += 1
            if exc.reason != previous_failure:
                self.alert(
                    raw.chain_id,
                    "load_failure",
                    f"{raw.kind} file {raw.path} (store {raw.store_code}): {exc.reason}",
                    file_id=f.id,
                )
            return "failed"
        rep.loaded += 1
        return "loaded"


def _with_tracked_raw(parsed: ParsedFile, tracked: RawFile) -> ParsedFile:
    """Use the tracked identity (hash, store, time, path) with the schema version the adapter
    detected, whatever RawFile the adapter put on its result."""
    raw = tracked.model_copy(update={"schema_version": parsed.raw.schema_version})
    return parsed.model_copy(update={"raw": raw})
