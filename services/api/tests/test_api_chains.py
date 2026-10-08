"""GET /chains/online (issue #72): the chains' public online stores, behind CART_HANDOFF_CHAINS."""

from __future__ import annotations

import psycopg
import pytest

from smartcart_api.settings import Settings, get_settings

pytestmark = [pytest.mark.db]

SHUFERSAL = "7290027600007"
SHUFERSAL_SEARCH = "https://www.shufersal.co.il/online/he/search?text={q}"


def flag(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("CART_HANDOFF_CHAINS", raising=False)
    else:
        monkeypatch.setenv("CART_HANDOFF_CHAINS", value)
    get_settings.cache_clear()


@pytest.fixture
def chains(db: psycopg.Connection) -> None:
    db.execute(
        "INSERT INTO chains (id, name, portal, online_url, search_url_template, online_referral)"
        " VALUES ('c-full', 'רשת מלאה', 'other', 'https://shop.example/', 'https://shop.example/s?q={q}', true),"
        " ('c-home', 'רשת בית', 'other', 'https://home.example/', NULL, false),"
        " ('c-none', 'רשת בלי אתר', 'other', NULL, NULL, false)"
    )


def by_id(client) -> dict[str, dict]:
    r = client.get("/chains/online")
    assert r.status_code == 200, r.text
    return {row["chain_id"]: row for row in r.json()}


def test_every_row_is_disabled_by_default(client, chains, monkeypatch) -> None:
    flag(monkeypatch, None)
    rows = by_id(client)
    assert {"c-full", "c-home", "c-none"} <= set(rows)
    assert not any(row["enabled"] for row in rows.values())
    assert rows["c-full"]["online_url"] == "https://shop.example/"
    assert rows["c-full"]["search_url_template"] == "https://shop.example/s?q={q}"


def test_enabled_needs_the_flag_and_an_address(client, chains, monkeypatch) -> None:
    flag(monkeypatch, " c-full , c-none ,unknown-chain")
    rows = by_id(client)
    assert rows["c-full"]["enabled"] is True
    assert rows["c-home"]["enabled"] is False  # has an address, not flagged
    assert rows["c-none"]["enabled"] is False  # flagged, but no address
    assert "unknown-chain" not in rows


def test_referral_is_reported_as_stored(client, chains, monkeypatch) -> None:
    flag(monkeypatch, "c-full,c-home")
    rows = by_id(client)
    assert rows["c-full"]["referral"] is True
    assert rows["c-home"]["referral"] is False
    assert rows["c-home"]["enabled"] is True and rows["c-home"]["search_url_template"] is None


def test_response_is_public_and_cacheable(client, chains, monkeypatch) -> None:
    flag(monkeypatch, None)
    r = client.get("/chains/online")  # no Authorization header
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=3600"


def test_settings_parse_the_comma_list(monkeypatch) -> None:
    monkeypatch.setenv("CART_HANDOFF_CHAINS", "a, b,,c")
    assert Settings().cart_handoff_chains == ["a", "b", "c"]
    monkeypatch.delenv("CART_HANDOFF_CHAINS")
    assert Settings().cart_handoff_chains == []


@pytest.mark.parametrize(
    "bad", ["http://insecure.example/", "ftp://x.example/", "https://has space.example/"]
)
def test_online_url_must_be_https(db: psycopg.Connection, bad: str) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("INSERT INTO chains (id, name, online_url) VALUES ('bad', 'x', %s)", (bad,))


@pytest.mark.parametrize("template", ["https://shop.example/search", "http://shop.example/?q={q}"])
def test_search_template_needs_https_and_the_placeholder(
    db: psycopg.Connection, template: str
) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO chains (id, name, search_url_template) VALUES ('bad', 'x', %s)",
            (template,),
        )


def test_new_chain_rows_get_the_seed_and_nothing_is_invented(db: psycopg.Connection) -> None:
    """The ingest loader creates chain rows after the migration: the trigger fills the seed."""
    db.execute("DELETE FROM chains WHERE id = %s", (SHUFERSAL,))
    db.execute(
        "INSERT INTO chains (id, name, portal) VALUES (%s, 'שופרסל', 'shufersal')", (SHUFERSAL,)
    )
    url, template, referral = db.execute(
        "SELECT online_url, search_url_template, online_referral FROM chains WHERE id = %s",
        (SHUFERSAL,),
    ).fetchone()
    assert url and template == SHUFERSAL_SEARCH and referral is False
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('7290000000000', 'אחר', 'other')")
    assert db.execute(
        "SELECT online_url, search_url_template FROM chains WHERE id = '7290000000000'"
    ).fetchone() == (None, None)
