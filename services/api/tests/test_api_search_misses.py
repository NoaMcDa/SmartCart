"""Search misses (issue #52): what is logged, what never is, retention, and that a failure to log
never breaks the request. No user id and no raw text are stored."""

from __future__ import annotations

from decimal import Decimal

import pytest
from api_world import World, make_token

from smartcart_api.misses import MAX_QUERY_CHARS, clean_query, record_miss


def rows(db) -> list[tuple]:
    return db.execute(
        "SELECT query_norm, source, best_confidence FROM search_misses ORDER BY id"
    ).fetchall()


# --- what may be stored (no database) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "stored"),
    [
        ("חלב 3%", "חלב 3%"),
        ("  עגבניות,  שרי  ", "עגבניות שרי"),
        ("ABC Cola", "abc cola"),
        ('שמן זית 750 מ"ל', "שמנ זית 750 מל"),  # quotes dropped, final letters folded
        ("חלב 1.5 ליטר 6 יחידות", "חלב 1.5 ליטר 6 יחידות"),
    ],
)
def test_normalized_query_is_stored(text: str, stored: str) -> None:
    assert clean_query(text) == stored


@pytest.mark.parametrize(
    "text",
    [
        "050-1234567",  # a phone number
        "050 123 4567",
        "+972 50 123 4567",
        "(03) 555-1234",
        "התקשרו אלי 0501234567 חלב",  # a phone number inside words
        "7290000000017",  # a barcode: digits only
        "1234567",  # seven digits
        "דני@example.com",  # an e-mail address
        "name at gmail dot com www.example.com",
        "https://example.org/x",
        "123456",  # no letter at all
        "!!!",
        "",
        " ",
        "א",  # one letter is not a product
        "ח" * (MAX_QUERY_CHARS + 1),  # not a product name: a pasted sentence
    ],
)
def test_personal_looking_text_is_never_stored(text: str) -> None:
    assert clean_query(text) is None


def test_a_query_of_exactly_the_maximum_is_kept() -> None:
    assert clean_query("ח" * MAX_QUERY_CHARS) == "ח" * MAX_QUERY_CHARS
    assert clean_query(None) is None


# --- the routes --------------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.pgvector
def test_search_with_no_acceptable_hit_is_logged_once_without_the_raw_text(
    client, db, world: World
) -> None:
    r = client.get("/search", params={"q": "  Xqzvbn,  PLORF "})
    assert r.status_code == 200 and r.json()["hits"] == []
    assert rows(db) == [("xqzvbn plorf", "search", None)]
    cols = [
        c[0]
        for c in db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'search_misses'"
        ).fetchall()
    ]
    assert set(cols) == {
        "id",
        "query_norm",
        "source",
        "best_confidence",
        "seen_at",
    }  # no user, no raw text
    # the time is rounded down to the hour
    assert db.execute("SELECT seen_at = date_trunc('hour', seen_at) FROM search_misses").fetchone()[
        0
    ]


@pytest.mark.db
@pytest.mark.pgvector
def test_a_signed_in_search_stores_no_user(client, db, world: World) -> None:
    import uuid

    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    headers = {"Authorization": f"Bearer {make_token(uid)}"}
    assert client.get("/search", params={"q": "qwertyplorf"}, headers=headers).status_code == 200
    assert rows(db) == [("qwertyplorf", "search", None)]
    dump = " ".join(str(c) for r in db.execute("SELECT * FROM search_misses").fetchall() for c in r)
    assert str(uid) not in dump


@pytest.mark.db
@pytest.mark.pgvector
def test_a_search_that_finds_something_logs_nothing(client, db, world: World) -> None:
    for q in ("חלב", "רסק עגבניות", "סלמונ"):
        assert client.get("/search", params={"q": q}).json()["hits"], q
    assert rows(db) == []


@pytest.mark.db
def test_a_weak_hit_below_the_parser_floor_is_a_miss_with_its_confidence(
    client, db, monkeypatch
) -> None:
    from smartcart_api.routes import search as search_route
    from smartcart_api.search import Hit

    def weak(_conn, _q, limit=10, **_kw):
        return [Hit(1, "חלב", "t.dairy.milk", "100ml", 1, confidence=0.2, score=0.4)]

    monkeypatch.setattr(search_route, "hybrid_search", weak)
    assert client.get("/search", params={"q": "זזזזזז חלבון"}).status_code == 200
    assert rows(db) == [("זזזזזז חלבונ", "search", Decimal("0.2"))]

    db.execute("DELETE FROM search_misses")
    monkeypatch.setattr(
        search_route,
        "hybrid_search",
        lambda *_a, **_k: [Hit(1, "חלב", "t.dairy.milk", "100ml", 1, confidence=0.35, score=0.4)],
    )
    assert client.get("/search", params={"q": "זזזזזז חלבון"}).status_code == 200
    assert rows(db) == []  # exactly at the floor is a hit


