"""Fixture-driven regression tests for every registered chain adapter.

Each chain folder under tests/fixtures holds transparency files named exactly as the portal
names them plus an ``expected.json`` with literal counts and field values. The tests below
enumerate REGISTRY against those folders, so adding a chain needs only a new adapter module and
a fixture folder; no test or loader code changes.

All fixtures are SYNTHETIC until the Israeli VPS can fetch real files (see
smartcart_ingest/adapters/fetch_fixtures.py and docs/adapters.md).
"""

from __future__ import annotations

import gzip
import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest

from smartcart_ingest.adapters import REGISTRY, get_adapter, register
from smartcart_ingest.adapters._common import (
    PROVISIONAL_V2_MARKER,
    RegulationAdapter,
    parse_filename,
)
from smartcart_ingest.adapters.base import AdapterError, UnknownSchemaError
from smartcart_ingest.models import ParsedFile

FIXTURES = Path(__file__).parent / "fixtures"
NON_CHAIN_DIRS = {"xmlutil", "real"}
ERRORS = {"AdapterError": AdapterError, "UnknownSchemaError": UnknownSchemaError}
REQUIRED_KINDS = {"stores", "price_full", "promo_full"}


def chain_adapters() -> dict[str, type[RegulationAdapter]]:
    return {
        cls.slug: cls
        for cls in REGISTRY.values()
        if isinstance(cls, type) and issubclass(cls, RegulationAdapter)
    }


def chain_dirs(root: Path = FIXTURES) -> list[Path]:
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and p.name not in NON_CHAIN_DIRS and not p.name.startswith(("_", "."))
    )


def resolve(parsed: ParsedFile, path: str) -> Any:
    """``"prices[0].price"`` -> parsed.prices[0].price"""
    value: Any = parsed
    for name, index in re.findall(r"(\w+)(?:\[(\d+)\])?", path):
        value = getattr(value, name)
        if index:
            value = value[int(index)]
    return value


def parse_fixture(adapter: RegulationAdapter, file: Path) -> ParsedFile:
    data = file.read_bytes()
    raw = adapter.raw_file_for(file.name, data, path=f"fixtures/{file.parent.name}/{file.name}")
    return adapter.parse(raw, data)


def check_folder(adapter: RegulationAdapter, folder: Path) -> list[str]:
    """Run every fixture in ``folder`` against ``expected.json``; return the kinds covered."""
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    assert expected["chain_id"] == adapter.chain_id
    # Files only: a chain's real/ subdirectory holds real portal files (tests below).
    on_disk = {p.name for p in folder.iterdir() if p.is_file() and p.name != "expected.json"}
    assert on_disk == set(expected["files"]), "every fixture file needs an expected.json entry"
    covered: list[str] = []
    for name, exp in expected["files"].items():
        file = folder / name
        assert adapter.detect_kind(name) == exp["kind"], name
        if "error" in exp:
            with pytest.raises(ERRORS[exp["error"]]) as info:
                parse_fixture(adapter, file)
            assert info.value.chain_id == adapter.chain_id
            assert adapter.chain_id in str(info.value), "alerts must name the chain"
            if exp["error"] == "AdapterError":
                assert not isinstance(info.value, UnknownSchemaError), name
            continue
        parsed = parse_fixture(adapter, file)
        assert parsed.raw.schema_version == exp["schema"], name
        for field in ("stores", "items", "prices", "promos"):
            assert len(getattr(parsed, field)) == exp["counts"].get(field, 0), f"{name}: {field}"
        for path, want in exp["checks"].items():
            assert str(resolve(parsed, path)) == want, f"{name}: {path}"
        if exp["kind"] == "stores":
            online = sorted(s.store_code for s in parsed.stores if s.channel == "online")
            assert online == sorted(exp["online"]), f"{name}: online stores"
            assert all(s.channel in ("physical", "online") for s in parsed.stores)
        if exp["schema"] == "v1":
            covered.append(exp["kind"])
    return covered


# --------------------------------------------------------------------------- registry


