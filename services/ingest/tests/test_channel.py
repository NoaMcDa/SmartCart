"""Sales-channel tagging (#53): chain rules, the shared heuristic and per-chain fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from smartcart_ingest.adapters import get_adapter
from smartcart_ingest.adapters._common import RegulationAdapter
from smartcart_ingest.adapters.base import ChainAdapter
from smartcart_ingest.channel import ONLINE_KEYWORDS, heuristic_is_online, tag_all, tag_channel
from smartcart_ingest.models import StoreRecord

FIXTURES = Path(__file__).parent / "fixtures"

# chain id -> (stores fixture, online store codes, rule that identifies them)
CHAIN_ONLINE = {
    "7290027600007": (
        "shufersal/Stores7290027600007-000-202610060201.gz",
        {"90"},
        "sub-chain ONLINE",
    ),
    "7290058140886": ("ramilevy/Stores7290058140886-202610060100.xml", {"331"}, "store code"),
    "7290103152017": ("osherad/Stores7290103152017-202610060100.xml", set(), "none"),
    "7290803800003": ("yohananof/Stores7290803800003-202610060100.xml", {"100"}, "StoreType 2"),
    "7290696200003": ("victory/Stores7290696200003-000-202610060100.xml.gz", {"45"}, "name"),
    "7290700100008": (
        "hazihinam/Stores7290700100008-000-000-20261006-010000.xml.gz",
        {"299"},
        "name אתר",
    ),
    "7290873255550": ("tivtaam/Stores7290873255550-000-202610060100.gz", {"80"}, "address"),
    "7290055700007": ("mega/Stores7290055700007-000-202610060100.gz", {"5000"}, "store code"),
}


def _store(**kw: object) -> StoreRecord:
    base: dict[str, object] = {"chain_id": "7290027600007", "store_code": "1", "name": "סניף"}
    base.update(kw)
    return StoreRecord(**base)  # type: ignore[arg-type]


class _NoRule(ChainAdapter):
    chain_id = "0000000000000"
    display_name = "none"
    portal = "other"

    def detect_kind(self, filename):  # pragma: no cover - unused
        raise NotImplementedError

    def detect_schema(self, xml_root):  # pragma: no cover - unused
        raise NotImplementedError

    def parse(self, raw, data):  # pragma: no cover - unused
        raise NotImplementedError


@pytest.mark.parametrize("chain_id", sorted(CHAIN_ONLINE))
def test_each_chain_online_record_from_fixture(chain_id: str) -> None:
    rel, online_codes, _rule = CHAIN_ONLINE[chain_id]
    adapter = get_adapter(chain_id)
    assert isinstance(adapter, RegulationAdapter)
    file = FIXTURES / rel
    data = file.read_bytes()
    parsed = adapter.parse(adapter.raw_file_for(file.name, data), data)
    assert {s.store_code for s in parsed.stores if s.channel == "online"} == online_codes
    # Re-tagging is idempotent.
    assert tag_all(adapter, parsed.stores) == parsed.stores


def test_chains_without_online_record_are_declared() -> None:
    no_online = sorted(
        cid
        for cid in CHAIN_ONLINE
        if get_adapter(cid).has_online_record is False  # type: ignore[attr-defined]
    )
    assert no_online == ["7290103152017"]  # Osher Ad
    for cid in no_online:
        assert CHAIN_ONLINE[cid][1] == set()


@pytest.mark.parametrize(
    ("store", "expected"),
    [
        (_store(name="שופרסל אונליין"), True),
        (_store(name="Shufersal Online"), True),
        (_store(name="סניף", city="משלוחים"), True),
        (_store(name="מכירות באינטרנט"), True),
        (_store(name="סניף", address="און ליין"), True),
        (_store(name="שופרסל דיל חולון", city="חולון", address="המרכבה 1"), False),
    ],
)
def test_shared_heuristic(store: StoreRecord, expected: bool) -> None:
    assert heuristic_is_online(store) is expected
    assert tag_channel(_NoRule(), store).channel == ("online" if expected else "physical")


def test_known_codes_in_heuristic() -> None:
    assert heuristic_is_online(_store(store_code="5000"), {"5000"})
    assert not heuristic_is_online(_store(store_code="5001"), {"5000"})


def test_declared_online_is_kept() -> None:
    store = _store(name="סניף רגיל", channel="online")
    assert tag_channel(_NoRule(), store) is store


def test_chain_rule_without_keyword() -> None:
    tivtaam = get_adapter("7290873255550")
    store = _store(chain_id="7290873255550", name="טיב טעם הזמנות", address="מרכז הפצה ראשון לציון")
    assert not heuristic_is_online(store)
    assert tivtaam.online_store_rule(store)
    assert tag_channel(tivtaam, store).channel == "online"


def test_tagging_never_mutates() -> None:
    store = _store(name="אונליין")
    tagged = tag_channel(_NoRule(), store)
    assert store.channel == "physical" and tagged.channel == "online"


def test_online_stores_may_lack_coordinates() -> None:
    adapter = get_adapter("7290027600007")
    assert isinstance(adapter, RegulationAdapter)
    file = FIXTURES / CHAIN_ONLINE["7290027600007"][0]
    data = file.read_bytes()
    online = [
        s
        for s in adapter.parse(adapter.raw_file_for(file.name, data), data).stores
        if s.channel == "online"
    ]
    assert online and all(s.lat is None and s.lon is None for s in online)


def test_keywords_are_documented() -> None:
    doc = (Path(__file__).parents[3] / "docs" / "adapters.md").read_text(encoding="utf-8")
    for keyword in ONLINE_KEYWORDS:
        assert keyword in doc
