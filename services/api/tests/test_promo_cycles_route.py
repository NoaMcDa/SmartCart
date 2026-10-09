"""GET /promo-cycles/{canonical_id} (issue #69) on synthetic promo history."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from api_world import World

from smartcart_catalog import promo_cycles as pc

pytestmark = [pytest.mark.db, pytest.mark.postgis]


def every(period: int, n: int, first: date, length: int = 5) -> list[pc.Window]:
    return [
        pc.Window(
            first + timedelta(days=i * period), first + timedelta(days=i * period + length - 1)
        )
        for i in range(n)
    ]


def test_promo_cycles_per_chain(client, db, world: World) -> None:
    today = datetime.now(UTC).date()
    milk = world.canon["milk3"]
    # chain 1: every 4 weeks, the last one ended 20 days ago, so the next is 1 to 13 days away
    first = today - timedelta(days=28 * 5 + 24)
    pc.seed_promo_history(
        db,
        "t-c1",
        [world.items["milk3_c1_tnuva"], world.items["milk3_c1_private"]],
        every(28, 6, first),
        prefix="M1",
    )
    # chain 2: only two promos
    pc.seed_promo_history(
        db, "t-c2", [world.items["milk3_c2"]], every(40, 2, today - timedelta(days=60)), prefix="M2"
    )
    r = client.get(f"/promo-cycles/{milk}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canonical_id"] == milk
    c1, c2 = body["chains"]
    assert set(c1) == {
        "chain_id",
        "chain_name",
        "cycles_seen",
        "median_gap_days",
        "confidence",
        "last_promo_ends",
        "next_expected_from",
        "next_expected_to",
        "advice",
    }
    assert (c1["chain_id"], c1["chain_name"], c1["cycles_seen"], c1["median_gap_days"]) == (
        "t-c1",
        "רשת אחת",
        5,
        28.0,
    )
    assert c1["confidence"] == round(5 / 6.5, 3) and c1["advice"] == "wait"
    assert c1["last_promo_ends"] == (first + timedelta(days=28 * 5 + 4)).isoformat()
    nxt = first + timedelta(days=28 * 6)
    assert c1["next_expected_from"] == (nxt - timedelta(days=3)).isoformat()
    assert c1["next_expected_to"] == (nxt + timedelta(days=4 + 3)).isoformat()
    assert c2["chain_id"] == "t-c2" and c2["cycles_seen"] == 1 and c2["advice"] == "unknown"
    assert (
        c2["next_expected_from"] is None
        and c2["next_expected_to"] is None
        and c2["confidence"] == 0.0
    )


def test_no_history_and_unknown_canonical(client, world: World) -> None:
    assert client.get(f"/promo-cycles/{world.canon['bread']}").json()["chains"] == []
    assert client.get("/promo-cycles/987654321").status_code == 404


def test_club_promos_need_the_club(client, db, world: World) -> None:
    today = datetime.now(UTC).date()
    eggs = world.canon["eggs"]
    pc.seed_promo_history(
        db,
        "t-c1",
        [world.items["eggs_c1"]],
        every(30, 6, today - timedelta(days=30 * 5 + 10)),
        prefix="E",
        club_only=True,
        club_name="מועדון לקוחות",
    )
    # The fixture's own club promo on eggs (P3) has no dates and never counts.
    assert client.get(f"/promo-cycles/{eggs}").json()["chains"] == []
    # The chain's own club, marked by the chain's name, as the web app sends it.
    got = client.get(f"/promo-cycles/{eggs}", params={"clubs": ["רשת אחת"]}).json()["chains"]
    assert len(got) == 1 and got[0]["cycles_seen"] == 5
    assert (
        client.get(f"/promo-cycles/{eggs}", params={"clubs": ["מועדון אחר"]}).json()["chains"] == []
    )