@pytest.mark.db
@pytest.mark.pgvector
def test_search_never_stores_a_phone_number_or_an_email(client, db, world: World) -> None:
    for q in ("0501234567", "050-123-4567", "me@example.com", "7290000000017"):
        assert client.get("/search", params={"q": q}).status_code == 200
    assert rows(db) == []


@pytest.mark.db
@pytest.mark.pgvector
def test_parse_list_logs_each_not_found_row_and_nothing_else(client, db, world: World) -> None:
    r = client.post("/parse-list", json={"text": "חלב\n2 xqzvbn plorf\nרסק עגבניות\nqwertyplorf"})
    assert r.status_code == 200, r.text
    parsed = r.json()["rows"]
    assert [p["not_found"] for p in parsed] == [False, True, False, True]
    assert rows(db) == [("xqzvbn plorf", "parse_list", None), ("qwertyplorf", "parse_list", None)]


@pytest.mark.db
@pytest.mark.pgvector
def test_parse_recipe_logs_unresolved_ingredients(client, db, world: World) -> None:
    text = 'מצרכים:\n2 ק"ג עגבניות\n3 כפות xqzvbn plorf\n'
    r = client.post("/parse-recipe", json={"text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    assert any("xqzvbn" in line for line in body["unresolved"])
    logged = rows(db)
    assert [s for _, s, _ in logged] == ["parse_recipe"]
    assert "xqzvbn plorf" in logged[0][0]


# --- never breaks the request ------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.pgvector
def test_a_failing_write_does_not_break_search_or_parse_list(client, db, world: World) -> None:
    db.execute(
        "ALTER TABLE search_misses RENAME TO search_misses_gone"
    )  # rolled back with the test
    assert client.get("/search", params={"q": "xqzvbn plorf"}).status_code == 200
    r = client.post("/parse-list", json={"text": "xqzvbn plorf\nחלב"})
    assert r.status_code == 200 and r.json()["rows"][0]["not_found"] is True
    assert record_miss(db, "xqzvbn plorf", "search", None) is False
    # the request transaction is still usable afterwards
    assert db.execute("SELECT 1").fetchone() == (1,)


@pytest.mark.db
def test_record_miss_reports_what_it_did(db) -> None:
    assert record_miss(db, "xqzvbn plorf", "parse_image", 0.2) is True
    assert record_miss(db, "0501234567", "parse_image", None) is False
    assert rows(db) == [("xqzvbn plorf", "parse_image", Decimal("0.2"))]
    assert record_miss(db, "xqzvbn plorf", "parse_image", 7) is True  # clamped into the CHECK range
    assert rows(db)[-1][2] == 1


@pytest.mark.db
def test_source_is_restricted_by_the_table(db) -> None:
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO search_misses (query_norm, source) VALUES ('x', 'voice')")
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            "INSERT INTO search_misses (query_norm, source) VALUES (%s, 'search')", ("x" * 121,)
        )


# --- retention ---------------------------------------------------------------------------------


@pytest.mark.db
def test_inserting_a_miss_deletes_rows_older_than_180_days(db) -> None:
    db.execute(
        "INSERT INTO search_misses (query_norm, source, seen_at) VALUES"
        " ('very old', 'search', now() - interval '200 days'),"
        " ('old', 'search', now() - interval '181 days'),"
        " ('kept', 'search', now() - interval '179 days'),"
        " ('recent', 'search', now() - interval '2 days')"
    )
    assert record_miss(db, "fresh miss", "search", None)
    assert sorted(q for q, _, _ in rows(db)) == ["fresh miss", "kept", "recent"]


@pytest.mark.db
def test_purge_function_counts_and_respects_the_window(db) -> None:
    db.execute(
        "INSERT INTO search_misses (query_norm, source, seen_at) VALUES"
        " ('a', 'search', now() - interval '400 days'),"
        " ('b', 'search', now() - interval '100 days'),"
        " ('c', 'search', now() - interval '10 days')"
    )
    assert db.execute("SELECT purge_search_misses()").fetchone()[0] == 1
    assert db.execute("SELECT purge_search_misses(30)").fetchone()[0] == 1  # the 100 day row
    assert [q for q, _, _ in rows(db)] == ["c"]
    assert db.execute("SELECT purge_search_misses()").fetchone()[0] == 0
