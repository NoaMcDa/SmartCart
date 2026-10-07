"""A quality-gate test for every registered chain adapter (issue #42), using each chain's
fixture files end to end: download, parse with the real adapter, gates, load.

The fixtures are the adapters' checked-in files under ``tests/fixtures/<slug>`` (synthetic until
the VPS fetches real ones; see docs/adapters.md). Adding a chain adds a case here automatically.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from smartcart_ingest import quality, tracking
from smartcart_ingest.adapters import REGISTRY, get_adapter
from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.alerts import Alerter
from smartcart_ingest.download import sha256_hex
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import Scheduler
from smartcart_ingest.settings import Settings
from tests.fakes import FakeFetcher, RecordingSink, kind_of

FIXTURES = Path(__file__).parent / "fixtures"
KINDS = ("stores", "price_full", "promo_full")


def _chains() -> list[type[RegulationAdapter]]:
    return sorted(
        {
            cls
            for cls in REGISTRY.values()
            if isinstance(cls, type)
            and issubclass(cls, RegulationAdapter)
            and (FIXTURES / cls.slug).is_dir()
        },
        key=lambda c: c.slug,
    )


def _expected(slug: str) -> dict:
    return json.loads((FIXTURES / slug / "expected.json").read_text(encoding="utf-8"))["files"]


def _first_files(slug: str) -> list[Path]:
    """The earliest fixture of each full kind that the adapter is expected to parse."""
    expected = _expected(slug)
    out = []
    for kind in KINDS:
        files = sorted(
            FIXTURES / slug / name
            for name, spec in expected.items()
            if spec.get("kind") == kind and "error" not in spec
        )
        if files:
            out.append(files[0])
    return out


def _bad_files(slug: str) -> dict[Path, str]:
    """Fixtures the adapter must reject, with the alert kind each should raise."""
    kinds = {"AdapterError": "parse_failure", "UnknownSchemaError": "unknown_schema"}
    return {
        FIXTURES / slug / name: kinds[spec["error"]]
        for name, spec in _expected(slug).items()
        if spec.get("error") in kinds
    }


def test_every_registered_chain_has_fixtures_here() -> None:
    assert len(_chains()) >= 2


@pytest.mark.db
@pytest.mark.parametrize("cls", _chains(), ids=lambda c: c.slug)
def test_chain_fixture_passes_the_gates_and_a_bad_copy_is_caught(db, tmp_path, cls) -> None:
    adapter = get_adapter(cls.chain_id)
    files = _first_files(cls.slug)
    assert any(kind_of(p.name) == "price_full" for p in files), cls.slug
    fetcher = FakeFetcher()
    published = []
    for path in files:
        info = adapter.parse_filename(path.name)
        if info.published_at:
            published.append(info.published_at)
        fetcher.add(info.kind, path.read_bytes(), chain_id=cls.chain_id, name=path.name)
    now = max(published) + timedelta(hours=1)
    sink = RecordingSink()
    sched = Scheduler(
        db,
        fetcher,
        LocalRawStore(tmp_path),
        Alerter([sink]),
        Settings(),
        adapter_for=get_adapter,
        now=lambda: now,
        sleep=lambda s: None,
    )

    rep = sched.run_full([cls.chain_id]).chains[0]
    assert (rep.quarantined, rep.failed, rep.error) == (0, 0, None), sink.alerts
    assert rep.loaded == len(files)

    # The same chain's PriceFull, made bad two ways, is caught by the gates.
    pf = next(p for p in files if kind_of(p.name) == "price_full")
    row = tracking.get_by_sha(db, sha256_hex(pf.read_bytes()))
    parsed = adapter.parse(row.to_raw(), pf.read_bytes())
    assert parsed.prices, cls.slug
    first = parsed.prices[0]
    zero = parsed.model_copy(
        update={"prices": [first.model_copy(update={"price": 0}), *parsed.prices[1:]]}
    )
    jump = parsed.model_copy(
        update={"prices": [first.model_copy(update={"price": first.price * 4 + 1})]}
    )
    th = Settings().thresholds_for(cls.chain_id)
    assert "zero_price" in [f.gate for f in quality.check(db, zero, th, now=now)]
    assert "price_jump" in [f.gate for f in quality.check(db, jump, th, now=now)]
    late = now + timedelta(hours=th.stale_file_max_age_hours + 1)
    assert "stale_date" in [f.gate for f in quality.check(db, parsed, th, now=late)]


@pytest.mark.db
@pytest.mark.parametrize("cls", [c for c in _chains() if _bad_files(c.slug)], ids=lambda c: c.slug)
def test_chain_fixtures_the_adapter_rejects_fail_and_alert(db, tmp_path, cls) -> None:
    bad = _bad_files(cls.slug)
    adapter = get_adapter(cls.chain_id)
    fetcher = FakeFetcher()
    for path in bad:
        fetcher.add(adapter.detect_kind(path.name), path.read_bytes(), chain_id=cls.chain_id,
                    name=path.name)  # fmt: skip
    sink = RecordingSink()
    sched = Scheduler(
        db, fetcher, LocalRawStore(tmp_path), Alerter([sink]), Settings(),
        adapter_for=get_adapter, sleep=lambda s: None,
    )  # fmt: skip
    rep = sched.run_full([cls.chain_id]).chains[0]
    # Full kinds only are listed in a full run; count what was actually processed.
    processed = {p: k for p, k in bad.items() if kind_of(p.name) in KINDS}
    assert rep.loaded == 0 and rep.failed == len(processed)
    assert sorted(a.kind for a in sink.alerts) == sorted(processed.values())
    assert all(a.chain_id == cls.chain_id for a in sink.alerts)


# --------------------------------------------------------------------------- base prices (#80)
#
# The price-jump gate compares a store price with the store's own latest event and, when the
# store has no history for the item (or is not loaded yet), with the chain base price
# (``store_id NULL``). A chain-level record is compared with the base.


def _load_base_price(db, code: str, amount: str) -> None:
    from smartcart_ingest.loader import load
    from tests.fakes import NOW, FakeAdapter, encode, item, parsed_file, price, store

    data = encode(
        stores=[store(c) for c in ("1", "2")],
        items=[item(code)],
        prices=[price(code, None, amount, NOW - timedelta(hours=6))],
        salt=f"base-{code}",
    )
    parsed = parsed_file("price_full", data, None, NOW - timedelta(hours=6), f"raw/fake/b-{code}")
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    load(db, parsed, FakeAdapter())


def _jumps(db, prices) -> list[str]:
    from tests.fakes import NOW, encode, parsed_file

    parsed = parsed_file("price", encode(prices=prices, salt="jump"), "1", NOW, "raw/fake/jump")
    failure = quality.gate_price_jump(db, parsed, 3.0)
    return [] if failure is None else failure.detail.split(": ", 1)[1].split(", ")


@pytest.mark.db
def test_price_jump_falls_back_to_the_chain_base_price(db) -> None:
    from tests.fakes import price

    _load_base_price(db, "100", "9.90")
    # Store 1 has no event of its own for the item: 40.00 is more than 3x the base 9.90.
    assert _jumps(db, [price("100", "1", "40.00")]) == ["100@1 9.90->40.00"]
    # A store that is not loaded yet is compared with the base too.
    assert _jumps(db, [price("100", "77", "40.00")]) == ["100@77 9.90->40.00"]
    # A chain-level record is compared with the previous base.
    assert _jumps(db, [price("100", None, "40.00")]) == ["100@base 9.90->40.00"]
    # Within the factor, nothing is flagged.
    assert _jumps(db, [price("100", "1", "29.70"), price("100", None, "12.00")]) == []


@pytest.mark.db
def test_price_jump_prefers_the_store_event_over_the_base(db) -> None:
    from smartcart_ingest.loader import load
    from tests.fakes import NOW, FakeAdapter, encode, item, parsed_file, price, store

    _load_base_price(db, "200", "5.00")
    data = encode(stores=[store("1")], items=[item("200")],
                  prices=[price("200", "1", "20.00", NOW - timedelta(hours=5))], salt="exc")  # fmt: skip
    parsed = parsed_file("price", data, "1", NOW - timedelta(hours=5), "raw/fake/exc-200")
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    load(db, parsed, FakeAdapter())
    # Store 1's own price is 20.00, so 50.00 is fine there, but 4x the base at store 2.
    assert _jumps(db, [price("200", "1", "50.00"), price("200", "2", "50.00")]) == [
        "200@2 5.00->50.00"
    ]
