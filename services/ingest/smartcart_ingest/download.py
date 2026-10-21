"""Idempotent downloads by content hash (issue #37).

A :class:`Fetcher` lists and fetches a chain's transparency files. :func:`download` hashes the
bytes (sha256), archives them to the raw store, and records the file in ``file_tracking`` as
``seen`` then ``downloaded``. A hash already ``loaded`` or ``quarantined`` is skipped and logged,
so re-running a job, an overlapping poll or the 08:30 second pass never loads a file twice.

:class:`ScraperFetcher` wraps the upstream ``il_supermarket_scarper`` package, which is imported
only inside this module (and only when a ScraperFetcher is used). Tests use a fake fetcher.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
import sys
import tempfile
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

import psycopg
import structlog

from smartcart_ingest import tracking
from smartcart_ingest.adapters.base import ChainAdapter
from smartcart_ingest.models import FileKind, RawFile
from smartcart_ingest.rawstore import RawStore, duplicate_key, raw_key

ISRAEL = ZoneInfo("Asia/Jerusalem")
log = structlog.get_logger("smartcart_ingest.download")


@dataclass(frozen=True)
class RemoteFile:
    """One file as a portal lists it. Only ``chain_id`` and ``name`` are required; a fetcher
    that knows the kind, store or publication time fills them in, otherwise they are derived
    from the standard filename (``PriceFull<chain>-<store>-<yyyymmddhhmm>.gz``)."""

    chain_id: str
    name: str
    kind: FileKind | None = None
    store_code: str | None = None
    published_at: datetime | None = None
    url: str | None = None
    size: int | None = None
    local_path: str | None = None  # set by fetchers that download while listing


class Fetcher(Protocol):
    def list_files(
        self,
        chain_id: str,
        kinds: Sequence[FileKind] | None = None,
        since: datetime | None = None,
    ) -> list[RemoteFile]: ...

    def fetch(self, remote: RemoteFile) -> bytes: ...


class PortalError(RuntimeError):
    """The portal could not be listed or a file could not be fetched (retryable)."""

    def __init__(self, chain_id: str, message: str) -> None:
        self.chain_id = chain_id
        super().__init__(f"[{chain_id}] {message}")


class PortalTimeout(PortalError):
    """A portal call did not finish in time (:func:`call_with_timeout`). Unlike other portal
    errors it is not retried within the same tick: a portal that hung once is likely to hang
    again, and the retry would spend the chain's whole time budget on it."""


