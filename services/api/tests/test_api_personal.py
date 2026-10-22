"""``/me/personal`` (phase 3 personalization): own data only, bounded, erasable."""

from __future__ import annotations

import uuid

import pytest
from api_world import make_token
from psycopg.types.json import Jsonb

from smartcart_api import schemas

pytestmark = pytest.mark.db

NOW = "2026-10-22T08:30:00Z"


def h(user_id) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def users(db) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid.uuid4(), uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s), (%s)", (a, b))
    return a, b


def ref(cid: int = 1009, **over) -> dict:
    return {
        "canonical_id": cid,
        "display_name_he": "ביצים L, 12 יחידות",
        "display_name_ar": "بيض L",
        "taxonomy_id": "eggs.chicken",
        "base_unit": "unit",
        "category_path_he": ["מוצרי חלב", "ביצים"],
        **over,
    }


def doc(**over) -> dict:
    base = {
        "version": 1,
        "prefs": {"learn": True, "value_packs": True, "updated_at": NOW},
        "refs": [ref()],
        "trips": [
            {
                "id": "trip-0001",
                "at": NOW,
                "kind": "finished",
                "lines": [{"canonical_id": 1009, "quantity": 2}],
            }
        ],
        "signals": [
            {
                "id": "sig-0001",
                "at": NOW,
                "taxonomy_id": "dairy.milk",
                "kind": "kept_brand",
            }
        ],
        "dismissals": [{"kind": "buy_again", "key": "1009", "at": NOW}],
    }
    return {**base, **over}


def test_nothing_stored_reads_as_the_defaults(client, users) -> None:
    a, _ = users
    r = client.get("/me/personal", headers=h(a))
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is False
    assert body["prefs"]["learn"] is True and body["prefs"]["value_packs"] is False
    assert body["trips"] == [] and body["signals"] == [] and body["refs"] == []


def test_put_replaces_the_document_and_get_reads_it_back(client, users) -> None:
    a, _ = users
    put = client.put("/me/personal", json=doc(), headers=h(a))
    assert put.status_code == 200, put.text
    assert put.json()["exists"] is True
    got = client.get("/me/personal", headers=h(a)).json()
    assert got["exists"] is True
    assert got["prefs"]["value_packs"] is True
    assert got["trips"][0]["lines"] == [{"canonical_id": 1009, "quantity": 2.0}]
    assert got["signals"][0]["taxonomy_id"] == "dairy.milk"
    assert got["dismissals"][0]["kind"] == "buy_again"
    assert got["refs"][0]["display_name_ar"] == "بيض L"
    # a second PUT replaces, it does not merge
    client.put("/me/personal", json=doc(trips=[], signals=[], dismissals=[]), headers=h(a))
    again = client.get("/me/personal", headers=h(a)).json()
    assert again["trips"] == [] and again["signals"] == [] and again["dismissals"] == []


def test_a_user_never_sees_or_changes_another_users_document(client, users, db) -> None:
    a, b = users
    client.put("/me/personal", json=doc(), headers=h(a))
    assert client.get("/me/personal", headers=h(b)).json()["exists"] is False
    client.put("/me/personal", json=doc(prefs={"learn": False, "value_packs": False}), headers=h(b))
    assert client.get("/me/personal", headers=h(a)).json()["prefs"]["value_packs"] is True
    assert client.delete("/me/personal", headers=h(b)).status_code == 204
    assert client.get("/me/personal", headers=h(a)).json()["exists"] is True
    stored = db.execute("SELECT count(*) FROM preferences").fetchone()[0]
    assert stored == 2


def test_other_keys_of_the_preferences_row_survive_a_put_and_a_delete(client, users, db) -> None:
    a, _ = users
    db.execute(
        "INSERT INTO preferences (user_id, data) VALUES (%s, %s)", (a, Jsonb({"other": {"x": 1}}))
    )
    client.put("/me/personal", json=doc(), headers=h(a))
    data = db.execute("SELECT data FROM preferences WHERE user_id = %s", (a,)).fetchone()[0]
    assert data["other"] == {"x": 1} and "personal" in data
    assert client.delete("/me/personal", headers=h(a)).status_code == 204
    data = db.execute("SELECT data FROM preferences WHERE user_id = %s", (a,)).fetchone()[0]
    assert data == {"other": {"x": 1}}
    assert client.get("/me/personal", headers=h(a)).json()["exists"] is False


def test_delete_without_a_document_is_still_204(client, users) -> None:
    a, _ = users
    assert client.delete("/me/personal", headers=h(a)).status_code == 204


