"""Club promotions of the real chains reach their members (docs/adapters.md, "Club promotions").

The ClubID texts are the real ones of the 2026-10-21 PromoFull files. Each promo's ``club_name`` is
what the ingest stores for that text (``resolve_clubs`` with the chain), so these tests run the
whole path: real text -> stored rule -> precompute -> /compare for a person who holds club ids.
A member sees the club price, a non-member never does, "everyone" is for everyone, an expression
matches either side (or needs one of each for an AND) and an unknown text matches nobody.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import ORIGIN, World, add_price, add_promo, add_store

from smartcart_api.basket import ChainClubNames, chain_club_names, club_member
from smartcart_api.precompute import precompute_effective_prices
from smartcart_ingest.adapters._common import resolve_clubs

D = Decimal
RAMI, TIV, MEGA = "7290058140886", "7290873255550", "7290055700007"
RAMI_AND = (
    "((1=מועדון שיווק   השקמה|1=מועדון לקוחות אשראי))"
    "&(3=ישראכרט מגנטי|3=תווי זיכוי מימוש|3=עיגול אגורות)"
)
RAMI_OR = (
    "(1=מועדון חברתי|1=מועדון שיווק   השקמה|1=מועדון לקוחות אשראי|1=מועדון נטען|1=לקוחות ארנק)"
)
MEGA_OR = "(2=מועדון קרפור אשראי|2=מועדון אפליקציה)"
UNKNOWN = "((1=מועדון לא מוכר))&(3=ישראכרט מגנטי)"

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


# --- the matching rule on real club names -----------------------------------------------------


def names(chain_id: str) -> ChainClubNames:
    return chain_club_names(chain_id, [])


def test_a_club_id_of_the_chain_matches_its_label() -> None:
    n = names(TIV)
    assert club_member("המועדון החדש", ["tivtaam:new"], "טיב טעם", n)
    assert club_member("המועדון החדש", [" TivTaam:New "], "טיב טעם", n)  # ids ignore case/space
    assert not club_member("המועדון החדש", [], "טיב טעם", n)
    assert not club_member("המועדון החדש", ["mega:app", "ramilevy:club"], "טיב טעם", n)


def test_an_id_works_only_for_its_own_chain() -> None:
    # "מועדון עובדים" is Yohananof's; a Tiv Taam promo of the same name is not unlocked by it.
    assert club_member("מועדון עובדים", ["yohananof:staff"], "יוחננוף", names("7290803800003"))
    assert not club_member("מועדון עובדים", ["yohananof:staff"], "טיב טעם", names(TIV))


def test_expressions_are_evaluated_as_written() -> None:
    n = names(RAMI)
    either = "מועדון קרפור אשראי | מועדון אפליקציה"
    assert club_member(either, ["mega:app"], "קרפור", names(MEGA))
    assert club_member(either, ["mega:credit"], "קרפור", names(MEGA))
    assert not club_member(either, ["mega:app"], "קרפור", names(TIV))  # not Mega's table
    both = "(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)"
    assert not club_member(both, ["ramilevy:club"], "רמי לוי", n)
    assert club_member(both, ["ramilevy:club", "ramilevy:vouchers"], "רמי לוי", n)


def test_unknown_and_unparseable_names_match_nobody() -> None:
    n = names(RAMI)
    everything = [c for c in ("ramilevy:club", "ramilevy:credit", "ramilevy:isracard", "אחר")]
    for bad in ("אחר", "", None, "club 3", "(A", "A &", "אחר | אחר", "(אחר) & מועדון רמי לוי"):
        assert not club_member(bad, everything, "רמי לוי", n), bad


# --- the endpoint -----------------------------------------------------------------------------


def test_chains_clubs_lists_what_the_picker_offers(client) -> None:
    r = client.get("/chains/clubs")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "public, max-age=3600"
    rows = {row["chain_id"]: row for row in r.json()}
    assert {RAMI, TIV, MEGA, "7290058108879", "7290803800003", "7290027600007"} == set(rows)
    ids = [c["id"] for row in rows.values() for c in row["clubs"]]
    assert len(ids) == len(set(ids))
    assert {c["id"]: c["kind"] for c in rows[RAMI]["clubs"]}["ramilevy:isracard"] == "card"
    assert rows[TIV]["clubs"] == [{"id": "tivtaam:new", "label": "המועדון החדש", "kind": "club"}]
    # Shufersal: the two card clubs of its list (a text read as any of, inferred), nothing else
    assert rows["7290027600007"]["clubs"] == [
        {"id": "shufersal:credit", "label": "מועדון לקוחות אשראי", "kind": "card"},
        {"id": "shufersal:staff_credit", "label": "מועדון עובדים אשראי", "kind": "card"},
    ]
    assert {c["id"]: c["kind"] for c in rows[RAMI]["clubs"]}["ramilevy:multipass"] == "card"


# --- the whole path ---------------------------------------------------------------------------


@pytest.fixture
def real(db, catalog: World) -> World:
    """Rami Levy, Tiv Taam and Mega with one store each, and one product per promo."""
    w = catalog
    for chain, name in ((RAMI, "רמי לוי"), (TIV, "טיב טעם"), (MEGA, "קרפור (מגה)")):
        db.execute("INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (chain, name))
    w.chains = (RAMI, TIV)
    w.stores["rami"] = add_store(db, RAMI, "1", 1.0, name="רמי לוי א")
    w.stores["tiv"] = add_store(db, TIV, "1", 2.0, name="טיב טעם א")
    w.stores["mega"] = add_store(db, MEGA, "1", 3.0, name="מגה א")
    db.execute("SELECT ensure_price_partition(%s::date)", (w.valid_from.date(),))
    # (key, canonical, chain, promo price, ClubID values of the promo, store key); the shelf price
    # is 20.00 for every product, per pack (a pack is 12 eggs, 1 loaf, 100 g or 100 ml).
    plan = [
        ("and", "eggs", RAMI, "8.00", [RAMI_AND], "rami"),
        ("or", "bread", RAMI, "9.00", [RAMI_OR], "rami"),
        ("unknown", "cream", RAMI, "5.00", [UNKNOWN], "rami"),
        ("tiv", "wafer", TIV, "6.00", ["1 - המועדון החדש"], "tiv"),
        ("all", "milk3", TIV, "7.00", ["0 - כלל הלקוחות"], "tiv"),
        ("mega", "paste", MEGA, "10.00", [MEGA_OR], "mega"),
    ]
    packs = {  # base unit -> (quantity, unit, uom)
        "unit": ("1", "יחידה", None),
        "100g": ("100", "גרם", "100g"),
        "100ml": ("100", 'מ"ל', "100ml"),
    }
    for n, (key, canon, chain, promo, values, _store) in enumerate(plan):
        base = db.execute(
            "SELECT base_unit FROM canonical_products WHERE id = %s", (w.canon[canon],)
        ).fetchone()[0]
        qty, unit, uom = packs[base]
        iid = db.execute(
            "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (chain, key, f"7291111{n:06d}", f"מוצר {key}", qty, unit),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
            " VALUES (%s, %s, 'any_brand', 1.0, 'rule')",
            (iid, w.canon[canon]),
        )
        add_price(db, iid, None, "20.00", "20.00" if uom else None, uom, w.valid_from)
        club_only, club_name, _ = resolve_clubs(values, chain)
        add_promo(
            db, chain, None, f"P-{key}", [iid], "price", promo,
            club_only=club_only, club_name=club_name, description=f"מבצע {key}",
        )  # fmt: skip
        w.items[key] = iid
    precompute_effective_prices(db, chains=[RAMI, TIV, MEGA])
    return w


def price(client, w: World, canon: str, store: str, clubs: list[str]) -> tuple[D, dict]:
    body = {
        "items": [{"canonical_id": w.canon[canon], "quantity": 1}],
        "location": w.location,
        "clubs": clubs,
    }
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    row = next(s for s in r.json()["stores"] if s["store_id"] == w.stores[store])
    return D(row["total"]), row["items"][0]


def test_the_ingest_stored_rules_the_api_reads(real: World, db) -> None:
    rows = dict(
        db.execute("SELECT promo_id, club_name FROM promos WHERE promo_id LIKE 'P-%'").fetchall()
    )
    assert rows["P-tiv"] == "המועדון החדש"
    assert (
        rows["P-or"]
        == "מועדון חברתי | מועדון רמי לוי | מועדון לקוחות אשראי | מועדון נטען | לקוחות ארנק"
    )
    assert rows["P-unknown"] == "אחר"
    assert (
        db.execute("SELECT club_only FROM promos WHERE promo_id = 'P-all'").fetchone()[0] is False
    )


def test_a_member_sees_the_club_price_and_a_non_member_never_does(client, real: World) -> None:
    total, line = price(client, real, "wafer", "tiv", ["tivtaam:new"])
    assert total == D("6.00") and line["club_required"] and line["club_name"] == "המועדון החדש"
    for clubs in ([], ["mega:app"], ["ramilevy:club", "ramilevy:credit"], ["טיב טעם"], ["אחר"]):
        total, line = price(client, real, "wafer", "tiv", clubs)
        assert total == D("20.00") and not line["club_required"], clubs
    # the non-member still sees what the club would save, apart from the total
    _, line = price(client, real, "wafer", "tiv", [])
    assert line["club_offer_name"] == "המועדון החדש" and D(line["club_offer_discount"]) == D(
        "14.00"
    )


def test_everyone_is_everyone(client, real: World) -> None:
    for clubs in ([], ["tivtaam:new"], ["ramilevy:club"]):
        total, line = price(client, real, "milk3", "tiv", clubs)
        assert total == D("7.00") and not line["club_required"], clubs


def test_an_or_expression_matches_either_side(client, real: World) -> None:
    for club in ("social", "club", "credit", "topup", "wallet"):
        total, line = price(client, real, "bread", "rami", [f"ramilevy:{club}"])
        assert total == D("9.00") and line["club_required"], club
    for clubs in ([], ["ramilevy:isracard"], ["ramilevy:vouchers"], ["tivtaam:new"]):
        assert price(client, real, "bread", "rami", clubs)[0] == D("20.00"), clubs
    assert price(client, real, "paste", "mega", ["mega:app"])[0] == D("10.00")
    assert price(client, real, "paste", "mega", ["mega:credit"])[0] == D("10.00")
    assert price(client, real, "paste", "mega", ["mega:app", "mega:credit"])[0] == D("10.00")
    assert price(client, real, "paste", "mega", ["ramilevy:club"])[0] == D("20.00")


def test_an_and_expression_needs_one_of_each_group(client, real: World) -> None:
    member = ["ramilevy:club", "ramilevy:isracard"]
    assert price(client, real, "eggs", "rami", member)[0] == D("8.00")
    assert price(client, real, "eggs", "rami", ["ramilevy:credit", "ramilevy:vouchers"])[0] == D(
        "8.00"
    )
    for clubs in (
        [],
        ["ramilevy:club"],
        ["ramilevy:isracard"],
        ["ramilevy:club", "ramilevy:social"],
    ):
        assert price(client, real, "eggs", "rami", clubs)[0] == D("20.00"), clubs


def test_an_unknown_text_matches_nobody(client, real: World) -> None:
    every = [c["id"] for row in client.get("/chains/clubs").json() for c in row["clubs"]] + [
        "אחר",
        "מועדון לא מוכר",
        "club 1",
    ]
    total, line = price(client, real, "cream", "rami", every)
    assert total == D("20.00") and not line["club_required"]


def test_other_endpoints_use_the_same_rule(client, real: World) -> None:
    body = {
        "items": [{"canonical_id": real.canon["wafer"], "quantity": 1}],
        "location": {"lon": ORIGIN[0], "lat": ORIGIN[1], "radius_m": 5000},
        "max_stores": 1,
    }
    member = client.post("/optimize", json={**body, "clubs": ["tivtaam:new"]}).json()
    plain = client.post("/optimize", json={**body, "clubs": []}).json()
    assert D(member["single"]["total"]) == D("6.00")
    assert D(plain["single"]["total"]) == D("20.00")
