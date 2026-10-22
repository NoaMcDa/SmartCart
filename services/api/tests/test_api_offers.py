"""A store's item for the quantity asked, not only the best unit price (docs/optimizer.md, "Offers
for the quantity asked").

The precompute keeps the offer with the best effective unit price in ``effective_prices`` (rank 0,
what /search and the history read) and the other offers that are the cheapest line for some quantity
or audience in ``effective_offers`` (``offers.choose_extras``). /compare and /optimize take, per
line, the cheapest line for the quantity asked among them.

Here: the eggs of the issue (12 asked is the 12-pack, 30 the tray), a promo that only pays at the
asked quantity (two items; two promos on one item), a club deal against non-club deals at different
quantities, items of one size only for weights and volumes, an exact barcode, and the selection
itself with no database. The randomized comparison with an independent reference is in
``test_api_optimizer_props_db.py``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World, add_promo
from test_api_packs import add_counted_canonical, add_pack_item, ep_row, line

from smartcart_api import offers
from smartcart_api.precompute import precompute_effective_prices

D = Decimal
pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


def offer_rows(
    db, w: World, canon: str, store: str = "home", flex: str = "any_brand"
) -> list[dict]:
    cur = db.execute(
        "SELECT rank, kind, item_id, shelf_price, effective_price, promo_min_qty, club_required,"
        " club_name, pack_units FROM effective_offers"
        " WHERE canonical_id = %s AND store_id = %s AND flex_level = %s ORDER BY rank",
        (w.canon[canon], w.stores[store], flex),
    )
    return [dict(zip([c.name for c in cur.description], r, strict=True)) for r in cur.fetchall()]


def member_line(client, w: World, canon: str, quantity, clubs: list[str], store: str = "home"):
    """The line of ``/compare`` for a user who marked ``clubs``."""
    body = {
        "items": [{"canonical_id": w.canon[canon], "quantity": quantity}],
        "location": w.location,
        "clubs": clubs,
    }
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    return {s["store_id"]: s for s in r.json()["stores"]}[w.stores[store]]["items"][0]


def totals(
    client, w: World, canon: str, quantities, store: str = "home", clubs: list[str] | None = None
) -> dict:
    return {
        q: D(
            (
                member_line(client, w, canon, q, clubs, store)
                if clubs
                else line(client, w, canon, q, store)
            )["line_total"]
        )
        for q in quantities
    }


# --- the eggs: a tray beats the 12-pack by unit price, not for 12 eggs ----------------------------


@pytest.mark.parametrize("pack_size", [1, 12])
def test_twelve_eggs_are_the_twelve_pack_and_thirty_the_tray(
    client, db, world: World, pack_size: int
) -> None:
    """Close level: a tray of 30 at 29.90 (1.00 an egg) beats a 12-pack at 14.20 (1.18) by unit
    price. For 12 eggs the 12-pack is the cheapest way to buy; for 30 the tray is. ``pack_size`` 1
    counts single eggs (12 and 30 asked), 12 counts packs of a dozen (1 and 2.5 asked)."""
    add_counted_canonical(db, world, "eggs", pack_size)
    add_pack_item(db, world, "p12", "eggs", "t-c1", "ביצים 12 יח גדול L", "1.00", "יחידות", "14.20")
    add_pack_item(
        db, world, "p30", "eggs", "t-c1", "ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90",
        level="close",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    # /search and the history read the best unit price: the tray. The 12-pack is the other offer.
    assert ep_row(db, world, "eggs", "home", "close")["item_id"] == world.items["p30"]
    rows = offer_rows(db, world, "eggs", flex="close")
    assert [(r["rank"], r["kind"], r["item_id"]) for r in rows] == [(1, "pack", world.items["p12"])]
    assert (
        offer_rows(db, world, "eggs", flex="any_brand") == []
    )  # the tray is not an any-brand item

    div = D(1) if pack_size == 1 else D(12)  # eggs per unit of quantity
    asked = {eggs: D(eggs) / div for eggs in (12, 24, 30, 36)}
    got = {
        eggs: line(client, world, "eggs", float(q), flex_level="close") for eggs, q in asked.items()
    }
    assert got[12]["item_id"] == world.items["p12"] and D(got[12]["line_total"]) == D("14.20")
    assert not got[12]["is_substitute"]  # an any-brand item, not the tray (a close substitute)
    assert got[24]["item_id"] == world.items["p12"] and D(got[24]["line_total"]) == D("28.40")
    assert got[30]["item_id"] == world.items["p30"] and D(got[30]["packs"]) == 1
    assert D(got[30]["line_total"]) == D("29.90") and got[30]["is_substitute"]
    assert got[36]["item_id"] == world.items["p12"] and D(got[36]["line_total"]) == D("42.60")
    # At any brand only the 12-pack competes: unchanged.
    assert D(line(client, world, "eggs", float(asked[12]))["line_total"]) == D("14.20")

    # /optimize prices the same lines, with the heuristic and with the MILP.
    body = {
        "items": [
            {
                "canonical_id": world.canon["eggs"],
                "quantity": float(asked[12]),
                "flex_level": "close",
            }
        ],
        "location": world.location,
    }
    for solver in ("heuristic", "milp"):
        r = client.post("/optimize", json={**body, "solver": solver})
        assert r.status_code == 200, r.text
        only = r.json()["single"]["stores"][0]["store"]["items"][0]
        assert only["item_id"] == world.items["p12"] and D(only["line_total"]) == D("14.20")


def test_a_pack_of_six_is_the_best_pair_for_twelve_when_the_dozen_is_dear(
    client, db, world: World
) -> None:
    """Three sizes: 6 for 8.40 (1.40 an egg), 12 for 17.00 (1.42), 30 for 29.90 (1.00). By unit
    price the tray. 12 eggs cost 16.80 as two packs of 6 and 17.00 as the dozen: the packs of 6
    win; 6 eggs are one pack of 6; 30 eggs are the tray. Whole packs throughout."""
    add_counted_canonical(db, world, "eggs", 12)
    for key, name, price, units in (
        ("p6", "ביצים 6 יח'", "8.40", 6),
        ("p12", "ביצים 12 יח'", "17.00", 12),
        ("p30", "ביצים 30 יח'", "29.90", 30),
    ):
        add_pack_item(
            db, world, key, "eggs", "t-c1", name, str(units), "יחידות", price, level="close"
        )
    precompute_effective_prices(db, chains=world.chains)
    assert ep_row(db, world, "eggs", "home", "close")["item_id"] == world.items["p30"]
    twelve = line(client, world, "eggs", 1, flex_level="close")
    assert twelve["item_id"] == world.items["p6"] and D(twelve["packs"]) == 2
    assert D(twelve["line_total"]) == D("16.80")
    six = line(client, world, "eggs", 0.5, flex_level="close")
    assert six["item_id"] == world.items["p6"] and D(six["line_total"]) == D("8.40")
    thirty = line(client, world, "eggs", 2.5, flex_level="close")
    assert thirty["item_id"] == world.items["p30"] and D(thirty["line_total"]) == D("29.90")
    assert len(offer_rows(db, world, "eggs", flex="close")) <= offers.MAX_EXTRA_OFFERS


# --- promos that pay at one quantity only ---------------------------------------------------------


def two_items_with_promos(db, world: World):
    """Two brands of one canonical at the home chain: B has the best unit price (4 for 28 =
    7.00), A has a deal that pays at two (2 for 16 = 8.00)."""
    add_counted_canonical(db, world, "soda", 1)
    a = add_pack_item(db, world, "soda_a", "soda", "t-c1", "משקה א", "1", "יחידה", "10.00")
    b = add_pack_item(db, world, "soda_b", "soda", "t-c1", "משקה ב", "1", "יחידה", "9.00")
    add_promo(db, "t-c1", None, "SA", [a], "bundle", "16.00", min_qty="2", description="2 ב-16")
    add_promo(db, "t-c1", None, "SB", [b], "bundle", "28.00", min_qty="4", description="4 ב-28")
    precompute_effective_prices(db, chains=world.chains)
    return a, b


def test_a_promo_of_another_item_that_only_pays_at_the_asked_quantity(
    client, db, world: World
) -> None:
    a, b = two_items_with_promos(db, world)
    assert ep_row(db, world, "soda", "home")["item_id"] == b  # rank 0: the best unit price
    rows = offer_rows(db, world, "soda")
    assert [(r["rank"], r["kind"], r["item_id"], r["promo_min_qty"]) for r in rows] == [
        (1, "bundle", a, 2)
    ]
    got = {q: line(client, world, "soda", q) for q in (1, 2, 3, 4, 5, 8)}
    # (item, total): one pack is B (9.00); two and three are A's "2 for 16" (16.00, 26.00); four is
    # B's "4 for 28"; five 28 + 9; eight is two of B's bundles (56) against four of A's (64).
    want = {1: (b, "9.00"), 2: (a, "16.00"), 3: (a, "26.00"), 4: (b, "28.00"), 5: (b, "37.00"),
            8: (b, "56.00")}  # fmt: skip
    for q, (item, total) in want.items():
        assert (got[q]["item_id"], D(got[q]["line_total"])) == (item, D(total)), q
    assert got[2]["promo_applied"] and got[2]["promo_description"] == "2 ב-16"
    # The MILP sees the same lines.
    for q, (item, total) in want.items():
        body = {
            "items": [{"canonical_id": world.canon["soda"], "quantity": q}],
            "location": world.location,
            "solver": "milp",
        }
        r = client.post("/optimize", json=body)
        assert r.status_code == 200, r.text
        only = r.json()["single"]["stores"][0]["store"]["items"][0]
        assert (only["item_id"], D(only["line_total"])) == (item, D(total)), q


def test_two_promos_on_one_item_each_pay_at_their_own_quantity(client, db, world: World) -> None:
    """The same item with "2 for 16" and "4 for 28": the second is the best by unit price and was
    the only one considered, so two packs cost 20.00. Now 16.00."""
    add_counted_canonical(db, world, "soda", 1)
    item = add_pack_item(db, world, "soda_a", "soda", "t-c1", "משקה א", "1", "יחידה", "10.00")
    p2 = add_promo(
        db, "t-c1", None, "S2", [item], "bundle", "16.00", min_qty="2", description="2 ב-16"
    )
    p4 = add_promo(
        db, "t-c1", None, "S4", [item], "bundle", "28.00", min_qty="4", description="4 ב-28"
    )
    precompute_effective_prices(db, chains=world.chains)
    assert db.execute(
        "SELECT promo_id FROM effective_prices WHERE canonical_id = %s AND store_id = %s"
        " AND flex_level = 'any_brand'",
        (world.canon["soda"], world.stores["home"]),
    ).fetchone() == (p4,)
    assert [r["kind"] for r in offer_rows(db, world, "soda")] == ["bundle"]
    got = totals(client, world, "soda", (1, 2, 3, 4, 6))
    # a line uses one promo: six packs are 28 + two loose (48.00) or three of "2 for 16" (48.00)
    assert got == {1: D("10.00"), 2: D("16.00"), 3: D("26.00"), 4: D("28.00"), 6: D("48.00")}
    three = line(client, world, "soda", 3)
    assert three["promo_description"] == "2 ב-16" and D(three["promo_add_qty"]) == 1
    assert p2 != p4


def test_a_dominated_offer_is_not_kept(db, world: World) -> None:
    """A second item that costs more at every quantity leaves no row."""
    add_counted_canonical(db, world, "soda", 1)
    add_pack_item(db, world, "soda_a", "soda", "t-c1", "משקה א", "1", "יחידה", "9.00")
    add_pack_item(db, world, "soda_b", "soda", "t-c1", "משקה ב", "1", "יחידה", "10.00")
    precompute_effective_prices(db, chains=world.chains)
    assert offer_rows(db, world, "soda") == []
    assert db.execute("SELECT count(*) FROM effective_offers").fetchone() == (0,)


# --- club deals against non-club deals ------------------------------------------------------------


def club_world(db, world: World):
    add_counted_canonical(db, world, "soda", 1)
    item = add_pack_item(db, world, "soda_a", "soda", "t-c1", "משקה א", "1", "יחידה", "10.00")
    add_promo(
        db, "t-c1", None, "C4", [item], "bundle", "20.00", min_qty="4", description="4 למועדון",
        club_only=True, club_name="club-a",
    )  # fmt: skip
    add_promo(db, "t-c1", None, "N3", [item], "bundle", "24.00", min_qty="3", description="3 ב-24")
    add_promo(db, "t-c1", None, "N2", [item], "bundle", "17.00", min_qty="2", description="2 ב-17")
    precompute_effective_prices(db, chains=world.chains)
    return item


def test_a_club_deal_and_non_club_deals_at_different_quantities(client, db, world: World) -> None:
    item = club_world(db, world)
    ep = ep_row(db, world, "soda", "home")
    assert ep["item_id"] == item and ep["effective_unit_price"] == D("5.0000")  # the club deal
    kinds = sorted(r["kind"] for r in offer_rows(db, world, "soda"))
    assert kinds == ["bundle"]  # "2 for 17"; "3 for 24" is the row's own no-club option
    member = totals(client, world, "soda", (1, 2, 3, 4, 5), clubs=["club-a"])
    assert member == {1: D("10.00"), 2: D("17.00"), 3: D("24.00"), 4: D("20.00"), 5: D("30.00")}
    plain = totals(client, world, "soda", (1, 2, 3, 4, 5))
    # Without the club: four packs are "3 for 24" + one at 10.00 (34.00) or two "2 for 17" (34.00);
    # five are 44.00 either way.
    assert plain == {1: D("10.00"), 2: D("17.00"), 3: D("24.00"), 4: D("34.00"), 5: D("44.00")}
    assert all(plain[q] >= member[q] for q in plain)  # marking a club never raises a line
    # The club deal the user did not mark is information, never in the total.
    four = line(client, world, "soda", 4)
    assert four["club_offer_name"] == "club-a" and D(four["club_offer_discount"]) == D("14.00")
    assert not four["club_required"]
    two = line(client, world, "soda", 2)
    assert two["club_offer_name"] is None  # the club deal does not help two packs


def test_a_club_row_of_another_club_does_not_apply(client, db, world: World) -> None:
    club_world(db, world)
    other = totals(client, world, "soda", (4,), clubs=["club-b"])
    assert other == {4: D("34.00")}


# --- weights and volumes: only items of one size are compared -------------------------------------


def test_a_cheaper_small_bottle_is_not_a_cheaper_line(client, db, world: World) -> None:
    """Per 100 ml: a 2 l bottle at 8.60 (0.43) and a 500 ml bottle at 2.90 (0.58) of one canonical.
    One bottle of the best unit price stays the 2 l bottle; the small one is not a cheaper line."""
    add_counted_canonical(db, world, "cola", 1, base="100ml")
    big = add_pack_item(
        db, world, "big", "cola", "t-c1", "קולה", "2000", "מיליליטר", "8.60", "0.43", "100ml"
    )
    add_pack_item(
        db, world, "small", "cola", "t-c1", "סודה", "500", "מיליליטר", "2.90", "0.58", "100ml"
    )
    precompute_effective_prices(db, chains=world.chains)
    assert offer_rows(db, world, "cola") == []
    got = line(client, world, "cola", 1)
    assert got["item_id"] == big and D(got["line_total"]) == D("8.60")


def test_bottles_of_one_size_compete_on_their_promos(client, db, world: World) -> None:
    add_counted_canonical(db, world, "cola", 1, base="100ml")
    a = add_pack_item(
        db, world, "a", "cola", "t-c1", "קולה א", "1000", "מיליליטר", "6.00", "0.60", "100ml"
    )
    b = add_pack_item(
        db, world, "b", "cola", "t-c1", "קולה ב", "1000", "מיליליטר", "5.00", "0.50", "100ml"
    )
    add_promo(db, "t-c1", None, "PA", [a], "bundle", "9.00", min_qty="2", description="2 ב-9")
    add_promo(db, "t-c1", None, "PB", [b], "bundle", "16.00", min_qty="4", description="4 ב-16")
    precompute_effective_prices(db, chains=world.chains)
    got = {q: line(client, world, "cola", q) for q in (1, 2, 3, 4)}
    assert [(got[q]["item_id"], D(got[q]["line_total"])) for q in (1, 2, 3, 4)] == [
        (b, D("5.00")),
        (a, D("9.00")),
        (b, D("15.00")),  # A: 9.00 + 6.00; B: 3 x 5.00: the tie goes to the better unit price
        (b, D("16.00")),
    ]


# --- an exact barcode ------------------------------------------------------------------------------


def test_an_exact_barcode_takes_the_promo_that_pays_for_the_quantity(
    client, db, world: World
) -> None:
    add_counted_canonical(db, world, "soda", 1)
    item = add_pack_item(
        db, world, "soda_a", "soda", "t-c1", "משקה א", "1", "יחידה", "10.00", level="exact"
    )
    add_promo(db, "t-c1", None, "E2", [item], "bundle", "16.00", min_qty="2", description="2 ב-16")
    add_promo(db, "t-c1", None, "E4", [item], "bundle", "28.00", min_qty="4", description="4 ב-28")
    precompute_effective_prices(db, chains=world.chains)
    for q, total in ((1, "10.00"), (2, "16.00"), (3, "26.00"), (4, "28.00")):
        got = line(client, world, "soda", q, flex_level="exact", exact_item_id=item)
        assert got["item_id"] == item and D(got["line_total"]) == D(total), q


# --- the table ---------------------------------------------------------------------------------------


def test_a_rerun_replaces_the_rows_and_the_run_counts_them(db, world: World) -> None:
    a, b = two_items_with_promos(db, world)
    assert len(offer_rows(db, world, "soda")) == 1
    metrics = db.execute(
        "SELECT metrics FROM match_runs WHERE kind = 'precompute' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    assert metrics["offer_rows"] >= 1 and metrics["offers_by_kind"]["bundle"] >= 1
    # The deal of A ends: nothing but the best unit price is left, and the stale row goes.
    db.execute("UPDATE promos SET ends_at = now() - interval '1 hour' WHERE description = '2 ב-16'")
    again = precompute_effective_prices(db, chains=world.chains)
    assert offer_rows(db, world, "soda") == []
    assert again.offer_rows == 0
    assert ep_row(db, world, "soda", "home")["item_id"] == b


def test_the_table_is_bounded_and_ranked(db) -> None:
    db_columns = {
        r[0]: r[1]
        for r in db.execute(
            "SELECT column_name, data_type FROM information_schema.columns"
            " WHERE table_name = 'effective_offers' AND table_schema = current_schema()"
        )
    }
    assert db_columns["rank"] == "smallint" and "kind" in db_columns
    with pytest.raises(Exception, match="effective_offers"):
        with db.transaction():
            db.execute(
                "INSERT INTO effective_offers (canonical_id, store_id, flex_level, rank, kind,"
                " item_id, shelf_price, effective_unit_price, uom, price_valid_from,"
                " effective_price) SELECT 1, 1, 'close', 5, 'pack', 1, 1, 1, 'unit', now(), 1"
            )