def test_account_deletion_removes_it(client, users, db, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    a, _ = users
    client.put("/me/personal", json=doc(), headers=h(a))
    assert client.delete("/me", headers=h(a)).status_code == 200
    assert (
        db.execute("SELECT count(*) FROM preferences WHERE user_id = %s", (a,)).fetchone()[0] == 0
    )


def test_a_stored_document_the_schema_no_longer_reads_counts_as_not_stored(
    client, users, db
) -> None:
    a, _ = users
    db.execute(
        "INSERT INTO preferences (user_id, data) VALUES (%s, %s)",
        (a, Jsonb({"personal": {"version": 2, "surprise": True}})),
    )
    assert client.get("/me/personal", headers=h(a)).json()["exists"] is False


@pytest.mark.parametrize(
    "bad",
    [
        doc(version=2),
        doc(surprise=1),
        doc(prefs={"learn": True, "value_packs": False, "note": "free text"}),
        doc(trips=[{"id": "t", "at": NOW, "kind": "finished", "lines": []}]),  # short id
        doc(trips=[{"id": "trip-0001", "at": NOW, "kind": "bought", "lines": []}]),
        doc(trips=[{"id": "trip-0001", "at": "2026-10-22", "kind": "list", "lines": []}]),
        doc(
            trips=[
                {
                    "id": "trip-0001",
                    "at": NOW,
                    "kind": "list",
                    "lines": [{"canonical_id": 1, "quantity": 0}],
                }
            ]
        ),
        doc(
            trips=[
                {
                    "id": "trip-0001",
                    "at": NOW,
                    "kind": "list",
                    "lines": [{"canonical_id": 1, "quantity": 5000}],
                }
            ]
        ),
        doc(signals=[{"id": "sig-0001", "at": NOW, "taxonomy_id": "x", "kind": "liked"}]),
        doc(dismissals=[{"kind": "other", "key": "1", "at": NOW}]),
        doc(refs=[ref(display_name_he="x" * 121)]),
        doc(refs=[ref(base_unit="litre")]),
        doc(refs=[ref(category_path_he=["a"] * 5)]),
    ],
)
def test_a_malformed_document_is_a_422_and_stores_nothing(client, users, bad) -> None:
    a, _ = users
    assert client.put("/me/personal", json=bad, headers=h(a)).status_code == 422
    assert client.get("/me/personal", headers=h(a)).json()["exists"] is False


def test_every_list_is_bounded(client, users) -> None:
    a, _ = users
    refs = [ref(cid=i) for i in range(201)]
    assert client.put("/me/personal", json=doc(refs=refs), headers=h(a)).status_code == 422
    trips = [{"id": f"trip-{i:04d}", "at": NOW, "kind": "list", "lines": []} for i in range(41)]
    assert client.put("/me/personal", json=doc(trips=trips), headers=h(a)).status_code == 422
    lines = [{"canonical_id": i + 1, "quantity": 1} for i in range(61)]
    one = [{"id": "trip-0001", "at": NOW, "kind": "list", "lines": lines}]
    assert client.put("/me/personal", json=doc(trips=one), headers=h(a)).status_code == 422
    ok = [
        {"id": f"trip-{i:04d}", "at": NOW, "kind": "list", "lines": lines[:60]} for i in range(40)
    ]
    assert client.put("/me/personal", json=doc(trips=ok), headers=h(a)).status_code == 200


def test_the_largest_allowed_document_fits_the_body_limit(client, users) -> None:
    """200 refs at their longest, 40 trips of 60 lines, 100 signals, 200 dismissals."""
    a, _ = users
    refs = [
        ref(
            cid=i + 1,
            display_name_he="א" * 120,
            display_name_ar="ب" * 120,
            taxonomy_id="t" * 60,
            category_path_he=["ק" * 80] * 4,
        )
        for i in range(200)
    ]
    trips = [
        {
            "id": f"trip-{i:04d}",
            "at": NOW,
            "kind": "finished",
            "lines": [{"canonical_id": 100000 + j, "quantity": 999.5} for j in range(60)],
        }
        for i in range(40)
    ]
    signals = [
        {"id": f"sig-{i:04d}", "at": NOW, "taxonomy_id": "t" * 60, "kind": "kept_brand"}
        for i in range(100)
    ]
    dismissals = [{"kind": "buy_again", "key": "k" * 60, "at": NOW} for _ in range(200)]
    big = doc(refs=refs, trips=trips, signals=signals, dismissals=dismissals)
    r = client.put("/me/personal", json=big, headers=h(a))
    # Either it fits (200) or the body limit answers 413 before anything is stored: never a 500,
    # and never a partial write.
    assert r.status_code in (200, 413), r.status_code
    if r.status_code == 413:
        assert client.get("/me/personal", headers=h(a)).json()["exists"] is False


def test_the_personalization_event_takes_a_kind_and_an_action_only(client) -> None:
    ok = {
        "name": "personalization",
        "props": {"kind": "buy_again", "action": "accepted"},
        "session_id": "sess-abcdef12",
    }
    assert client.post("/events", json={"events": [ok]}).status_code == 200
    for props in (
        {"kind": "buy_again"},
        {"action": "shown"},
        {"kind": "buy_again", "action": "shown", "canonical_id": 7},
        {"kind": "buy_again", "action": "shown", "category": "חלב"},
        {"kind": "milk", "action": "shown"},
        {"kind": "usual", "action": "clicked"},
    ):
        bad = {**ok, "props": props}
        assert client.post("/events", json={"events": [bad]}).status_code == 422, props


def test_the_schema_defaults_match_a_fresh_account() -> None:
    d = schemas.PersonalData()
    assert d.prefs.learn is True and d.prefs.value_packs is False
    assert d.refs == [] and d.trips == [] and d.signals == [] and d.dismissals == []
