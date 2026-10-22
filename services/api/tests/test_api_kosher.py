"""The kosher filter end to end (docs/matching.md, "Kosher"): /compare, /optimize, /optimize/swaps
and /search under a level the person chose.

api_world's milk 3% canonical has three items: the c1 Tnuva item (base 6.90, 5.90 at store A, mapped
exact), the c1 house-brand item (6.20, any brand) and the c2 Tara item (6.40, any brand). Tests
rename them to state (or not) a certification, because the files have no kosher field: only the name
can state one. Prices come from api_world, so every total below is checked by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import EMB, World, add_price
from psycopg.types.json import Jsonb

from smartcart_api import kosher as kosher_mod
from smartcart_api import schemas
from smartcart_api.basket import price_baskets, store_info
from smartcart_api.embedding import to_pgvector
from smartcart_api.precompute import precompute_effective_prices
from smartcart_catalog import kosher as ck

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]
D = Decimal

TNUVA = 'חלב תנובה 3% 1 ליטר בד"ץ'  # states badatz
BY = 'חלב תנובה 3% 1 ליטר בד"ץ בית יוסף'  # states a named hechsher
EIDA = 'חלב תנובה 3% 1 ליטר בד"ץ העדה החרדית'
MEHADRIN = "חלב טרה 3% 1 ליטר מהדרין"
NOT_KOSHER = "חלב תנובה 3% 1 ליטר לא כשר"
PRIVATE = "חלב 3% מותג הבית 1 ליטר"  # states nothing


@pytest.fixture
def w(db, world: World) -> World:
    precompute_effective_prices(db, chains=world.chains)
    return world


def rename(db, w: World, names: dict[str, str]) -> None:
    for key, name in names.items():
        db.execute("UPDATE items SET raw_name = %s WHERE id = %s", (name, w.items[key]))


def add_item(
    db, w: World, key: str, chain: str, raw: str, canon: str, level: str, price: str, unit: str
) -> int:
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit) VALUES (%s, %s, %s, 1, %s)"
        " RETURNING id",
        (chain, key, raw, unit),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, %s, 0.95, 'rule')",
        (iid, w.canon[canon], level),
    )
    db.execute(
        "INSERT INTO item_attributes (item_id, attrs, verified_keys, extractor)"
        " VALUES (%s, %s, '{}', 'rule')",
        (iid, Jsonb({})),
    )
    db.execute(
        "INSERT INTO item_embeddings (item_id, embedding, model) VALUES (%s, %s::vector, %s)",
        (iid, to_pgvector(EMB.embed_one(raw)), EMB.model_name),
    )
    add_price(db, iid, None, price, None, None, w.valid_from)
    w.items[key] = iid
    return iid


def compare(client, w: World, items: list[dict], **kw) -> dict:
    r = client.post("/compare", json={"items": items, "location": w.location, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def milk(w: World, qty: int = 1, flex: str = "any_brand", **kw) -> list[dict]:
    return [{"canonical_id": w.canon["milk3"], "quantity": qty, "flex_level": flex, **kw}]


def stores(resp: dict) -> dict[int, dict]:
    return {s["store_id"]: s for s in resp["stores"]}


def only_line(store: dict) -> dict:
    assert len(store["items"]) == 1
    return store["items"][0]


# --- the filter is off unless it is set ----------------------------------------------------------------


def test_without_a_filter_nothing_changes_and_no_label_is_sent(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": NOT_KOSHER})
    resp = compare(client, w, milk(w))
    a = stores(resp)[w.stores["a"]]
    assert only_line(a)["item_id"] == w.items["milk3_c1_tnuva"]  # the name is not looked at
    assert only_line(a)["kosher"] is None and a["kosher_excluded"] == []
    assert resp["kosher_hidden_stores"] == 0
    for empty in (None, {}, {"level": None, "only_stated": True, "passover": False}):
        got = compare(client, w, milk(w), kosher=empty)
        assert only_line(stores(got)[w.stores["a"]])["kosher"] is None


# --- /compare ------------------------------------------------------------------------------------------


def test_an_item_that_meets_the_level_is_offered_with_its_label(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA})
    a = stores(compare(client, w, milk(w), kosher={"level": "badatz"}))[w.stores["a"]]
    line = only_line(a)
    assert line["item_id"] == w.items["milk3_c1_tnuva"] and D(line["line_total"]) == D("5.90")
    assert line["kosher"] == {"level": "meets", "passover": None, "stated": ["badatz"]}
    assert a["kosher_excluded"] == [] and a["missing"] == []


def test_an_item_that_states_nothing_is_offered_labelled_unknown(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA})
    home = stores(compare(client, w, milk(w), kosher={"level": "badatz"}))[w.stores["home"]]
    line = only_line(home)
    # the cheapest item at the home store is the house brand (6.20), whose name states nothing
    assert line["item_id"] == w.items["milk3_c1_private"] and D(line["line_total"]) == D("6.20")
    assert line["kosher"] == {"level": "unknown", "passover": None, "stated": []}


def test_only_stated_leaves_unknown_out_and_prices_the_next_item_that_meets(
    client, db, w: World
) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA})
    resp = compare(client, w, milk(w), kosher={"level": "badatz", "only_stated": True})
    home = stores(resp)[w.stores["home"]]
    line = only_line(home)
    # the house brand is not enough: the Tnuva item, dearer (6.90), is the line
    assert line["item_id"] == w.items["milk3_c1_tnuva"] and D(line["line_total"]) == D("6.90")
    assert line["kosher"]["level"] == "meets"
    # the c2 store sells only the Tara item, which states nothing: missing, said so, not relaxed
    b = stores(resp)[w.stores["b"]] if w.stores["b"] in stores(resp) else None
    assert b is None  # a store with nothing left is not listed ...
    assert resp["kosher_hidden_stores"] == 1  # ... and the response says how many were left out


def test_an_item_ruled_out_is_never_offered_even_when_it_is_the_cheapest(
    client, db, w: World
) -> None:
    rename(db, w, {"milk3_c1_tnuva": BY})
    resp = compare(client, w, milk(w), kosher={"level": "badatz_eida"})
    a = stores(resp)[w.stores["a"]]
    # at store A Tnuva is 5.90, the cheapest, but it states a different hechsher: the house brand
    # (6.20, states nothing) is offered instead, labelled unknown
    line = only_line(a)
    assert line["item_id"] == w.items["milk3_c1_private"] and D(line["line_total"]) == D("6.20")
    assert line["kosher"]["level"] == "unknown"
    everything = [i for s in resp["stores"] for i in s["items"]]
    assert w.items["milk3_c1_tnuva"] not in {i["item_id"] for i in everything}


def test_a_store_that_cannot_meet_the_basket_says_so(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": BY, "milk3_c1_private": NOT_KOSHER})
    resp = compare(
        client,
        w,
        milk(w) + [{"canonical_id": w.canon["bread"], "quantity": 1}],
        kosher={"level": "badatz_eida"},
        home_store_id=w.stores["home"],
    )
    home = stores(resp)[w.stores["home"]]
    assert home["missing"] == [w.canon["milk3"]] and home["kosher_excluded"] == [w.canon["milk3"]]
    assert [i["canonical_id"] for i in home["items"]] == [w.canon["bread"]]
    # not stocked at all is missing but not "excluded by the filter": the salmon of store B
    salmon = compare(
        client,
        w,
        [{"canonical_id": w.canon["salmon"], "quantity": 1}],
        kosher={"level": "regular"},
    )
    assert all(s["kosher_excluded"] == [] for s in salmon["stores"])


def test_no_line_ever_has_an_item_the_name_rules_out(client, db, w: World) -> None:
    rename(
        db,
        w,
        {
            "milk3_c1_tnuva": EIDA,
            "milk3_c1_private": NOT_KOSHER,
            "milk3_c2": MEHADRIN,
            "bread_c1": "לחם אחיד פרוס 750 גרם לא כשר",
        },
    )
    items = milk(w) + [{"canonical_id": w.canon["bread"], "quantity": 3}]
    for level in ck.LEVELS:
        for only in (False, True):
            resp = compare(client, w, items, kosher={"level": level, "only_stated": only})
            for s in resp["stores"]:
                for line in s["items"]:
                    name = db.execute(
                        "SELECT raw_name FROM items WHERE id = %s", (line["item_id"],)
                    ).fetchone()[0]
                    assert ck.judge(ck.read_item_name(name), level) != "fails", (level, name)
                    if only:
                        assert line["kosher"]["level"] == "meets", (level, name)


def test_a_filter_every_item_passes_changes_no_price(client, db, w: World) -> None:
    """Where every item states what the level needs, the filter only adds labels: the same items
    at the same prices, store by store."""
    for key in ("milk3_c1_tnuva", "milk3_c1_private", "milk3_c2", "bread_c1", "bread_c2"):
        (name,) = db.execute("SELECT raw_name FROM items WHERE id = %s", (w.items[key],)).fetchone()
        rename(db, w, {key: f"{name} מהדרין"})
    items = [*milk(w, 2), {"canonical_id": w.canon["bread"], "quantity": 3}]
    plain = compare(client, w, items, home_store_id=w.stores["home"])
    strict = compare(
        client,
        w,
        items,
        home_store_id=w.stores["home"],
        kosher={"level": "mehadrin", "only_stated": True},
    )
    assert [s["store_id"] for s in strict["stores"]] == [s["store_id"] for s in plain["stores"]]
    for p, q in zip(plain["stores"], strict["stores"], strict=True):
        assert p["total"] == q["total"] and p["saving_vs_home"] == q["saving_vs_home"]
        assert [(i["item_id"], i["line_total"]) for i in p["items"]] == [
            (i["item_id"], i["line_total"]) for i in q["items"]
        ]
        assert all(i["kosher"]["level"] == "meets" for i in q["items"])


def test_the_saving_versus_home_uses_the_same_filter(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA})
    resp = compare(
        client,
        w,
        milk(w, 2),
        kosher={"level": "badatz", "only_stated": True},
        home_store_id=w.stores["home"],
    )
    # home: Tnuva 6.90 x 2 = 13.80; A: Tnuva 5.90 x 2 = 11.80
    assert D(resp["home_store_total"]) == D("13.80")
    assert D(stores(resp)[w.stores["a"]]["saving_vs_home"]) == D("2.00")


def test_a_substitute_keeps_all_its_labels_and_gets_the_kosher_label_too(
    client, db, w: World
) -> None:
    rename(db, w, {"salmon_c2_frozen": "פילה סלמון קפוא 400 גרם מהדרין"})
    resp = compare(
        client,
        w,
        [{"canonical_id": w.canon["salmon"], "quantity": 1, "flex_level": "close"}],
        kosher={"level": "mehadrin"},
    )
    line = only_line(stores(resp)[w.stores["b"]])
    assert line["is_substitute"] and line["confidence"] is not None and line["tags"]
    assert {t["key"] for t in line["tags"]} >= {"state"}
    assert line["kosher"] == {"level": "meets", "passover": None, "stated": ["mehadrin"]}


def test_a_cheaper_item_is_found_when_the_best_one_is_ruled_out_and_clubs_still_apply(
    client, db, w: World
) -> None:
    # c1 eggs: the api_world item has a club deal (9.90 for members) and states nothing. A second
    # c1 item states badatz at 15.00. Under only_stated the member still cannot get the 9.90 deal.
    add_item(
        db,
        w,
        "eggs_c1_badatz",
        "t-c1",
        "ביצים L 12 יח' בד\"ץ",
        "eggs",
        "any_brand",
        "15.00",
        "יחידה",
    )
    precompute_effective_prices(db, chains=w.chains)
    items = [{"canonical_id": w.canon["eggs"], "quantity": 1}]
    home = w.stores["home"]
    plain = stores(compare(client, w, items, clubs=["מועדון לקוחות"]))[home]
    assert D(only_line(plain)["line_total"]) == D("9.90")
    got = stores(
        compare(
            client,
            w,
            items,
            clubs=["מועדון לקוחות"],
            kosher={"level": "badatz", "only_stated": True},
        )
    )[home]
    line = only_line(got)
    assert line["item_id"] == w.items["eggs_c1_badatz"] and D(line["line_total"]) == D("15.00")
    assert line["kosher"]["level"] == "meets" and not line["club_required"]


def test_a_club_deal_on_an_item_that_passes_is_kept(client, db, w: World) -> None:
    rename(db, w, {"eggs_c1": 'ביצים L תריסר בד"ץ'})
    items = [{"canonical_id": w.canon["eggs"], "quantity": 1}]
    got = stores(compare(client, w, items, clubs=["מועדון לקוחות"], kosher={"level": "badatz"}))[
        w.stores["home"]
    ]
    line = only_line(got)
    assert D(line["line_total"]) == D("9.90") and line["club_required"]
    assert line["kosher"]["level"] == "meets"


def test_the_exact_barcode_is_ruled_out_by_its_name_too(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": BY})
    items = milk(w, flex="exact", exact_item_id=w.items["milk3_c1_tnuva"])
    plain = compare(client, w, items)
    assert {w.stores["home"], w.stores["a"]} <= set(stores(plain))
    got = compare(client, w, items, kosher={"level": "badatz_eida"})
    assert got["stores"] == []  # no store sells this barcode in a form the level allows
    ok = compare(client, w, items, kosher={"level": "badatz_beit_yosef"})
    assert {w.stores["home"], w.stores["a"]} <= set(stores(ok))
    assert only_line(stores(ok)[w.stores["a"]])["kosher"]["level"] == "meets"


def test_kosher_for_passover_is_a_filter_of_its_own(client, db, w: World) -> None:
    rename(
        db,
        w,
        {
            "milk3_c1_tnuva": "חלב תנובה 3% 1 ליטר כשר לפסח",
            "milk3_c1_private": "חלב 3% מותג הבית 1 ליטר לא כשר לפסח",
        },
    )
    resp = compare(client, w, milk(w), kosher={"passover": True})
    home = only_line(stores(resp)[w.stores["home"]])
    # the house brand says it is not kosher for Passover: never offered, whatever it costs
    assert home["item_id"] == w.items["milk3_c1_tnuva"] and D(home["line_total"]) == D("6.90")
    assert home["kosher"] == {"level": None, "passover": "meets", "stated": ["passover"]}
    b = only_line(stores(resp)[w.stores["b"]])  # the Tara item states nothing: unknown
    assert b["kosher"]["passover"] == "unknown"
    strict = compare(client, w, milk(w), kosher={"passover": True, "only_stated": True})
    assert w.stores["b"] not in stores(strict)
    both = compare(client, w, milk(w), kosher={"level": "badatz", "passover": True})
    assert only_line(stores(both)[w.stores["home"]])["kosher"]["level"] == "unknown"


def test_a_value_a_model_extracted_is_not_trusted_but_a_verified_one_is(
    client, db, w: World
) -> None:
    f = schemas.KosherFilter(level="badatz")
    iid = w.items["milk3_c2"]
    db.execute(
        "UPDATE item_attributes SET attrs = attrs || %s WHERE item_id = %s",
        (Jsonb({"kosher": 'בד"ץ'}), iid),
    )
    assert kosher_mod.assess_items(db, {iid}, f)[iid].level == "unknown"  # unverified: ignored
    db.execute("UPDATE item_attributes SET verified_keys = '{kosher}' WHERE item_id = %s", (iid,))
    assert kosher_mod.assess_items(db, {iid}, f)[iid].level == "meets"


# --- price_baskets directly ------------------------------------------------------------------------


def test_price_baskets_without_a_filter_is_unchanged_by_the_new_argument(db, w: World) -> None:
    loc = schemas.Location(lon=w.location["lon"], lat=w.location["lat"])
    info = store_info(db, w.stores["a"], loc)
    items = [schemas.BasketItem(canonical_id=w.canon["milk3"], quantity=1)]
    one = price_baskets(db, items, [info], [])[info.store_id]
    two = price_baskets(db, items, [info], [], kosher=schemas.KosherFilter())[info.store_id]
    assert one.lines[w.canon["milk3"]] == two.lines[w.canon["milk3"]]
    assert one.kosher_blocked == two.kosher_blocked == []


# --- /optimize -----------------------------------------------------------------------------------------


def optimize(client, w: World, items: list[dict], **kw) -> dict:
    body = {"items": items, "location": w.location, "home_store_id": w.stores["home"], **kw}
    r = client.post("/optimize", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("solver", ["heuristic", "milp"])
def test_optimize_never_plans_an_item_the_filter_rules_out(client, db, w: World, solver) -> None:
    rename(db, w, {"milk3_c1_tnuva": BY})
    items = milk(w, 2) + [{"canonical_id": w.canon["bread"], "quantity": 3}]
    plain = optimize(client, w, items, solver=solver)
    got = optimize(client, w, items, solver=solver, kosher={"level": "badatz_eida"})
    ids = {
        item["item_id"]
        for plan in (got["single"], got["split"], got["minimum_effort"])
        if plan
        for a in plan["stores"]
        for item in a["store"]["items"]
    }
    assert w.items["milk3_c1_tnuva"] not in ids and ids
    assert all(
        item["kosher"] is not None
        for plan in (got["single"], got["split"])
        if plan
        for a in plan["stores"]
        for item in a["store"]["items"]
    )
    assert plain["single"]["kosher_excluded"] == []


@pytest.mark.parametrize("solver", ["heuristic", "milp"])
def test_optimize_says_what_the_filter_took_away(client, db, w: World, solver) -> None:
    rename(db, w, {"milk3_c1_tnuva": BY, "milk3_c1_private": NOT_KOSHER, "milk3_c2": NOT_KOSHER})
    items = milk(w) + [{"canonical_id": w.canon["bread"], "quantity": 1}]
    got = optimize(client, w, items, solver=solver, kosher={"level": "badatz_eida"})
    single = got["single"]
    assert single["missing"] == [w.canon["milk3"]]
    assert single["kosher_excluded"] == [w.canon["milk3"]]  # sold, but only in ruled-out items
    assert got["minimum_effort"]["kosher_excluded"] == [w.canon["milk3"]]


# --- /optimize/swaps -----------------------------------------------------------------------------------


def swaps(client, w: World, items: list[dict], store: str = "home", **kw) -> dict:
    r = client.post(
        f"/optimize/swaps?store_id={w.stores[store]}",
        json={"items": items, "location": w.location, **kw},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_swaps_never_suggest_an_item_the_filter_rules_out(client, db, w: World) -> None:
    # exact Tnuva at the home store costs 6.90; the house brand (6.20) is the cheaper any-brand swap
    items = milk(w, flex="exact", exact_item_id=w.items["milk3_c1_tnuva"])
    plain = swaps(client, w, items)
    assert [s["to_item_id"] for s in plain["swaps"]] == [w.items["milk3_c1_private"]]
    rename(db, w, {"milk3_c1_private": NOT_KOSHER})
    got = swaps(client, w, items, kosher={"level": "regular"})
    assert got["swaps"] == []  # the cheaper item states it is not kosher


def test_a_swap_from_a_stated_certification_to_an_unstated_one_is_not_suggested(
    client, db, w: World
) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA})
    items = milk(w, flex="exact", exact_item_id=w.items["milk3_c1_tnuva"])
    assert swaps(client, w, items)["swaps"]  # without the filter the house brand is a swap
    got = swaps(client, w, items, kosher={"level": "badatz"})
    assert got["swaps"] == []  # it states nothing: cheaper is not a reason to give up a hechsher


def test_a_swap_to_an_item_that_also_meets_the_level_carries_its_label(
    client, db, w: World
) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA, "milk3_c1_private": "חלב 3% מותג הבית 1 ליטר מהדרין"})
    items = milk(w, flex="exact", exact_item_id=w.items["milk3_c1_tnuva"])
    got = swaps(client, w, items, kosher={"level": "mehadrin"})
    (swap,) = got["swaps"]
    assert swap["to_item_id"] == w.items["milk3_c1_private"]
    assert swap["kosher"] == {"level": "meets", "passover": None, "stated": ["mehadrin"]}


# --- /search -------------------------------------------------------------------------------------------


def search(client, q: str, **params) -> dict:
    r = client.get("/search", params={"q": q, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_search_without_a_filter_has_no_kosher_field_set(client, w: World) -> None:
    hits = search(client, "חלב 3%")["hits"]
    assert hits and all(h["kosher"] is None for h in hits)


def test_search_labels_each_hit_from_the_items_behind_it(client, db, w: World) -> None:
    rename(db, w, {"milk3_c1_tnuva": TNUVA})
    hits = {
        h["canonical"]["canonical_id"]: h for h in search(client, "חלב 3%", kosher="badatz")["hits"]
    }
    label = hits[w.canon["milk3"]]["kosher"]
    # exact + any brand items of the canonical: Tnuva states badatz; house brand and Tara do not
    assert label == {"status": "meets", "meets": 1, "unknown": 2, "fails": 0}
    strict = search(client, "חלב 3%", kosher="badatz", kosher_only_stated="true")["hits"]
    assert (
        next(h for h in strict if h["canonical"]["canonical_id"] == w.canon["milk3"])["kosher"][
            "status"
        ]
        == "meets"
    )


def test_a_hit_with_nothing_to_offer_is_listed_after_the_others(client, db, w: World) -> None:
    plain = [h["canonical"]["canonical_id"] for h in search(client, "חלב")["hits"]]
    assert w.canon["milk3"] in plain and len(plain) >= 2
    first = plain[0]
    rename(
        db,
        w,
        {
            "milk3_c1_tnuva": NOT_KOSHER,
            "milk3_c1_private": NOT_KOSHER,
            "milk3_c2": NOT_KOSHER,
            "milk1_c1": 'חלב 1% תנובה 1 ליטר בד"ץ',
        },
    )
    got = search(client, "חלב", kosher="regular")["hits"]
    ids = [h["canonical"]["canonical_id"] for h in got]
    assert set(ids) == set(plain)  # nothing is hidden: a hit is a canonical, not an item
    last = {h["canonical"]["canonical_id"]: h["kosher"] for h in got}
    assert last[w.canon["milk3"]] == {"status": "none", "meets": 0, "unknown": 0, "fails": 3}
    assert ids.index(w.canon["milk3"]) > ids.index(w.canon["milk1"])
    if first == w.canon["milk3"]:
        assert ids[0] != first


def test_search_rejects_an_unknown_level(client, w: World) -> None:
    r = client.get("/search", params={"q": "חלב", "kosher": "super"})
    assert r.status_code == 422


def test_the_request_rejects_an_unknown_level_and_extra_keys(client, w: World) -> None:
    for bad in ({"level": "super"}, {"level": "badatz", "strict": True}):
        r = client.post("/compare", json={"items": milk(w), "location": w.location, "kosher": bad})
        assert r.status_code == 422


# --- the pure parts ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("marks", "level", "only", "passover", "allowed"),
    [
        (set(), "badatz", False, False, True),
        (set(), "badatz", True, False, False),
        ({ck.BADATZ}, "badatz", True, False, True),
        ({ck.NOT_KOSHER}, "regular", False, False, False),
        ({ck.BADATZ_BEIT_YOSEF, ck.BADATZ}, ck.BADATZ_EIDA, False, False, False),
        ({ck.BADATZ}, "badatz", False, True, True),  # Passover unknown, shown
        ({ck.BADATZ}, "badatz", True, True, False),  # Passover unknown, only stated
        ({ck.BADATZ, ck.PASSOVER}, "badatz", True, True, True),
        ({ck.BADATZ, ck.NOT_PASSOVER}, "badatz", False, True, False),
    ],
)
def test_allowed(marks, level, only, passover, allowed) -> None:
    f = schemas.KosherFilter(level=level, only_stated=only, passover=passover)
    assert kosher_mod.allowed(kosher_mod.assess_marks(frozenset(marks), f), f) is allowed


def test_label_is_absent_without_a_filter_and_unknown_for_an_unread_item() -> None:
    assert kosher_mod.label(None, None) is None
    assert kosher_mod.label(None, schemas.KosherFilter()) is None
    got = kosher_mod.label(None, schemas.KosherFilter(level="badatz", passover=True))
    assert got is not None and (got.level, got.passover, got.stated) == ("unknown", "unknown", [])