def test_registry_matches_fixture_folders() -> None:
    adapters = chain_adapters()
    folders = {p.name for p in chain_dirs()}
    assert set(adapters) == folders, "each registered chain needs a fixture folder and vice versa"
    assert len(adapters) >= 8


def test_phase0_chains_registered() -> None:
    expected = {
        "shufersal": "7290027600007",
        "ramilevy": "7290058140886",
        "osherad": "7290103152017",
        "yohananof": "7290803800003",
        "victory": "7290696200003",
        "hazihinam": "7290700100008",
        "tivtaam": "7290873255550",
        "mega": "7290055700007",
        "machsanei_hashuk": "7290661400001",
        "king_store": "7290058108879",
    }
    adapters = chain_adapters()
    assert {slug: cls.chain_id for slug, cls in adapters.items()} == expected
    for chain_id in expected.values():
        assert isinstance(get_adapter(chain_id), RegulationAdapter)


@pytest.mark.parametrize("slug", sorted(chain_adapters()))
def test_chain_fixtures(slug: str) -> None:
    adapter = chain_adapters()[slug]()
    covered = check_folder(adapter, FIXTURES / slug)
    missing = REQUIRED_KINDS - set(covered)
    assert not missing, f"{slug} lacks v1 fixtures for {sorted(missing)}"


@pytest.mark.parametrize("slug", sorted(chain_adapters()))
def test_adapter_metadata(slug: str) -> None:
    cls = chain_adapters()[slug]
    assert cls.portal in ("cerberus", "shufersal", "matrix", "bina", "web", "other")
    assert cls.display_name
    assert cls.has_online_record in (True, False)


def test_adding_a_chain_needs_only_a_module_and_a_fixture(tmp_path: Path) -> None:
    """Write a brand-new adapter module and fixture folder, then run the generic harness."""
    module_src = textwrap.dedent(
        """
        from smartcart_ingest.adapters._common import RegulationAdapter
        from smartcart_ingest.adapters.base import register

        @register
        class NewChainAdapter(RegulationAdapter):
            chain_id = "7290000000001"
            display_name = "רשת חדשה"
            slug = "newchain"
            portal = "other"
            has_online_record = False
        """
    )
    namespace: dict[str, Any] = {}
    try:
        exec(compile(module_src, "newchain.py", "exec"), namespace)  # noqa: S102
        folder = tmp_path / "newchain"
        folder.mkdir()
        doc = (
            '<?xml version="1.0" encoding="utf-8"?><Root><ChainId>7290000000001</ChainId>'
            "<StoreId>001</StoreId><Items><Item><ItemCode>7290000000123</ItemCode>"
            '<ItemName>אורז פרסי 1 ק"ג</ItemName><ItemPrice>9.90</ItemPrice></Item></Items></Root>'
        )
        (folder / "PriceFull7290000000001-001-202610060300.gz").write_bytes(
            gzip.compress(doc.encode("utf-8"), mtime=0)
        )
        expected = {
            "chain_id": "7290000000001",
            "files": {
                "PriceFull7290000000001-001-202610060300.gz": {
                    "kind": "price_full",
                    "schema": "v1",
                    "counts": {"items": 1, "prices": 1},
                    "checks": {"prices[0].price": "9.90", "items[0].raw_name": 'אורז פרסי 1 ק"ג'},
                }
            },
        }
        (folder / "expected.json").write_text(json.dumps(expected, ensure_ascii=False), "utf-8")
        assert "newchain" in chain_adapters()
        assert check_folder(get_adapter("7290000000001"), folder) == ["price_full"]  # type: ignore[arg-type]
        assert "newchain" in {p.name for p in chain_dirs(tmp_path)}
    finally:
        REGISTRY.pop("7290000000001", None)


def test_register_rejects_duplicate_chain() -> None:
    with pytest.raises(ValueError):
        register(type("Dup", (chain_adapters()["shufersal"],), {}))


# --------------------------------------------------------------------------- filenames


