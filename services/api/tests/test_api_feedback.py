"""Feedback routes: substitution verdicts and report-a-gap."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from api_world import World, make_token

pytestmark = [pytest.mark.db, pytest.mark.postgis, pytest.mark.pgvector]


def test_not_good_flags_the_mapping_for_review(client, db, world: World) -> None:
    w = world
    body = {"canonical_id": w.canon["salmon"], "substitute_item_id": w.items["salmon_c2_frozen"],
            "verdict": "not_good"}
    r = client.post("/feedback/substitution", json=body)
    assert r.status_code == 200 and r.json()["ok"] and r.json()["id"]
    flagged = db.execute(
        "SELECT needs_review FROM item_canonical WHERE item_id = %s AND canonical_id = %s",
        (w.items["salmon_c2_frozen"], w.canon["salmon"]),
    ).fetchone()[0]
    assert flagged
    row = db.execute("SELECT verdict, user_id FROM substitution_feedback WHERE id = %s",
                     (r.json()["id"],)).fetchone()
    assert row == ("not_good", None)


def test_accepted_does_not_flag_and_records_the_user(client, db, world: World) -> None:
    w = world
    uid = uuid.uuid4()
    body = {"canonical_id": w.canon["milk3"], "substitute_item_id": w.items["milk3_c1_private"],
            "original_item_id": w.items["milk3_c1_tnuva"], "verdict": "accepted"}
    r = client.post("/feedback/substitution", json=body,
                    headers={"Authorization": f"Bearer {make_token(uid)}"})
    assert r.status_code == 200
    assert db.execute("SELECT user_id FROM substitution_feedback WHERE id = %s",
                      (r.json()["id"],)).fetchone()[0] == uid
    assert not db.execute(
        "SELECT bool_or(needs_review) FROM item_canonical WHERE item_id = %s",
        (w.items["milk3_c1_private"],),
    ).fetchone()[0]


def test_gap_report(client, db, world: World) -> None:
    w = world
    body = {"store_id": w.stores["home"], "item_id": w.items["paste_c1"], "shown_price": "3.50",
            "actual_price": "3.90", "note": "המחיר במדף שונה"}
    r = client.post("/feedback/gap", json=body)
    assert r.status_code == 200
    row = db.execute("SELECT store_id, shown_price, actual_price, note FROM gap_reports WHERE id = %s",
                     (r.json()["id"],)).fetchone()
    assert row == (w.stores["home"], Decimal("3.50"), Decimal("3.90"), "המחיר במדף שונה")


def test_unknown_ids_are_rejected_without_breaking_the_request(client, world: World) -> None:
    r = client.post("/feedback/gap", json={"store_id": 999_999_999})
    assert r.status_code == 422
    r = client.post("/feedback/substitution",
                    json={"canonical_id": 999_999_999, "substitute_item_id": 1, "verdict": "accepted"})
    assert r.status_code == 422
    assert client.post("/feedback/gap", json={"store_id": world.stores["a"]}).status_code == 200


SWAP_VERDICTS = {"apply": "accepted", "undo": "kept_original", "dismiss": "not_good"}


@pytest.mark.parametrize("action", sorted(SWAP_VERDICTS))
def test_swap_verdicts_round_trip_through_the_catalog(client, db, world: World, action) -> None:
    """A smart-cart swap action is stored as catalog feedback with its context and source."""
    w = world
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    list_id = db.execute("INSERT INTO lists (user_id, name) VALUES (%s, 'x') RETURNING id",
                         (uid,)).fetchone()[0]
    line = db.execute("INSERT INTO list_items (list_id, user_id, canonical_id) VALUES (%s, %s, %s)"
                      " RETURNING id", (list_id, uid, w.canon["milk3"])).fetchone()[0]
    body = {"canonical_id": w.canon["milk3"], "original_item_id": w.items["milk3_c1_tnuva"],
            "substitute_item_id": w.items["milk3_c1_private"], "verdict": SWAP_VERDICTS[action],
            "source": "swap", "list_item_id": line, "flex_level": "any_brand",
            "match_confidence": 0.95}
    r = client.post("/feedback/substitution", json=body,
                    headers={"Authorization": f"Bearer {make_token(uid)}"})
    assert r.status_code == 200, r.text
    row = db.execute(
        "SELECT verdict, source, list_item_id, flex_level, match_confidence, user_id,"
        " original_item_id, substitute_item_id FROM substitution_feedback WHERE id = %s",
        (r.json()["id"],),
    ).fetchone()
    assert row == (SWAP_VERDICTS[action], "swap", line, "any_brand", Decimal("0.95"), uid,
                   w.items["milk3_c1_tnuva"], w.items["milk3_c1_private"])
    flagged = db.execute(
        "SELECT needs_review FROM item_canonical WHERE item_id = %s AND canonical_id = %s",
        (w.items["milk3_c1_private"], w.canon["milk3"]),
    ).fetchone()[0]
    assert flagged is (action == "dismiss")  # dismiss = not_good puts the mapping in review


def test_swap_verdicts_count_in_the_catalog_rejection_rates(client, db, world: World) -> None:
    from smartcart_catalog.feedback import rejection_rates

    w = world
    base = {"canonical_id": w.canon["paste"], "substitute_item_id": w.items["paste_c1"]}
    for verdict, source in (("not_good", "swap"), ("accepted", "swap"),
                            ("accepted", "substitution_card")):
        payload = {**base, "verdict": verdict, "source": source}
        assert client.post("/feedback/substitution", json=payload).status_code == 200
    sources = db.execute(
        "SELECT source, count(*) FROM substitution_feedback GROUP BY 1 ORDER BY 1").fetchall()
    assert sources == [("substitution_card", 1), ("swap", 2)]
    paste = [r for r in rejection_rates(db) if r["category"] == "t.pantry"]
    assert sum(r["reports"] for r in paste) == 3 and sum(r["not_good"] for r in paste) == 1


def test_substitution_card_is_the_default_source(client, db, world: World) -> None:
    w = world
    body = {"canonical_id": w.canon["salmon"], "substitute_item_id": w.items["salmon_c2_frozen"],
            "verdict": "kept_original", "flex_level": "close", "match_confidence": 0.81}
    r = client.post("/feedback/substitution", json=body)
    assert r.status_code == 200
    row = db.execute("SELECT source, flex_level, match_confidence, list_item_id"
                     " FROM substitution_feedback WHERE id = %s", (r.json()["id"],)).fetchone()
    assert row == ("substitution_card", "close", Decimal("0.81"), None)
    assert client.post("/feedback/substitution",
                       json={**body, "source": "banner"}).status_code == 422
