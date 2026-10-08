"""POST /parse-list and GET /search with Arabic lists, and the Arabic evaluation gate (issue #73)."""

from __future__ import annotations

import psycopg
import pytest
from api_world import JWT_SECRET
from fastapi.testclient import TestClient

from smartcart_api.db import get_conn
from smartcart_api.main import app
from smartcart_api.settings import get_settings
from smartcart_catalog.evaluate_ar import load_lines, passes, run_evaluation
from smartcart_catalog.seed import load_catalog, seed_all

pytestmark = [pytest.mark.db, pytest.mark.pgvector]


@pytest.fixture(scope="module")
def db(database):
    with psycopg.connect(database.dsn) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        seed_all(conn, load_catalog())
        try:
            yield conn
        finally:
            conn.rollback()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    get_settings.cache_clear()

    def _conn():
        yield db

    app.dependency_overrides[get_conn] = _conn
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)
        get_settings.cache_clear()


def _rows(client: TestClient, text: str) -> list[dict]:
    r = client.post("/parse-list", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def test_an_arabic_list_is_split_parsed_and_resolved(client) -> None:
    rows = _rows(client, "حليب 3%\n2 كيلو بندورة\nكوتيج 5%، علبتين لبنة\nلابتوب")
    assert [r["input_text"] for r in rows] == ["حليب 3%", "2 كيلو بندورة", "كوتيج 5%", "علبتين لبنة", "لابتوب"]
    milk, tomato, cottage, labane, laptop = rows
    assert milk["canonical"]["display_name_he"] == "חלב טרי 3%" and not milk["needs_confirmation"]
    assert float(tomato["quantity"]) == 2 and tomato["unit"] == "kg" and tomato["is_weighed"]
    assert cottage["canonical"]["display_name_he"] == "קוטג' 5%"
    assert float(labane["quantity"]) == 2 and labane["canonical"]["display_name_he"] == "לבנה 5%"
    assert laptop["not_found"] and laptop["canonical"] is None


def test_the_conjunction_splits_items_but_not_a_half(client) -> None:
    rows = _rows(client, "بندورة وخيار")
    assert [r["canonical"]["display_name_he"] for r in rows] == ["עגבניות", "מלפפונים"]
    rows = _rows(client, "كيلو ونص بندورة")  # "a kilo and a half of tomatoes": one row
    assert len(rows) == 1 and float(rows[0]["quantity"]) == 1.5 and rows[0]["unit"] == "kg"
    rows = _rows(client, "منديل ورق")  # a waw that starts a real word: the whole fragment resolves
    assert len(rows) == 1
    rows = _rows(client, "حليب 3% وجبنة بيضاء 5%")
    assert [r["canonical"]["display_name_he"] for r in rows] == ["חלב טרי 3%", "גבינה לבנה 5%"]


def test_a_missing_attribute_asks_and_a_wrong_one_never_answers(client) -> None:
    (milk,) = _rows(client, "حليب")
    assert milk["needs_confirmation"] and milk["confidence"] < 0.75
    assert {c["display_name_he"] for c in milk["candidates"]} & {"חלב טרי 3%", "חלב טרי 1%"}
    (odd,) = _rows(client, "حليب 2%")
    assert odd["needs_confirmation"] or odd["not_found"]
    names = {c["display_name_he"] for c in odd["candidates"]} | (
        {odd["canonical"]["display_name_he"]} if odd["canonical"] else set()
    )
    assert not names & {"חלב טרי 3%", "חלב טרי 1%"}  # a 2% line never offers a 3% or a 1% milk


def test_hebrew_and_arabic_lines_in_one_list(client) -> None:
    rows = _rows(client, "חלב 3%\nحليب 1%\nלחם")
    assert rows[0]["canonical"]["display_name_he"] == "חלב טרי 3%"  # no names_ar needed for Hebrew
    assert rows[1]["canonical"]["display_name_he"] == "חלב טרי 1%"


def test_search_endpoint_takes_arabic(client) -> None:
    r = client.get("/search", params={"q": "جبنة بلغارية 24%"})
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert hits[0]["canonical"]["display_name_he"] == "גבינה בולגרית 24%"
    assert "גבינה בולגרית 5%" not in [h["canonical"]["display_name_he"] for h in hits]
    assert hits[0]["matched_by"] == ["trigram", "fts"]


def test_search_endpoint_hebrew_is_unchanged(client) -> None:
    r = client.get("/search", params={"q": "גבינה בולגרית"})
    assert r.status_code == 200 and r.json()["hits"]
    assert all(h["matched_by"] != [] for h in r.json()["hits"])


# --- the evaluation -----------------------------------------------------------------------------------------


def test_arabic_evaluation_meets_the_precision_gate(db) -> None:
    """The synthetic Arabic query set (not evidence): any_brand precision >= 0.98 over /parse-list,
    and no line that expects `none` is served."""
    report = run_evaluation(db, load_lines(), seed=False)
    assert report.support["lines_all"] >= 300
    assert passes(report, 0.98), report.precision
    assert report.precision.get("all", 0) >= 0.98
    assert report.extra["none_lines_served"] == 0
    # the held-out lines, written after the rules were tuned, hold the same line
    assert report.extra["holdout_lines"] >= 90
    assert (report.extra["holdout_precision"] or 0) >= 0.98
    # recall is allowed to be lower (precision first) but not collapse
    assert report.recall["all"] >= 0.9
