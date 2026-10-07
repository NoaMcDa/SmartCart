"""Effective-price precompute (issue #47). Expected numbers are computed by hand."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from api_world import World, add_price, add_promo

from smartcart_api.precompute import (
    PromoTerms,
    derive_unit_price,
    fold_promo,
    precompute_effective_prices,
    to_base_unit,
)

D = Decimal


def _promo(reward_type: str, value: str | None, min_qty: str | None = None) -> PromoTerms:
    return PromoTerms(
        id=1, store_id=None, description="", club_only=False, club_name=None,
        min_qty=D(min_qty) if min_qty else None, reward_type=reward_type,
        reward_value=D(value) if value else None,
    )


# --- promo folding, no database ----------------------------------------------------------------


def test_one_plus_one_halves_the_price_when_buying_two() -> None:
    assert fold_promo(D("12.00"), _promo("buy_x_get_y", "1")) == (D("6.0000"), D(2))


def test_buy_two_get_one() -> None:
    # Pay for 2, take 3: 9.00 * 2 / 3 = 6.00 each, needs 3.
    assert fold_promo(D("9.00"), _promo("buy_x_get_y", "1", min_qty="2")) == (D("6.0000"), D(3))


def test_three_for_twenty() -> None:
    # 20 / 3 = 6.6667 each, needs 3.
    assert fold_promo(D("7.90"), _promo("bundle", "20", min_qty="3")) == (D("6.6667"), D(3))


def test_bundle_value_below_one_shelf_price_is_read_per_unit() -> None:
    assert fold_promo(D("7.90"), _promo("bundle", "5.50", min_qty="2")) == (D("5.5000"), D(2))


def test_price_promo() -> None:
    assert fold_promo(D("12.90"), _promo("price", "9.90")) == (D("9.9000"), D(1))


@pytest.mark.parametrize("rate", ["20", "0.2"])
def test_percent_promo_either_scale(rate: str) -> None:
    assert fold_promo(D("10.00"), _promo("percent", rate)) == (D("8.0000"), D(1))


@pytest.mark.parametrize(
    "promo",
    [
        _promo("price", "15.00"),  # dearer than the shelf
        _promo("percent", "100"),
        _promo("bundle", "40", min_qty="3"),  # 13.33 each > 12.90
        _promo("other", "1"),
        _promo("price", None),
    ],
)
def test_promos_that_do_not_lower_the_price_are_ignored(promo: PromoTerms) -> None:
    assert fold_promo(D("12.90"), promo) is None


def test_units() -> None:
    assert derive_unit_price(D("6.50"), D("260"), "גרם") == (D("6.50") * 100 / 260, "100g")
    assert derive_unit_price(D("6.90"), D("1"), "ליטר") == (D("0.69"), "100ml")
    assert derive_unit_price(D("12.90"), D("12"), "יח'") == (D("1.075"), "unit")
    assert derive_unit_price(D("1"), None, "גרם") is None
    assert to_base_unit(D("9.975"), "100g", "kg") == D("99.75")
    assert to_base_unit(D("89.90"), "kg", "100g") == D("8.99")
    assert to_base_unit(D("1"), "100ml", "100g") is None


# --- the job against the database ---------------------------------------------------------------



def _row(db, w: World, canon: str, store: str, flex: str = "any_brand") -> dict | None:
    cur = db.execute(
        "SELECT item_id, shelf_price, effective_price, effective_unit_price, uom, promo_id,"
        " promo_min_qty, club_required, club_name, noclub, is_estimated, price_valid_from"
        " FROM effective_prices WHERE canonical_id = %s AND store_id = %s AND flex_level = %s",
        (w.canon[canon], w.stores[store], flex),
    )
    r = cur.fetchone()
    if r is None:
        return None
    return dict(zip([c.name for c in cur.description], r, strict=True))


@pytest.fixture
def computed(db, world: World) -> World:
    precompute_effective_prices(db, chains=world.chains)
    return world


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_any_brand_picks_the_lowest_unit_price(db, computed: World) -> None:
    w = computed
    home = _row(db, w, "milk3", "home")
    assert home["item_id"] == w.items["milk3_c1_private"]
    assert home["effective_unit_price"] == D("0.6200") and home["promo_id"] is None
    # Store A has its own (exception) price for Tnuva, which beats the private label there.
    a = _row(db, w, "milk3", "a")
    assert a["item_id"] == w.items["milk3_c1_tnuva"] and a["shelf_price"] == D("5.90")
    # The far store of the same chain inherits the chain base price.
    assert _row(db, w, "milk3", "far")["shelf_price"] == D("6.20")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_flex_levels_widen_the_candidates(db, computed: World) -> None:
    w = computed
    assert _row(db, w, "milk3", "home", "exact")["item_id"] == w.items["milk3_c1_tnuva"]
    assert _row(db, w, "milk3", "b", "exact") is None  # c2 has no exact match
    assert _row(db, w, "salmon", "b", "any_brand") is None
    close = _row(db, w, "salmon", "b", "close")
    assert close["item_id"] == w.items["salmon_c2_frozen"]
    # 39.90 for 400 g = 9.975 per 100 g = 99.75 per kg (the canonical's base unit).
    assert close["uom"] == "kg" and close["effective_unit_price"] == D("99.7500")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_one_plus_one_at_one_store(db, computed: World) -> None:
    w = computed
    a = _row(db, w, "paste", "a")
    assert a["promo_id"] == w.promos["paste_1plus1"]
    assert (a["shelf_price"], a["effective_price"], a["promo_min_qty"]) == (D("3.00"), D("1.5000"), D(2))
    assert a["effective_unit_price"] == D("1.5000")
    home = _row(db, w, "paste", "home")
    assert home["promo_id"] is None and home["effective_price"] == D("3.50")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_three_for_twenty_chain_wide(db, computed: World) -> None:
    w = computed
    for store in ("home", "a", "far"):
        r = _row(db, w, "bread", store)
        assert r["promo_id"] == w.promos["bread_3for20"]
        assert (r["effective_price"], r["promo_min_qty"]) == (D("6.6667"), D(3))


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_club_promo_is_flagged_with_a_no_club_fallback(db, computed: World) -> None:
    w = computed
    r = _row(db, w, "eggs", "home")
    assert r["club_required"] and r["club_name"] == "מועדון לקוחות"
    assert r["effective_price"] == D("9.9000")
    # 9.90 / 12 eggs = 0.825 per egg
    assert r["effective_unit_price"] == D("0.8250")
    assert r["noclub"]["effective_price"] == "12.90" and r["noclub"]["promo_id"] is None
    assert r["noclub"]["effective_unit_price"] == "1.0750"
    assert _row(db, w, "eggs", "b")["noclub"] is None  # no club needed in c2


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_prices_from_unloaded_files_are_ignored(db, world: World) -> None:
    w = world
    fid = db.execute(
        "INSERT INTO file_tracking (sha256, chain_id, kind, status) VALUES (%s, 't-c1', 'price', 'quarantined')"
        " RETURNING id",
        ("f" * 64,),
    ).fetchone()[0]
    # A newer, absurd price from a quarantined file must not replace the loaded one.
    add_price(db, w.items["milk3_c1_private"], None, "0.10", "0.01", "100ml",
              w.valid_from + timedelta(hours=1), file_id=fid)
    add_promo(db, "t-c1", None, "PQ", [w.items["milk1_c1"]], "price", "0.50", file_id=fid)
    precompute_effective_prices(db, chains=w.chains)
    assert _row(db, w, "milk3", "home")["shelf_price"] == D("6.20")
    assert _row(db, w, "milk1", "home")["promo_id"] is None


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_expired_and_future_promos_are_ignored(db, world: World) -> None:
    w = world
    now = datetime.now(UTC)
    add_promo(db, "t-c1", None, "OLD", [w.items["milk1_c1"]], "price", "1.00",
              starts_at=now - timedelta(days=10), ends_at=now - timedelta(hours=1))
    add_promo(db, "t-c1", None, "NEW", [w.items["milk1_c1"]], "price", "1.00",
              starts_at=now + timedelta(days=1))
    precompute_effective_prices(db, chains=w.chains)
    assert _row(db, w, "milk1", "home")["promo_id"] is None
    # As of a time inside the old promo, it applies.
    precompute_effective_prices(db, as_of=now - timedelta(hours=2), chains=w.chains)
    assert _row(db, w, "milk1", "home")["effective_price"] == D("1.0000")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_idempotent_and_records_a_run(db, world: World) -> None:
    w = world
    first = precompute_effective_prices(db, chains=w.chains)
    snapshot = db.execute(
        "SELECT canonical_id, store_id, flex_level, item_id, effective_unit_price, promo_id"
        " FROM effective_prices ORDER BY 1, 2, 3"
    ).fetchall()
    second = precompute_effective_prices(db, chains=w.chains)
    again = db.execute(
        "SELECT canonical_id, store_id, flex_level, item_id, effective_unit_price, promo_id"
        " FROM effective_prices ORDER BY 1, 2, 3"
    ).fetchall()
    assert snapshot == again and first.rows_written == second.rows_written == len(again)
    assert second.rows_deleted == 0
    metrics = db.execute(
        "SELECT metrics FROM match_runs WHERE id = %s AND kind = 'precompute' AND finished_at IS NOT NULL",
        (second.run_id,),
    ).fetchone()[0]
    assert metrics["rows_written"] == len(again) and metrics["chains"] == 2
    assert metrics["rows_club_required"] >= 1 and metrics["rows_with_promo"] >= 1


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_stale_rows_are_removed(db, world: World) -> None:
    w = world
    precompute_effective_prices(db, chains=w.chains)
    db.execute("UPDATE item_canonical SET needs_review = true WHERE item_id = %s",
               (w.items["salmon_c2_frozen"],))
    result = precompute_effective_prices(db, chains=w.chains)
    assert _row(db, w, "salmon", "b", "close") is None and result.rows_deleted >= 1


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_cli_runs(db, world: World, monkeypatch) -> None:
    from typer.testing import CliRunner

    from smartcart_api import cli

    monkeypatch.setattr(cli, "_connect", lambda: _NoClose(db))
    out = CliRunner().invoke(cli.app, ["precompute", "--chain", "t-c1", "--chain", "t-c2"])
    assert out.exit_code == 0, out.output
    assert "rows_written" in out.output


class _NoClose:
    def __init__(self, conn) -> None:
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc) -> None:
        return None
