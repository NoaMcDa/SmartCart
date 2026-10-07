"""export-seo: categories.json, products.json, quality.json (issues #35, #21)."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from smartcart_catalog import cli_seo
from smartcart_catalog.export_seo import (
    CATEGORIES_FILE,
    MAX_PAGES,
    MIN_PAGES,
    PRODUCTS_FILE,
    QUALITY_FILE,
    PriceRow,
    aggregate_prices,
    build_quality,
    category_slug,
    export_from_db,
    export_from_files,
)
from smartcart_catalog.seed import load_catalog, seed_all
from smartcart_catalog.taxonomy import default_data_dir

SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "apps" / "web" / "public" / "seo"
NOW = datetime(2026, 10, 7, 6, 0, tzinfo=UTC)


# --- seeded prices (shared with test_basket_index) ------------------------------------------------


class PriceWorld:
    """Chains, stores, one item per chain and ``put`` to write effective_prices rows."""

    def __init__(self, db) -> None:
        self.db = db
        seed_all(db, load_catalog())
        self.canon = dict(db.execute("SELECT slug, id FROM canonical_products").fetchall())
        self.stores: dict[str, int] = {}
        self.items: dict[str, int] = {}
        for chain, name in (("a", "רמי לוי"), ("b", "שופרסל"), ("c", "יוחננוף")):
            db.execute(
                "INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (chain, name)
            )
            self.items[chain] = db.execute(
                "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, 'x', 'פריט')"
                " RETURNING id",
                (chain,),
            ).fetchone()[0]
        for key, chain, channel in (
            ("a1", "a", "physical"), ("a2", "a", "physical"), ("a3", "a", "physical"),
            ("b1", "b", "physical"), ("b2", "b", "physical"),
            ("c1", "c", "physical"), ("c_online", "c", "online"),
        ):  # fmt: skip
            self.stores[key] = db.execute(
                "INSERT INTO stores (chain_id, store_code, name, channel) VALUES (%s, %s, %s, %s)"
                " RETURNING id",
                (chain, key, key, channel),
            ).fetchone()[0]

    def put(
        self,
        slug: str,
        store: str,
        unit_price: str,
        *,
        level: str = "any_brand",
        club: bool = False,
        noclub: str | None = None,
        estimated: bool = False,
        valid_from: datetime = NOW,
        computed_at: datetime = NOW,
    ) -> None:
        chain = store[0]
        noclub_json = (
            json.dumps(
                {"effective_unit_price": noclub, "is_estimated": estimated,
                 "price_valid_from": valid_from.isoformat()}
            )
            if noclub is not None
            else None
        )  # fmt: skip
        self.db.execute(
            "INSERT INTO effective_prices (canonical_id, store_id, item_id, flex_level, shelf_price,"
            " effective_unit_price, uom, club_required, price_valid_from, computed_at, is_estimated,"
            " noclub) VALUES (%s, %s, %s, %s, %s, %s, 'unit', %s, %s, %s, %s, %s)",
            (self.canon[slug], self.stores[store], self.items[chain], level, unit_price,
             unit_price, club, valid_from, computed_at, estimated, noclub_json),
        )  # fmt: skip


@pytest.fixture
def prices(db) -> PriceWorld:
    return PriceWorld(db)


# --- categories and the page budget ----------------------------------------------------------------


def test_files_mode_covers_every_mvp_canonical_within_the_page_budget(tmp_path) -> None:
    result = export_from_files(load_catalog(default_data_dir()), tmp_path, now=NOW)
    categories = json.loads((tmp_path / CATEGORIES_FILE).read_text(encoding="utf-8"))
    products = json.loads((tmp_path / PRODUCTS_FILE).read_text(encoding="utf-8"))
    assert not (tmp_path / QUALITY_FILE).exists()  # files mode never writes the quality metric
    assert products["count"] == 245 and len(products["products"]) == 245
    assert MIN_PAGES <= result.pages <= MAX_PAGES
    assert categories["page_count"] + products["page_count"] == result.pages
    # taxonomy levels 1 and 2 only, with their canonical counts
    assert {c["level"] for c in categories["categories"]} == {1, 2}
    dairy = next(c for c in categories["categories"] if c["slug"] == "dairy")
    assert dairy["canonical_count"] == 37 and dairy["parent_slug"] is None and dairy["has_page"]
    milk = next(c for c in categories["categories"] if c["slug"] == "dairy-milk")
    assert milk["parent_slug"] == "dairy" and milk["path"][0]["name_he"] == dairy["name_he"]
    health = next(c for c in categories["categories"] if c["slug"] == "health")
    assert health["canonical_count"] == 0 and not health["has_page"]
    # best-ranked products get the pages
    ranked = sorted(products["products"], key=lambda p: p["rank"])
    assert all(p["has_page"] for p in ranked[: products["page_count"]])
    assert not any(p["has_page"] for p in ranked[products["page_count"] :])


def test_every_product_has_a_name_unit_attributes_and_the_no_prices_flag(tmp_path) -> None:
    export_from_files(load_catalog(default_data_dir()), tmp_path, now=NOW)
    products = json.loads((tmp_path / PRODUCTS_FILE).read_text(encoding="utf-8"))["products"]
    milk = next(p for p in products if p["slug"] == "milk-fresh-3")
    assert milk["name_he"] == "חלב טרי 3%"
    assert milk["base_unit"] == "100ml"
    assert milk["critical_attrs"] == {"fat_pct": 3, "state": "fresh"}
    assert [n["id"] for n in milk["path"]] == ["dairy", "dairy.milk", "dairy.milk.fresh"]
    assert [n["slug"] for n in milk["path"]] == ["dairy", "dairy-milk", None]
    for p in products:
        assert p["no_prices_yet"] is True and p["prices"] is None and p["price_valid_from"] is None


def test_page_budget_is_configurable(tmp_path) -> None:
    result = export_from_files(load_catalog(default_data_dir()), tmp_path, max_pages=100, now=NOW)
    assert result.pages == 100


def test_category_slug_is_ascii_and_url_clean() -> None:
    assert category_slug("dairy.milk.long_life") == "dairy-milk-long_life"
    catalog = load_catalog(default_data_dir())
    slugs = [category_slug(n.id) for n in catalog.taxonomy.nodes]
    assert len(slugs) == len(set(slugs))


def test_committed_snapshot_matches_the_seed_files(tmp_path) -> None:
    """apps/web/public/seo must be regenerated when data/*.yaml changes (docs/seo.md)."""
    export_from_files(load_catalog(default_data_dir()), tmp_path, now=NOW)
    for name in (CATEGORIES_FILE, PRODUCTS_FILE):
        fresh = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        committed = json.loads((SNAPSHOT_DIR / name).read_text(encoding="utf-8"))
        fresh.pop("generated_at"), committed.pop("generated_at")
        assert fresh == committed, f"{name} is stale: run smartcart-catalog export-seo"


# --- prices ------------------------------------------------------------------------------------------


def _price(chain: str, store: int, value: str, day: int = 1, estimated: bool = False) -> PriceRow:
    return PriceRow("milk-fresh-3", chain, chain.upper(), store, Decimal(value), estimated,
                    datetime(2026, 10, day, tzinfo=UTC))  # fmt: skip


def test_aggregate_prices_min_median_per_chain_and_latest_date() -> None:
    rows = [_price("a", 1, "1.00", 3), _price("a", 2, "1.50", 5), _price("a", 3, "4.00", 2),
            _price("b", 4, "0.90", 4), _price("b", 5, "1.10", 1, estimated=True)]  # fmt: skip
    out = aggregate_prices(rows)["milk-fresh-3"]
    by_chain = {p["chain_id"]: p for p in out["prices"]}
    assert by_chain["a"]["min_unit_price"] == 1.0 and by_chain["a"]["median_unit_price"] == 1.5
    assert by_chain["a"]["stores"] == 3 and not by_chain["a"]["is_estimated"]
    assert by_chain["b"]["median_unit_price"] == 1.0 and by_chain["b"]["is_estimated"]
    assert [p["chain_id"] for p in out["prices"]] == ["b", "a"]  # cheapest median first
    assert out["price_valid_from"] == "2026-10-05T00:00:00Z"
    assert by_chain["a"]["price_valid_from"] == "2026-10-05T00:00:00Z"


@pytest.mark.db
def test_db_mode_aggregates_effective_prices_like_the_app(db, prices: PriceWorld, tmp_path) -> None:
    p = prices
    older = datetime(2026, 10, 5, tzinfo=UTC)
    p.put("milk-fresh-3", "a1", "0.50", valid_from=older)
    p.put("milk-fresh-3", "a2", "0.70")
    p.put("milk-fresh-3", "a3", "0.90")
    p.put("milk-fresh-3", "b1", "0.60")
    p.put("milk-fresh-3", "c_online", "0.10")  # online stores never count
    p.put("milk-fresh-3", "c1", "0.40", level="exact")  # only the any-brand level counts
    p.put("milk-fresh-3", "b2", "0.20", club=True, noclub="0.80")  # club promo: use the no-club option
    p.put("cottage-5", "a1", "0.99", club=True)  # club-only and no alternative: left out
    p.put("tomato", "a1", "6.90", estimated=True)

    result = export_from_db(db, tmp_path, now=NOW)
    products = {x["slug"]: x for x in result.products["products"]}
    milk = products["milk-fresh-3"]
    assert not milk["no_prices_yet"]
    by_chain = {x["chain_id"]: x for x in milk["prices"]}
    assert set(by_chain) == {"a", "b"}  # c has only an online store and an exact-level row
    assert (by_chain["a"]["min_unit_price"], by_chain["a"]["median_unit_price"]) == (0.5, 0.7)
    assert by_chain["a"]["stores"] == 3
    assert (by_chain["b"]["min_unit_price"], by_chain["b"]["median_unit_price"]) == (0.6, 0.7)
    assert by_chain["b"]["stores"] == 2
    assert milk["price_valid_from"] == "2026-10-07T06:00:00Z"
    assert products["cottage-5"]["no_prices_yet"] and products["cottage-5"]["prices"] is None
    assert products["tomato"]["prices"][0]["is_estimated"] is True
    assert result.products["priced_count"] == 2
    on_disk = json.loads((tmp_path / PRODUCTS_FILE).read_text(encoding="utf-8"))
    assert on_disk["products"][0]["slug"] == "milk-fresh-3"


# --- quality.json ---------------------------------------------------------------------------------------


def test_quality_without_an_evaluate_run_shows_no_number() -> None:
    q = build_quality(None, NOW)
    assert q == {"generated_at": "2026-10-07T06:00:00Z", "available": False}


def test_quality_comes_from_the_run_not_from_text() -> None:
    row = {
        "id": 7,
        "finished_at": datetime(2026, 10, 6, 12, 30, 5, tzinfo=UTC),
        "metrics": {
            "precision": {"exact": 1.0, "any_brand": 0.9876, "close": 0.95},
            "support": {"items": 831, "pairs": 2419, "predicted_exact": 120,
                        "predicted_any_brand": 400, "predicted_close": 80},
            "synthetic_gold_set": True,
            "judge": "rule",
        },
    }  # fmt: skip
    q = build_quality(row, NOW)
    assert q["available"] and q["run_id"] == 7 and q["measured_at"] == "2026-10-06T12:30:05Z"
    assert q["precision"] == {"exact": 1.0, "any_brand": 0.9876, "close": 0.95}
    assert q["sample"] == {"exact": 120, "any_brand": 400, "close": 80}
    assert q["synthetic"] is True and q["gold_items"] == 831 and q["target_any_brand"] == 0.98


def test_quality_omits_levels_without_a_precision() -> None:
    row = {"id": 1, "finished_at": NOW, "metrics": {"precision": {"any_brand": 0.99}, "support": {}}}
    q = build_quality(row, NOW)
    assert list(q["precision"]) == ["any_brand"] and q["synthetic"] is True  # unknown = synthetic


@pytest.mark.db
def test_db_mode_reads_the_latest_finished_evaluate_run(db, tmp_path) -> None:
    seed_all(db, load_catalog())
    old = {"precision": {"any_brand": 0.5}, "support": {}}
    new = {"precision": {"any_brand": 0.99}, "support": {"predicted_any_brand": 10},
           "synthetic_gold_set": False}  # fmt: skip
    db.execute("INSERT INTO match_runs (kind, finished_at, metrics) VALUES ('evaluate',"
               " '2026-10-01', %s::jsonb)", (json.dumps(old),))  # fmt: skip
    db.execute("INSERT INTO match_runs (kind, finished_at, metrics) VALUES ('evaluate',"
               " '2026-10-05', %s::jsonb)", (json.dumps(new),))  # fmt: skip
    db.execute("INSERT INTO match_runs (kind, finished_at, metrics) VALUES ('judge',"
               " '2026-10-06', '{}'::jsonb)")  # fmt: skip
    db.execute("INSERT INTO match_runs (kind, metrics) VALUES ('evaluate', %s::jsonb)",
               (json.dumps({"precision": {"any_brand": 0.1}}),))  # unfinished: ignored
    result = export_from_db(db, tmp_path, now=NOW)
    q = json.loads((tmp_path / QUALITY_FILE).read_text(encoding="utf-8"))
    assert result.quality == q
    assert q["precision"] == {"any_brand": 0.99} and q["synthetic"] is False
    assert q["measured_at"] == "2026-10-05T00:00:00Z"


# --- the command ------------------------------------------------------------------------------------


class _NoCommit:
    def __init__(self, conn) -> None:
        self._conn = conn

    def commit(self) -> None:
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def _app() -> typer.Typer:
    app = typer.Typer()
    cli_seo.register(app)
    return app


def test_register_adds_the_commands_to_the_catalog_cli() -> None:
    from smartcart_catalog.cli import app

    names = {c.name for c in app.registered_commands}
    assert {"export-seo", "basket-index"} <= names


def test_cli_export_from_files(tmp_path) -> None:
    out = CliRunner().invoke(_app(), ["export-seo", "--from-files", "--out", str(tmp_path),
                                      "--max-pages", "120"])  # fmt: skip
    assert out.exit_code == 0, out.output
    assert "120 pages" in out.output and "245 canonicals, 0 with prices" in out.output
    assert (tmp_path / PRODUCTS_FILE).exists() and not (tmp_path / QUALITY_FILE).exists()


@pytest.mark.db
def test_cli_export_from_db(db, monkeypatch, tmp_path) -> None:
    seed_all(db, load_catalog())

    @contextmanager
    def fake_connect():
        yield _NoCommit(db)

    monkeypatch.setattr(cli_seo, "_connect", fake_connect)
    out = CliRunner().invoke(_app(), ["export-seo", "--out", str(tmp_path)])
    assert out.exit_code == 0, out.output
    assert "quality: no evaluate run" in out.output
    assert json.loads((tmp_path / QUALITY_FILE).read_text(encoding="utf-8"))["available"] is False


# --- regenerating the committed snapshot ---------------------------------------------------------------


@pytest.mark.db
@pytest.mark.pgvector
@pytest.mark.skipif(
    os.environ.get("SMARTCART_REGEN_SEO") != "1",
    reason="set SMARTCART_REGEN_SEO=1 to rewrite apps/web/public/seo from the seeded test data",
)
def test_regenerate_the_committed_snapshot(db) -> None:
    """Writes apps/web/public/seo: categories and products from the seed files (no prices exist
    in seeded data), and quality.json from a fresh evaluation of the synthetic gold set.

    ``SMARTCART_REGEN_SEO=1 uv run pytest services/catalog/tests/test_export_seo.py -k regenerate``

    The evaluation runs on the gold set's own canonicals, the state the matching-eval workflow
    measures. The gold set adds its own taxonomy nodes to the database, so the catalog files are
    read from the seed files rather than from this database.
    """
    from smartcart_catalog.embed import HashEmbedder
    from smartcart_catalog.evaluate import run_evaluation
    from smartcart_catalog.export_seo import read_latest_evaluation, write_json
    from smartcart_catalog.judge import RuleJudge

    run_evaluation(db, RuleJudge(), HashEmbedder(), k=10)
    now = datetime.now(UTC)
    result = export_from_files(load_catalog(default_data_dir()), SNAPSHOT_DIR, now=now)
    quality = build_quality(read_latest_evaluation(db), now)
    write_json(SNAPSHOT_DIR / QUALITY_FILE, quality)
    assert quality["available"] and quality["synthetic"] is True
    assert result.products["priced_count"] == 0
