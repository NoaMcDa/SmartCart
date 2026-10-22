"""Proposals from a loaded database (issue #52): which items count as unmapped, how many stores
carry them, the price events, and the search misses that name a group."""

from __future__ import annotations

import pytest
from test_match_seed import seed_catalog

from smartcart_catalog import proposals as P
from smartcart_catalog.seed import load_catalog
from smartcart_catalog.taxonomy import default_data_dir


def gtin(prefix12: str) -> str:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(prefix12))
    return prefix12 + str((10 - total % 10) % 10)


@pytest.fixture
def shelves(db):
    ids = seed_catalog(db)
    for cid in ("pd-a", "pd-b", "gold"):
        db.execute(
            "INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (cid, f"chain {cid}")
        )
    stores: dict[str, list[int]] = {"pd-a": [], "pd-b": []}
    for chain, n in (("pd-a", 3), ("pd-b", 2)):
        for i in range(n):
            stores[chain].append(db.execute(
                "INSERT INTO stores (chain_id, store_code, name) VALUES (%s, %s, 's') RETURNING id",
                (chain, f"s{i}")).fetchone()[0])  # fmt: skip
    db.execute("SELECT ensure_price_partition(now()::date)")

    def item(chain, code, name, barcode=None, *, base=None, at=(), qty=None, unit=None):
        iid = db.execute(
            "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (chain, code, barcode, name, qty, unit)).fetchone()[0]  # fmt: skip
        if base is not None:
            db.execute("INSERT INTO prices (item_id, store_id, price, valid_from)"
                       " VALUES (%s, NULL, %s, now())", (iid, base))  # fmt: skip
        for sid, price in at:
            db.execute("INSERT INTO prices (item_id, store_id, price, valid_from)"
                       " VALUES (%s, %s, %s, now())", (iid, sid, price))  # fmt: skip
        return iid

    return db, ids, stores, item


@pytest.mark.db
def test_unmapped_items_stores_prices_and_events(shelves) -> None:
    db, ids, stores, item = shelves
    code = gtin("729000555666")
    a = item("pd-a", "1", "רוטב טבסקו חריף", code, base=12, qty=60, unit="מל")  # base: 3 stores
    b = item(
        "pd-b", "1", "רוטב טבסקו חריף", code, at=[(stores["pd-b"][0], 11.5)], qty=60, unit="מל"
    )
    db.execute("INSERT INTO prices (item_id, store_id, price, valid_from)"
               " VALUES (%s, NULL, 13, now() - interval '1 day')", (a,))  # fmt: skip
    mapped = item("pd-a", "2", "חלב טרי 3%", base=6)
    rejected = item("pd-a", "3", "רוטב פיקנטי", base=7)
    gold = item("gold", "g", "פריט זהב", base=1)
    cid = next(iter(ids.values()))
    for iid, human_rejected in ((mapped, False), (rejected, True), (gold, False)):
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
            " human_rejected) VALUES (%s, %s, 'any_brand', 0.9, 'human', %s)",
            (iid, cid, human_rejected))  # fmt: skip
    pool = P.items_from_db(db)
    keys = {i.key: i for i in pool.items}
    assert "pd-a:2" not in keys  # mapped
    assert "gold:g" not in keys  # the synthetic gold chain is never a candidate
    assert "pd-a:3" in keys  # a rejected mapping does not count as mapped
    ia, ib = keys["pd-a:1"], keys["pd-b:1"]
    assert ia.stores == 3 and ib.stores == 1  # a base price counts every physical store
    assert ia.price_events == 2 and ia.price == 12  # the base price, not the older event
    assert ib.price == 11.5 and ia.item_id == a
    assert pool.total_items == 4 and pool.mapped_items == 4 - len(pool.items)


@pytest.mark.db
def test_the_same_barcode_at_two_chains_becomes_a_proposal_with_misses(shelves) -> None:
    db, _, stores, item = shelves
    code = gtin("729000555777")
    item("pd-a", "1", "רוטב טבסקו חריף", code, base=12, qty=60, unit="מל")
    item(
        "pd-b",
        "1",
        "טבסקו רוטב חריף",
        code,
        at=[(s, 11) for s in stores["pd-b"]],
        qty=60,
        unit="מל",
    )
    for _ in range(4):
        db.execute("INSERT INTO search_misses (query_norm, source) VALUES ('טבסקו', 'search')")
    pool = P.items_from_db(db)
    assert dict(pool.misses)["טבסקו"] == 4
    run = P.propose(pool, load_catalog(default_data_dir()))
    p = next(p for p in run.proposals if "טבסקו" in p.display_name_he)
    assert p.chains == 2 and p.stores == 3 + 2 and p.shared_barcodes == 1 and p.miss_hits == 4
    assert p.items == 2 and p.price_events == 3  # 1 base event + 2 store events
    assert run.stats["barcodes_shared_chains"] == 1


@pytest.mark.db
def test_a_database_without_search_misses_still_works(shelves) -> None:
    db, _, _, item = shelves
    item("pd-a", "1", "רוטב טבסקו חריף", base=12)
    db.execute("DROP TABLE search_misses CASCADE")
    pool = P.items_from_db(db)
    assert pool.misses == [] and pool.unmapped_items == 1