@pytest.mark.parametrize(
    ("filename", "kind", "chain", "store", "published"),
    [
        (
            "PriceFull7290027600007-001-202610060300.gz",
            "price_full",
            "7290027600007",
            "1",
            "2026-10-06 03:00:00+03:00",
        ),
        (
            "Price7290027600007-001-202610061130.gz",
            "price",
            "7290027600007",
            "1",
            "2026-10-06 11:30:00+03:00",
        ),
        (
            "PromoFull7290058140886-039-202610060300.gz",
            "promo_full",
            "7290058140886",
            "39",
            "2026-10-06 03:00:00+03:00",
        ),
        (
            "Promo7290700100008-000-207-20261006-103225.xml.gz",
            "promo",
            "7290700100008",
            "207",
            "2026-10-06 10:32:25+03:00",
        ),
        (
            "Stores7290058140886-202610060100.xml",
            "stores",
            "7290058140886",
            None,
            "2026-10-06 01:00:00+03:00",
        ),
        (
            "StoresFull7290875100001-000-202610060510.gz",
            "stores",
            "7290875100001",
            None,
            "2026-10-06 05:10:00+03:00",
        ),
        (
            "NULLPriceFull7290055700007-2960-202610060300.gz",
            "price_full",
            "7290055700007",
            "2960",
            "2026-10-06 03:00:00+03:00",
        ),
        (
            "raw/shufersal/1/PriceFull7290027600007-001-202610060300.gz",
            "price_full",
            "7290027600007",
            "1",
            "2026-10-06 03:00:00+03:00",
        ),
        # Real Shufersal Stores name (portal, 2026-10-08): date, then HHM with the minute in tens.
        (
            "Stores7290027600007-000-20261008-020.gz",
            "stores",
            "7290027600007",
            None,
            "2026-10-08 02:00:00+03:00",
        ),
    ],
)
def test_parse_filename(
    filename: str, kind: str, chain: str, store: str | None, published: str
) -> None:
    info = parse_filename(filename)
    assert (info.kind, info.chain_id, info.store_code) == (kind, chain, store)
    assert str(info.published_at) == published


@pytest.mark.parametrize(
    "filename", ["README.md", "Catalog7290027600007-001-202610060300.gz", "PriceFull-001.gz"]
)
def test_detect_kind_rejects_unknown_names(filename: str) -> None:
    with pytest.raises(AdapterError, match=r"\[7290027600007\]"):
        get_adapter("7290027600007").detect_kind(filename)


def test_detect_kind_rejects_other_chains_file() -> None:
    with pytest.raises(AdapterError, match="7290058140886"):
        get_adapter("7290027600007").detect_kind("PriceFull7290058140886-039-202610060300.gz")


def test_victory_accepts_second_chain_id() -> None:
    adapter = get_adapter("7290696200003")
    assert adapter.detect_kind("PriceFull7290058103393-001-202610060300.xml.gz") == "price_full"


def test_every_d13_chain_has_an_adapter() -> None:
    """``smartcart-ingest run --mode full`` skips D13 chains without an adapter (issue #81)."""
    from smartcart_ingest.scheduler import D13_CHAINS

    assert [c.chain_id for c in D13_CHAINS if c.chain_id not in REGISTRY] == []


def test_machsanei_hashuk_second_chain_id_is_an_alias() -> None:
    adapter = get_adapter("7290633800006")
    assert type(adapter) is type(get_adapter("7290661400001"))
    assert adapter.detect_kind("Promo7290633800006-003-202610061110.xml.gz") == "promo"
    assert adapter.portal == "matrix" and adapter.upstream_scraper == "MAHSANI_ASHUK_NEW_SOURCE"


def test_king_store_is_the_bina_chain() -> None:
    adapter = get_adapter("7290058108879")
    assert adapter.portal == "bina" and adapter.upstream_scraper == "KING_STORE"
    # Bina serves compressed bytes under a plain .xml name: detected by content, not extension.
    name = "PriceFull7290058108879-001-202610060510.xml"
    data = (FIXTURES / "king_store" / name).read_bytes()
    assert data[:2] == b"\x1f\x8b"
    assert parse_fixture(adapter, FIXTURES / "king_store" / name).prices