def call_with_timeout[T](
    fn: Callable[..., T], timeout: float, chain_id: str, what: str, *args: Any, **kwargs: Any
) -> T:
    """Run ``fn`` and return its result, or raise :class:`PortalTimeout` after ``timeout`` seconds.

    The call runs in a daemon thread, because the upstream scraper blocks inside sockets and
    event-loop code that a cooperative cancel cannot reach. A call that outlives its timeout
    cannot be killed: the thread is abandoned (daemon, so it never keeps the process alive) and
    whatever it finishes later is discarded. It touches nothing but the portal and its own
    staging directory, never the database. An exception raised by ``fn`` is re-raised here."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as exc:  # handed to the caller's thread
            box["error"] = exc

    worker = threading.Thread(target=target, name=f"portal-{chain_id}-{what}", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        log.error(
            "portal call timed out, abandoning it", chain_id=chain_id, call=what, seconds=timeout
        )
        raise PortalTimeout(chain_id, f"{what} did not finish within {timeout:g} s")
    if "error" in box:
        raise box["error"]
    return box["value"]


# --- filename conventions -----------------------------------------------------------------------

# ...-<store>-<yyyymmddhhmm>[...]   e.g. PriceFull7290027600007-001-202610060600.gz
_TS12 = re.compile(r"-(?P<ts>\d{12})(?=\D|$)")
# ...-<store>-<yyyymmdd>-<hhmmss>   e.g. Promo7290700100008-000-207-20250224-103225
_TS8_6 = re.compile(r"-(?P<d>\d{8})-(?P<t>\d{6})(?=\D|$)")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_store_code(code: str | None) -> str | None:
    """Store codes appear as ``001`` in filenames and ``1`` in some files: strip leading zeros."""
    if code is None:
        return None
    code = code.strip()
    if not code:
        return None
    stripped = code.lstrip("0")
    return stripped or "0"


def parse_filename(name: str) -> tuple[str | None, datetime | None]:
    """Best-effort ``(store_code, published_at)`` from a standard transparency filename.

    ``published_at`` is Israel local time made timezone-aware. Either value is None when the
    name does not follow the convention.
    """
    stem = Path(name).name
    published: datetime | None = None
    head = stem
    m6 = _TS8_6.search(stem)
    m12 = _TS12.search(stem)
    try:
        if m6:
            published = datetime.strptime(m6["d"] + m6["t"], "%Y%m%d%H%M%S").replace(tzinfo=ISRAEL)
            head = stem[: m6.start()]
        elif m12:
            published = datetime.strptime(m12["ts"], "%Y%m%d%H%M").replace(tzinfo=ISRAEL)
            head = stem[: m12.start()]
    except ValueError:
        published = None
    # The store is the last numeric dash-separated segment before the timestamp, after the
    # leading <Kind><chain id> token.
    parts = head.split("-")
    store: str | None = None
    if len(parts) >= 2 and parts[-1].isdigit():
        store = parts[-1]
    return store, published


# --- download ----------------------------------------------------------------------------------

Outcome = Literal["new", "resumed", "skipped"]


@dataclass(frozen=True)
class DownloadResult:
    file: tracking.TrackedFile
    outcome: Outcome
    data: bytes


def _archive(store: RawStore, key: str, data: bytes, sha: str) -> str:
    """Put ``data`` at ``key`` unless it is already there; on a filename collision with other
    content use the duplicate key. Returns the key the bytes live under."""
    if store.exists(key):
        if sha256_hex(store.get(key)) == sha:
            return key
        key = duplicate_key(key, sha)
        if store.exists(key):
            return key
    store.put(key, data)
    return key


def _filename_info(name: str, adapter: ChainAdapter) -> tuple[str | None, datetime | None]:
    """Store code and publication time from the adapter's own filename parser when it has one
    (``RegulationAdapter.parse_filename``), else from the generic :func:`parse_filename`."""
    hook = getattr(adapter, "parse_filename", None)
    if callable(hook):
        try:
            info = hook(name)
        except Exception:  # fall back to the generic parser for odd names
            info = None
        if info is not None and hasattr(info, "store_code"):
            return info.store_code, getattr(info, "published_at", None)
    return parse_filename(name)


def describe(remote: RemoteFile, adapter: ChainAdapter, sha: str, now: datetime) -> RawFile:
    """Build the RawFile for a fetched file: kind from the adapter, store and time from the
    listing or the filename. The path is the raw store key."""
    kind = remote.kind or adapter.detect_kind(remote.name)
    name_store, name_ts = _filename_info(remote.name, adapter)
    published = remote.published_at or name_ts
    if published is None:
        # No time in the listing or the name: the stale-date gate can only judge the download
        # time, so it cannot fire for this file. Visible in the log, never silent.
        log.warning(
            "no publication time in the listing or the file name, using the download time",
            chain_id=remote.chain_id,
            file=remote.name,
        )
        published = now
    if published.tzinfo is None:
        published = published.replace(tzinfo=ISRAEL)
    store_code = None if kind == "stores" else normalize_store_code(remote.store_code or name_store)
    return RawFile(
        chain_id=remote.chain_id,
        store_code=store_code,
        kind=kind,
        published_at=published,
        sha256=sha,
        path=raw_key(remote.chain_id, published, remote.name),
    )


def download(
    conn: psycopg.Connection,
    fetcher: Fetcher,
    store: RawStore,
    remote: RemoteFile,
    adapter: ChainAdapter,
    now: datetime | None = None,
) -> DownloadResult:
    """Fetch, hash, archive and track one file.

    * new hash: tracked ``seen``, archived, then ``downloaded``  -> outcome ``new``
    * hash already ``loaded`` or ``quarantined``: nothing changes -> outcome ``skipped``
    * hash tracked in any other status (an earlier run stopped, a held delta, a failed load):
      the archive is checked and a failed file goes back to ``downloaded``  -> ``resumed``
    """
    now = now or datetime.now(tz=ISRAEL)
    data = fetcher.fetch(remote)
    sha = sha256_hex(data)

    existing = tracking.get_by_sha(conn, sha)
    if existing is not None and existing.status in tracking.TERMINAL:
        log.info(
            "skipped: hash already processed",
            chain_id=remote.chain_id,
            file=remote.name,
            sha256=sha,
            status=existing.status,
            file_id=existing.id,
        )
        _note_republished(conn, existing, remote, adapter, sha, now, data)
        return DownloadResult(existing, "skipped", data)

    raw = describe(remote, adapter, sha, now)
    row, created = tracking.register(conn, raw)
    key = _archive(store, row.path or raw.path, data, sha)

    if row.status == "seen":
        row = tracking.mark_downloaded(conn, row.id, key)
    elif row.status == "failed":
        # Keep the earlier failure so a repeat of the same failure does not alert again.
        row = tracking.mark_downloaded(
            conn, row.id, key, f"{tracking.RETRY_PREFIX}{tracking.strip_retry(row.reason)}"
        )
    outcome: Outcome = "new" if created else "resumed"
    log.info(
        "downloaded",
        chain_id=raw.chain_id,
        file=remote.name,
        kind=raw.kind,
        store_code=raw.store_code,
        sha256=sha,
        file_id=row.id,
        outcome=outcome,
        status=row.status,
    )
    return DownloadResult(row, outcome, data)


def _note_republished(
    conn: psycopg.Connection,
    existing: tracking.TrackedFile,
    remote: RemoteFile,
    adapter: ChainAdapter,
    sha: str,
    now: datetime,
    data: bytes | None = None,
) -> None:
    """A loaded full file seen again on a later Israel day, byte for byte: record it, so the
    deltas of that day are not held for a "full file of the day" that was rightly skipped."""
    if existing.status != "loaded" or existing.kind not in tracking.FULL_KINDS:
        return
    if existing.published_at is None:
        return
    try:
        raw = describe(remote, adapter, sha, now)
    except Exception:  # an unrecognised name is reported by the caller's normal path
        return
    if (
        raw.kind == existing.kind
        and raw.store_code == existing.store_code
        and tracking.israel_day(raw.published_at) > tracking.israel_day(existing.published_at)
        and tracking.record_republished(conn, existing, raw)
    ):
        log.info(
            "identical full file republished on a later day, recorded as loaded",
            chain_id=raw.chain_id,
            file=remote.name,
            source_file_id=existing.id,
        )
        if raw.kind == "promo_full" and data is not None:
            _end_promos_the_republished_full_lacks(conn, adapter, raw, data)


def _end_promos_the_republished_full_lacks(
    conn: psycopg.Connection, adapter: ChainAdapter, raw: RawFile, data: bytes
) -> None:
    """The same bytes are the store's list for the new day too, so a promotion a Promo delta added
    since is withdrawn, as it would be by a PromoFull that loaded. A parse error is the normal
    path's business (the file was loaded once already), never this one's."""
    from smartcart_ingest.loader import end_withdrawn_promos

    try:
        end_withdrawn_promos(conn, adapter.parse(raw, data))
    except Exception as exc:
        log.warning("could not end promotions for a republished PromoFull", error=str(exc))


# --- upstream scraper ---------------------------------------------------------------------------

# Loggers that il_supermarket_scarper ("Logger") and il_supermarket_parsers ("mylogger") build at
# import time. Without a handler they also open FileHandler("logging.log") in the working
# directory, which is read-only on the VPS (ProtectSystem=strict, WorkingDirectory=/opt/smartcart)
# and would make the import fail there.
UPSTREAM_LOGGERS = ("Logger", "mylogger")


class _StderrHandler(logging.StreamHandler):
    """Writes to whatever ``sys.stderr`` is at emit time (systemd appends it to the log file)."""

    def __init__(self) -> None:
        super().__init__()

    @property  # type: ignore[override]
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value) -> None:
        pass


def quiet_upstream_loggers(level: int = logging.INFO) -> None:
    """Give the upstream loggers a stderr handler before they are imported, so they do not
    create ``logging.log`` in the working directory. Idempotent."""
    for name in UPSTREAM_LOGGERS:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = _StderrHandler()
            handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(level)
            logger.propagate = False


def load_upstream() -> tuple[Any, Any]:
    """``(ScraperFactory, DiskFileOutput)`` from il_supermarket_scarper, imported safely."""
    quiet_upstream_loggers()
    from smartcart_ingest.adapters._scraper import scraper_api

    return scraper_api()


# D13 chain id -> ScraperFactory member name in il_supermarket_scarper 1.0.15.
UPSTREAM_SCRAPERS: dict[str, str] = {
    "7290027600007": "SHUFERSAL",
    "7290058140886": "RAMI_LEVY",
    "7290696200003": "VICTORY_NEW_SOURCE",
    "7290055700007": "YAYNO_BITAN_AND_CARREFOUR",
    "7290700100008": "HAZI_HINAM",
    "7290873255550": "TIV_TAAM",
    "7290103152017": "OSHER_AD",
    "7290803800003": "YOHANANOF",
    "7290661400001": "MAHSANI_ASHUK_NEW_SOURCE",
    "7290058108879": "KING_STORE",
}

_UPSTREAM_TYPES: dict[str, str] = {
    "stores": "STORE_FILE",
    "price_full": "PRICE_FULL_FILE",
    "price": "PRICE_FILE",
    "promo_full": "PROMO_FULL_FILE",
    "promo": "PROMO_FILE",
}


class ScraperFetcher:
    """Lists and fetches files through ``il_supermarket_scarper`` (via ``adapters._scraper``).

    Upstream couples listing and downloading (its ``scrape()`` downloads every listed file), so
    ``list_files`` runs a scrape into a fresh staging directory with gzip extraction off and
    returns one RemoteFile per saved file; ``fetch`` reads and removes the staged file. Hash
    idempotency is applied afterwards by :func:`download`. A fresh directory per call keeps
    upstream's own "already downloaded" bookkeeping from hiding files we have not tracked.

    Upstream swallows listing exceptions and logs them; a scrape that produced no file but
    reported download errors is raised as PortalError so the scheduler can back off.
    """

    def __init__(
        self,
        staging_root: str | Path | None = None,
        scrapers: dict[str, str] | None = None,
    ) -> None:
        self.staging_root = Path(staging_root) if staging_root else None
        self.scrapers = scrapers or UPSTREAM_SCRAPERS
        self._staging: list[Path] = []

    def _scraper_name(self, chain_id: str) -> str:
        """The adapter's ``upstream_scraper`` when it declares one, else the D13 table."""
        from smartcart_ingest.adapters.base import REGISTRY

        declared = getattr(REGISTRY.get(chain_id), "upstream_scraper", None)
        if isinstance(declared, str) and declared:
            return declared
        try:
            return self.scrapers[chain_id]
        except KeyError as exc:
            raise PortalError(chain_id, "no upstream scraper mapped for this chain") from exc

    def list_files(
        self,
        chain_id: str,
        kinds: Sequence[FileKind] | None = None,
        since: datetime | None = None,
    ) -> list[RemoteFile]:
        ScraperFactory, DiskFileOutput = load_upstream()  # noqa: N806

        name = self._scraper_name(chain_id)
        scraper_cls = ScraperFactory.get(name)
        if scraper_cls is None:
            raise PortalError(chain_id, f"upstream scraper {name} is disabled")
        if self.staging_root:
            self.staging_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f"stage-{chain_id}-", dir=self.staging_root))
        self._staging.append(staging)
        files_dir = staging / "files"
        output = DiskFileOutput(str(files_dir), extract_gz=False)
        scraper = scraper_cls(file_output=output)
        types = [_UPSTREAM_TYPES[k] for k in kinds] if kinds else None
        when = since.astimezone(ISRAEL).replace(tzinfo=None) if since else None

        async def collect() -> tuple[list, list[str]]:
            ok, errors = [], []
            async for result in scraper.scrape(files_types=types, when_date=when):
                if result.extract_succefully:
                    ok.append(result)
                elif result.error:
                    errors.append(f"{result.file_name}: {result.error}")
            return ok, errors

        try:
            results, errors = asyncio.run(collect())
        except Exception as exc:
            raise PortalError(chain_id, f"listing failed: {exc}") from exc
        if not results and errors:
            raise PortalError(chain_id, f"{len(errors)} download errors, e.g. {errors[0]}")
        out: list[RemoteFile] = []
        for result in results:
            entry = result.file_entry
            published = None
            if getattr(entry, "published_at", None):
                try:
                    published = datetime.fromisoformat(entry.published_at)
                except ValueError:
                    published = None
            if published is not None and published.tzinfo is None:
                published = published.replace(tzinfo=ISRAEL)
            out.append(
                RemoteFile(
                    chain_id=chain_id,
                    name=Path(entry.name).name,
                    published_at=published,
                    url=entry.url,
                    size=entry.size,
                    local_path=str(files_dir / result.file_name),
                )
            )
        return out

    def fetch(self, remote: RemoteFile) -> bytes:
        if not remote.local_path:
            raise PortalError(remote.chain_id, f"{remote.name} was not staged by list_files")
        path = Path(remote.local_path)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise PortalError(remote.chain_id, f"staged file unreadable: {exc}") from exc
        path.unlink(missing_ok=True)
        return data

    def close(self) -> None:
        for d in self._staging:
            shutil.rmtree(d, ignore_errors=True)
        self._staging.clear()


def order_for_processing(files: Iterable[RemoteFile], adapter: ChainAdapter) -> list[RemoteFile]:
    """Stores first, then full files, then deltas; each group by publication time. Listing
    order from a portal is arbitrary, so a delta listed before its full file still goes after."""
    rank = {"stores": 0, "price_full": 1, "promo_full": 2, "price": 3, "promo": 4}

    def key(f: RemoteFile) -> tuple:
        try:
            kind = f.kind or adapter.detect_kind(f.name)
        except Exception:
            kind = "zzz"
        _, ts = parse_filename(f.name)
        when = f.published_at or ts
        return (rank.get(kind, 9), when.timestamp() if when else 0.0, f.name)

    return sorted(files, key=key)
