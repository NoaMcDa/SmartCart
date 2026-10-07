"""Test doubles for the download, loader, quality and scheduler tests.

* ``FakeAdapter`` is registered under chain id ``fake``. Its "files" are JSON documents with the
  records a real adapter would produce, so their bytes (and hashes) change when the content does.
  ``b"!parse-error"`` raises AdapterError and ``b"!unknown-schema"`` raises UnknownSchemaError.
* ``FakeFetcher`` serves files from memory and can fail a set number of times per chain.
* ``encode`` builds a fake file from records; ``store``/``item``/``price``/``promo`` build records.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

from smartcart_ingest.adapters.base import (
    REGISTRY,
    AdapterError,
    ChainAdapter,
    UnknownSchemaError,
    register,
)
from smartcart_ingest.alerts import Alert, Alerter
from smartcart_ingest.download import PortalError, RemoteFile
from smartcart_ingest.models import (
    FileKind,
    ItemRecord,
    ParsedFile,
    PriceRecord,
    PromoRecord,
    RawFile,
    SchemaVersion,
    StoreRecord,
)
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import Scheduler
from smartcart_ingest.settings import Settings

CHAIN = "fake"
ISRAEL = ZoneInfo("Asia/Jerusalem")
# A fixed "now" for the tests: Tuesday 2026-10-06 10:00 Israel time.
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=ISRAEL)

_PREFIXES: tuple[tuple[str, FileKind], ...] = (
    ("pricefull", "price_full"),
    ("promofull", "promo_full"),
    ("stores", "stores"),
    ("price", "price"),
    ("promo", "promo"),
)


def kind_of(filename: str) -> FileKind | None:
    lower = filename.lower()
    for prefix, kind in _PREFIXES:
        if lower.startswith(prefix):
            return kind
    return None


class FakeAdapter(ChainAdapter):
    chain_id = CHAIN
    display_name = "Fake Chain"
    portal = "other"

    def detect_kind(self, filename: str) -> FileKind:
        kind = kind_of(filename)
        if kind is None:
            raise AdapterError(self.chain_id, f"unrecognized filename {filename!r}")
        return kind

    def detect_schema(self, xml_root: Any) -> SchemaVersion:
        return xml_root.get("schema_version", "v1") if isinstance(xml_root, dict) else "unknown"

    def parse(self, raw: RawFile, data: bytes) -> ParsedFile:
        if data.startswith(b"!unknown-schema"):
            raise UnknownSchemaError(self.chain_id, "neither v1 nor v2")
        if data.startswith(b"!parse-error"):
            raise AdapterError(self.chain_id, "broken XML")
        doc = json.loads(data)
        schema = self.detect_schema(doc)
        if schema == "unknown":
            raise UnknownSchemaError(self.chain_id, "neither v1 nor v2")
        return ParsedFile(
            raw=raw.model_copy(update={"schema_version": schema}),
            stores=[StoreRecord(**s) for s in doc.get("stores", [])],
            items=[ItemRecord(**i) for i in doc.get("items", [])],
            prices=[PriceRecord(**p) for p in doc.get("prices", [])],
            promos=[PromoRecord(**p) for p in doc.get("promos", [])],
        )

    def online_store_rule(self, store: StoreRecord) -> bool:
        return "online" in store.name.lower()


if CHAIN not in REGISTRY:
    register(FakeAdapter)


# --- records -----------------------------------------------------------------------------------


def store(code: str, name: str | None = None, **kw: Any) -> StoreRecord:
    return StoreRecord(chain_id=CHAIN, store_code=code, name=name or f"Store {code}", **kw)


def item(code: str, name: str | None = None, **kw: Any) -> ItemRecord:
    return ItemRecord(chain_id=CHAIN, item_code=code, raw_name=name or f"Item {code}", **kw)


def price(
    code: str,
    store_code: str,
    amount: str | Decimal,
    at: datetime = NOW - timedelta(hours=4),
    **kw: Any,
) -> PriceRecord:
    return PriceRecord(
        chain_id=CHAIN,
        store_code=store_code,
        item_code=code,
        price=Decimal(str(amount)),
        observed_at=at,
        **kw,
    )


def promo(promo_id: str, store_code: str, item_codes: Sequence[str], **kw: Any) -> PromoRecord:
    kw.setdefault("description", f"Promo {promo_id}")
    return PromoRecord(
        chain_id=CHAIN, store_code=store_code, promo_id=promo_id, item_codes=list(item_codes), **kw
    )


def encode(
    stores: Sequence[StoreRecord] = (),
    items: Sequence[ItemRecord] = (),
    prices: Sequence[PriceRecord] = (),
    promos: Sequence[PromoRecord] = (),
    schema_version: str = "v1",
    salt: str = "",
) -> bytes:
    """A fake transparency file. ``salt`` changes the bytes without changing the records (a
    republished file with identical content but a different hash)."""
    doc = {
        "schema_version": schema_version,
        "stores": [s.model_dump(mode="json") for s in stores],
        "items": [i.model_dump(mode="json") for i in items],
        "prices": [p.model_dump(mode="json") for p in prices],
        "promos": [p.model_dump(mode="json") for p in promos],
        "salt": salt,
    }
    return json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")


def filename(kind: FileKind, store_code: str | None, at: datetime) -> str:
    prefix = {
        "stores": "Stores",
        "price_full": "PriceFull",
        "promo_full": "PromoFull",
        "price": "Price",
        "promo": "Promo",
    }[kind]
    local = at.astimezone(ISRAEL)
    return f"{prefix}{CHAIN}-{store_code or '000'}-{local:%Y%m%d%H%M}.gz"


def parsed_file(
    kind: FileKind,
    data: bytes,
    store_code: str | None = "1",
    at: datetime = NOW - timedelta(hours=4),
    path: str = "raw/fake/test",
) -> ParsedFile:
    """Parse ``data`` with the FakeAdapter into a ParsedFile with a RawFile for it."""
    from smartcart_ingest.download import sha256_hex

    raw = RawFile(
        chain_id=CHAIN,
        store_code=None if kind == "stores" else store_code,
        kind=kind,
        published_at=at,
        sha256=sha256_hex(data),
        path=path,
    )
    return FakeAdapter().parse(raw, data)


# --- fetcher -----------------------------------------------------------------------------------


@dataclass
class FakeFetcher:
    files: dict[str, list[tuple[RemoteFile, bytes]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    list_failures: dict[str, int] = field(default_factory=dict)
    fetch_failures: dict[str, int] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def add(
        self,
        kind: FileKind,
        data: bytes,
        store_code: str | None = "1",
        at: datetime = NOW - timedelta(hours=4),
        chain_id: str = CHAIN,
        name: str | None = None,
    ) -> RemoteFile:
        remote = RemoteFile(chain_id=chain_id, name=name or filename(kind, store_code, at))
        self.files[chain_id].append((remote, data))
        return remote

    def clear(self, chain_id: str = CHAIN) -> None:
        self.files[chain_id] = []

    def list_files(
        self,
        chain_id: str,
        kinds: Sequence[FileKind] | None = None,
        since: datetime | None = None,
    ) -> list[RemoteFile]:
        self.calls.append(("list", chain_id))
        if self.list_failures.get(chain_id, 0) > 0:
            self.list_failures[chain_id] -= 1
            raise PortalError(chain_id, "connection reset by portal")
        out = []
        for remote, _ in self.files.get(chain_id, []):
            if kinds and kind_of(remote.name) not in kinds:
                continue
            out.append(remote)
        return out

    def fetch(self, remote: RemoteFile) -> bytes:
        self.calls.append(("fetch", remote.name))
        if self.fetch_failures.get(remote.chain_id, 0) > 0:
            self.fetch_failures[remote.chain_id] -= 1
            raise PortalError(remote.chain_id, "timeout")
        for r, data in self.files.get(remote.chain_id, []):
            if r.name == remote.name:
                return data
        raise PortalError(remote.chain_id, f"404 {remote.name}")


class RecordingSink:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self.alerts.append(alert)


@dataclass
class Harness:
    conn: psycopg.Connection
    fetcher: FakeFetcher
    store: LocalRawStore
    sink: RecordingSink
    settings: Settings
    clock: list[datetime]
    sleeps: list[float]

    def scheduler(self) -> Scheduler:
        return Scheduler(
            self.conn,
            self.fetcher,
            self.store,
            Alerter([self.sink]),
            self.settings,
            adapter_for=lambda chain_id: FakeAdapter() if chain_id == CHAIN else _no(chain_id),
            now=lambda: self.clock[0],
            sleep=self.sleeps.append,
            rng=lambda: 1.0,
        )

    def set_now(self, when: datetime) -> None:
        self.clock[0] = when

    def kinds_of_alerts(self) -> list[str]:
        return [a.kind for a in self.sink.alerts]


def _no(chain_id: str) -> ChainAdapter:
    raise KeyError(f"no adapter registered for chain {chain_id!r}")


def make_harness(conn: psycopg.Connection, root: Any, **settings: Any) -> Harness:
    settings.setdefault("portal_backoff_base_seconds", 1.0)
    settings.setdefault("portal_max_attempts", 3)
    return Harness(
        conn=conn,
        fetcher=FakeFetcher(),
        store=LocalRawStore(root),
        sink=RecordingSink(),
        settings=Settings(**settings),
        clock=[NOW],
        sleeps=[],
    )


TABLES = ("chains", "stores", "items", "prices", "promos", "promo_items")


def counts(conn: psycopg.Connection, chain_id: str = CHAIN) -> dict[str, int]:
    """Row counts of the data tables for one chain."""
    q = {
        "chains": "SELECT count(*) FROM chains WHERE id = %s",
        "stores": "SELECT count(*) FROM stores WHERE chain_id = %s",
        "items": "SELECT count(*) FROM items WHERE chain_id = %s",
        "prices": "SELECT count(*) FROM prices p JOIN items i ON i.id = p.item_id"
        " WHERE i.chain_id = %s",
        "promos": "SELECT count(*) FROM promos WHERE chain_id = %s",
        "promo_items": "SELECT count(*) FROM promo_items pi JOIN promos p ON p.id = pi.promo_id"
        " WHERE p.chain_id = %s",
    }
    return {t: conn.execute(q[t], (chain_id,)).fetchone()[0] for t in TABLES}


def statuses(conn: psycopg.Connection, chain_id: str = CHAIN) -> dict[str, str]:
    """filename (last path segment) -> status for one chain."""
    rows = conn.execute(
        "SELECT path, status FROM file_tracking WHERE chain_id = %s ORDER BY id", (chain_id,)
    ).fetchall()
    return {r[0].rsplit("/", 1)[-1]: r[1] for r in rows}


@contextmanager
def no_commit(conn: psycopg.Connection) -> Iterator[psycopg.Connection]:
    """Yield the test connection as if it were a fresh one (its outer transaction is kept)."""
    yield conn