# --------------------------------------------------------------------------- alerts (#32)


def _raw_for(chain_id: str, name: str, data: bytes):
    adapter = get_adapter(chain_id)
    assert isinstance(adapter, RegulationAdapter)
    return adapter, adapter.raw_file_for(name, data)


def test_empty_bytes_raise_adapter_error_naming_chain() -> None:
    adapter, raw = _raw_for("7290058140886", "PriceFull7290058140886-039-202610060300.gz", b"")
    with pytest.raises(AdapterError, match=r"^\[7290058140886\].*empty"):
        adapter.parse(raw, b"")


def test_not_xml_raises_adapter_error() -> None:
    data = gzip.compress(b"<html><body>link expired", mtime=0)
    adapter, raw = _raw_for("7290803800003", "PriceFull7290803800003-005-202610060300.gz", data)
    with pytest.raises(AdapterError, match=r"\[7290803800003\]"):
        adapter.parse(raw, data)


def test_rows_without_records_raise() -> None:
    doc = b"<Root><ChainId>7290873255550</ChainId><StoreId>2</StoreId><Items><Item><ItemCode></ItemCode></Item></Items></Root>"
    adapter, raw = _raw_for("7290873255550", "PriceFull7290873255550-002-202610060300.gz", doc)
    with pytest.raises(AdapterError, match=r"\[7290873255550\].*ItemCode"):
        adapter.parse(raw, doc)


def test_file_from_another_chain_is_rejected() -> None:
    doc = b"<Root><ChainId>7290058140886</ChainId><StoreId>39</StoreId><Items><Item><ItemCode>1</ItemCode><ItemName>x</ItemName><ItemPrice>1</ItemPrice></Item></Items></Root>"
    adapter, raw = _raw_for("7290027600007", "PriceFull7290027600007-001-202610060300.gz", doc)
    with pytest.raises(AdapterError, match="header ChainId is 7290058140886"):
        adapter.parse(raw, doc)


def test_raw_chain_mismatch_is_rejected() -> None:
    adapter, raw = _raw_for("7290027600007", "PriceFull7290027600007-001-202610060300.gz", b"x")
    with pytest.raises(AdapterError, match="belongs to chain"):
        get_adapter("7290058140886").parse(raw, b"x")


# --------------------------------------------------------------------------- schema (#57)


def test_v1_and_v2_files_map_to_the_same_records() -> None:
    adapter = get_adapter("7290027600007")
    assert isinstance(adapter, RegulationAdapter)
    folder = FIXTURES / "shufersal"
    v1 = parse_fixture(adapter, folder / "PriceFull7290027600007-001-202610060300.gz")
    v2 = parse_fixture(adapter, folder / "PriceFull7290027600007-001-202610070300.gz")
    assert (v1.raw.schema_version, v2.raw.schema_version) == ("v1", "v2")
    assert v2.items == v1.items[:3]
    assert v2.prices == v1.prices[:3]


def test_v2_marker_as_root_attribute() -> None:
    doc = (
        f'<root {PROVISIONAL_V2_MARKER.name}="2.1"><ChainId>7290027600007</ChainId><StoreId>1</StoreId>'
        "<Items><Item><ItemCode>7290004131074</ItemCode><ItemName>חלב</ItemName><ItemPrice>7.12</ItemPrice></Item></Items></root>"
    ).encode()
    adapter, raw = _raw_for("7290027600007", "PriceFull7290027600007-001-202610060300.gz", doc)
    assert adapter.parse(raw, doc).raw.schema_version == "v2"


def test_unknown_schema_is_an_adapter_error_subclass() -> None:
    assert issubclass(UnknownSchemaError, AdapterError)


@pytest.mark.parametrize("slug", sorted(chain_adapters()))
def test_unknown_container_is_unknown_for_every_chain(slug: str) -> None:
    cls = chain_adapters()[slug]
    doc = f"<Root><ChainId>{cls.chain_id}</ChainId><Catalogue><Entry/></Catalogue></Root>".encode()
    adapter = cls()
    raw = adapter.raw_file_for(f"PriceFull{cls.chain_id}-001-202610060300.gz", doc)
    with pytest.raises(UnknownSchemaError, match=cls.chain_id):
        adapter.parse(raw, doc)


