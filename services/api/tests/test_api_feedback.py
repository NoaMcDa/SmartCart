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