def test_container_outside_chain_dialect_is_unknown() -> None:
    """Shufersal never publishes <Products>; a sudden switch must alert, not load."""
    doc = b"<Prices><ChainID>7290027600007</ChainID><StoreID>1</StoreID><Products><Product><ItemCode>1</ItemCode></Product></Products></Prices>"
    adapter, raw = _raw_for("7290027600007", "PriceFull7290027600007-001-202610060300.gz", doc)
    with pytest.raises(UnknownSchemaError):
        adapter.parse(raw, doc)


def test_no_upstream_types_leak_from_parse() -> None:
    adapter = get_adapter("7290058140886")
    assert isinstance(adapter, RegulationAdapter)
    parsed = parse_fixture(
        adapter, FIXTURES / "ramilevy" / "PriceFull7290058140886-039-202610060300.gz"
    )
    for record in [parsed.raw, *parsed.items, *parsed.prices]:
        assert type(record).__module__ == "smartcart_ingest.models"


# --------------------------------------------------------------------------- real files


# Real portal files live in ``fixtures/<slug>/real/`` (committed by the "Portal probe" workflow
# with ``commit_fixtures``: Stores whole, PriceFull trimmed to its first 200 rows, plus a
# MANIFEST.json with the source file, hashes, times, row counts and the gate result seen on the
# runner) or in ``fixtures/real/<slug>/`` (``fetch_fixtures.py``'s default output). They are
# untrusted data: only the chain adapters read them. The synthetic fixtures stay as they are.

DOCUMENTED_GATES = {"zero_price", "price_jump", "item_count_drop", "stale_date"}
"""The quality gates of docs/ingestion.md; a real file may only be quarantined by these."""
MANIFEST_NAMES = {"MANIFEST.json", "manifest.json"}


def real_fixture_files(root: Path = FIXTURES) -> list[tuple[str, Path]]:
    """``[(chain slug, file)]`` for every real file under ``<slug>/real/`` and ``real/<slug>/``."""
    found: list[tuple[str, Path]] = []
    for chain_dir in chain_dirs(root):
        real = chain_dir / "real"
        if real.is_dir():
            found += [(chain_dir.name, p) for p in sorted(real.iterdir())
                      if p.is_file() and p.name not in MANIFEST_NAMES]  # fmt: skip
    legacy = root / "real"
    if legacy.is_dir():
        found += [(p.parent.name, p) for p in sorted(legacy.rglob("*"))
                  if p.is_file() and p.name not in MANIFEST_NAMES]  # fmt: skip
    return found


def real_manifest_entry(file: Path) -> dict[str, Any]:
    """The MANIFEST.json entry of a real file, or {} when there is none."""
    manifest = file.parent / "MANIFEST.json"
    if not manifest.is_file():
        return {}
    files = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
    return next((e for e in files if e.get("file") == file.name), {})


def documented_gates(file: Path) -> set[str]:
    gates = set((real_manifest_entry(file).get("gate") or {}).get("gates") or [])
    assert gates <= DOCUMENTED_GATES, (
        f"{file.name}: undocumented gate(s) {gates - DOCUMENTED_GATES}"
    )
    return gates


REAL_FILES = real_fixture_files()
REAL_CHAINS = sorted({slug for slug, _ in REAL_FILES})
NO_REAL = (
    "no real fixtures yet; run the Portal probe workflow with commit_fixtures (docs/ingestion.md)"
)


def test_real_fixture_discovery_reads_chain_real_dirs(tmp_path: Path) -> None:
    """The discovery itself, on a temporary tree (runs whether or not real files exist)."""
    (tmp_path / "victory" / "real").mkdir(parents=True)
    (tmp_path / "victory" / "real" / "Stores7290696200003-000-202610080900.xml.gz").write_bytes(
        b"x"
    )
    (tmp_path / "victory" / "real" / "MANIFEST.json").write_text("{}")
    (tmp_path / "real" / "shufersal").mkdir(parents=True)
    (tmp_path / "real" / "shufersal" / "Stores7290027600007-000-202610080201.gz").write_bytes(b"x")
    (tmp_path / "real" / "manifest.json").write_text("{}")
    found = [(slug, p.name) for slug, p in real_fixture_files(tmp_path)]
    assert found == [("victory", "Stores7290696200003-000-202610080900.xml.gz"),
                     ("shufersal", "Stores7290027600007-000-202610080201.gz")]  # fmt: skip


@pytest.mark.skipif(not REAL_FILES, reason=NO_REAL)
@pytest.mark.parametrize(
    ("slug", "file"), REAL_FILES, ids=lambda v: v if isinstance(v, str) else v.name
)
def test_real_fixture_parses(slug: str, file: Path) -> None:
    adapter = chain_adapters()[slug]()
    info = adapter.parse_filename(file.name)
    assert info.published_at is not None, "publication time not parsed from the file name"
    parsed = parse_fixture(adapter, file)
    assert parsed.raw.schema_version in ("v1", "v2")
    gates = documented_gates(file)
    if info.kind == "stores":
        assert parsed.stores, "a Stores file with no stores"
        assert all(s.store_code for s in parsed.stores)
        return
    assert info.store_code, "store code not parsed from the file name"
    assert parsed.items, "no items"
    assert parsed.prices, "no prices"
    assert all(p.store_code for p in parsed.prices), "a price without a store code"
    if "zero_price" not in gates:
        assert all(p.price > 0 for p in parsed.prices), "a zero or negative price"
    entry = real_manifest_entry(file)
    if entry.get("items_trimmed") is not None:
        assert len(parsed.prices) <= entry["items_trimmed"]


@pytest.mark.db
@pytest.mark.skipif(not REAL_FILES, reason=NO_REAL)
@pytest.mark.parametrize("slug", REAL_CHAINS)
def test_real_fixtures_load_or_are_quarantined_for_a_documented_reason(db, tmp_path, slug) -> None:
    """The chain's real files through the Scheduler path (adapter, gates, loader) with the clock
    one hour after the newest file, as the VPS would have seen them: each one loads, or is
    quarantined only by gates its MANIFEST.json recorded on the runner."""
    from datetime import timedelta

    from smartcart_ingest import tracking
    from smartcart_ingest.alerts import Alerter
    from smartcart_ingest.download import sha256_hex
    from smartcart_ingest.rawstore import LocalRawStore
    from smartcart_ingest.scheduler import Scheduler
    from smartcart_ingest.settings import Settings
    from tests.fakes import FakeFetcher, RecordingSink

    adapter = chain_adapters()[slug]()
    files = [p for s, p in REAL_FILES if s == slug]
    fetcher = FakeFetcher()
    published = []
    for path in files:
        info = adapter.parse_filename(path.name)
        published.append(info.published_at)
        fetcher.add(info.kind, path.read_bytes(), chain_id=adapter.chain_id, name=path.name)
    now = max(published) + timedelta(hours=1)
    sink = RecordingSink()
    sched = Scheduler(db, fetcher, LocalRawStore(tmp_path), Alerter([sink]), Settings(),
                      adapter_for=lambda c: chain_adapters()[slug](), now=lambda: now,
                      sleep=lambda s: None)  # fmt: skip
    rep = sched.run_full([adapter.chain_id]).chains[0]
    assert rep.error is None, rep.error
    for path in files:
        row = tracking.get_by_sha(db, sha256_hex(path.read_bytes()))
        assert row is not None, f"{path.name} was not tracked"
        if row.status == "quarantined":
            gates = {g for (g,) in db.execute(
                "SELECT gate FROM quarantine_events WHERE file_id = %s", (row.id,)).fetchall()}  # fmt: skip
            assert gates and gates <= documented_gates(path), (path.name, gates, sink.alerts)
        else:
            assert row.status == "loaded", (path.name, row.status, row.reason)
