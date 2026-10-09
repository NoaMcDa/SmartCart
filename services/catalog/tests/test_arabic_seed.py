"""Arabic canonical names: the seed file, its validation and the database column (issue #73)."""

from __future__ import annotations

import copy

import pytest
import yaml

from smartcart_catalog.normalize import ar_attributes, has_arabic, normalize_ar
from smartcart_catalog.seed import (
    MAX_NAMES_AR,
    SeedError,
    load_catalog,
    parse_canonicals,
    seed_all,
)
from smartcart_catalog.taxonomy import default_data_dir


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def _raw() -> dict:
    return yaml.safe_load((default_data_dir() / "canonicals.yaml").read_text(encoding="utf-8"))


def _problems(catalog, doc: dict) -> str:
    with pytest.raises(SeedError) as exc:
        parse_canonicals(doc, catalog.taxonomy, catalog.rules)
    return str(exc.value)


# --- the shipped file ------------------------------------------------------------------------------


def test_every_canonical_has_one_to_three_arabic_names(catalog) -> None:
    assert len(catalog.canonicals) == 245
    for c in catalog.canonicals:
        assert 1 <= len(c.names_ar) <= MAX_NAMES_AR, c.slug
        assert all(has_arabic(n) for n in c.names_ar), c.slug


def test_no_two_canonicals_share_a_normalized_name(catalog) -> None:
    seen: dict[str, str] = {}
    for c in catalog.canonicals:
        for name in c.names_ar:
            norm = normalize_ar(name)
            assert norm not in seen, f"{c.slug} and {seen[norm]} share {name!r}"
            seen[norm] = c.slug


def test_names_state_the_critical_attributes(catalog) -> None:
    for c in catalog.canonicals:
        for name in c.names_ar:
            stated = ar_attributes(name)
            if "fat_pct" in c.critical_attrs:
                assert {float(f) for f in stated.fat_pct} == {float(c.critical_attrs["fat_pct"])}, (
                    c.slug,
                    name,
                )
            if "base" in c.critical_attrs:
                assert stated.base == {c.critical_attrs["base"]}, (c.slug, name)
            if c.critical_attrs.get("state") in ("frozen", "canned"):
                assert c.critical_attrs["state"] in stated.state, (c.slug, name)


def test_the_file_says_the_names_are_machine_drafted() -> None:
    head = (default_data_dir() / "canonicals.yaml").read_text(encoding="utf-8")[:3000]
    assert "MACHINE-DRAFTED" in head and "native Arabic speaker" in head


def test_milk_fat_percentages_are_stated_in_every_name(catalog) -> None:
    by_slug = {c.slug: c for c in catalog.canonicals}
    assert all("3%" in n for n in by_slug["milk-fresh-3"].names_ar)
    assert all("1%" in n for n in by_slug["milk-fresh-1"].names_ar)
    assert all("مجمد" in n for n in by_slug["chicken-breast-frozen"].names_ar)
    assert any("لوز" in n for n in by_slug["almond-drink"].names_ar)


# --- validation catches mistakes --------------------------------------------------------------------


def test_missing_names_rejected(catalog) -> None:
    doc = copy.deepcopy(_raw())
    del doc["canonicals"][0]["names_ar"]
    assert "milk-fresh-3: names_ar must list 1-3 Arabic names" in _problems(catalog, doc)
    doc = copy.deepcopy(_raw())
    doc["canonicals"][0]["names_ar"] = ["a", "b", "c", "d"]
    assert "names_ar must list 1-3" in _problems(catalog, doc)


def test_names_need_arabic_letters(catalog) -> None:
    doc = copy.deepcopy(_raw())
    doc["canonicals"][0]["names_ar"] = ["milk 3%"]
    assert "has no Arabic letters" in _problems(catalog, doc)


def test_identical_normalized_names_rejected(catalog) -> None:
    doc = copy.deepcopy(_raw())
    # 'حليب طازج 3%' written with tashkeel, alef variants and a different digit script
    doc["canonicals"][1]["names_ar"] = ["حَلِيب طازج ٣٪", "حليب 1%"]
    text = _problems(catalog, doc)
    assert "is also a name of milk-fresh-3" in text
    assert "must state the fat percentage 1%" in text  # the first name states 3%


def test_repeated_name_after_folding_rejected(catalog) -> None:
    doc = copy.deepcopy(_raw())
    doc["canonicals"][0]["names_ar"] = ["حليب 3%", "حليب ٣%"]
    assert "repeats another name after folding" in _problems(catalog, doc)


def test_a_name_may_not_start_with_the_article(catalog) -> None:
    doc = copy.deepcopy(_raw())
    doc["canonicals"][0]["names_ar"] = ["الحليب 3%"]
    assert "do not start a name with the article" in _problems(catalog, doc)


def test_fat_percentage_must_be_stated(catalog) -> None:
    doc = copy.deepcopy(_raw())
    doc["canonicals"][0]["names_ar"] = ["حليب طازج"]
    assert "must state the fat percentage 3%" in _problems(catalog, doc)


def test_frozen_must_be_stated_and_not_contradicted(catalog) -> None:
    doc = copy.deepcopy(_raw())
    frozen = next(c for c in doc["canonicals"] if c["slug"] == "chicken-breast-frozen")
    frozen["names_ar"] = ["صدر دجاج"]
    assert "must state the state frozen" in _problems(catalog, doc)
    doc = copy.deepcopy(_raw())
    fresh = next(c for c in doc["canonicals"] if c["slug"] == "chicken-breast-fresh")
    fresh["names_ar"] = ["صدر دجاج مجمد"]
    text = _problems(catalog, doc)
    assert "must state the state fresh" in text and "the canonical is fresh" in text


def test_plant_base_must_be_stated(catalog) -> None:
    doc = copy.deepcopy(_raw())
    almond = next(c for c in doc["canonicals"] if c["slug"] == "almond-drink")
    almond["names_ar"] = ["مشروب صويا"]
    assert "must state the base almond" in _problems(catalog, doc)


def test_flavor_must_be_stated_when_a_sibling_differs(catalog) -> None:
    doc = copy.deepcopy(_raw())
    peach = next(c for c in doc["canonicals"] if c["slug"] == "yogurt-peach")
    peach["names_ar"] = ["زبادي فراولة"]
    text = _problems(catalog, doc)
    assert "must state the flavor peach" in text and "also a name of yogurt-strawberry" in text


# --- the database ------------------------------------------------------------------------------------


@pytest.mark.db
def test_seed_writes_names_ar_and_is_idempotent(db, catalog) -> None:
    first = seed_all(db, catalog)
    assert first.canonicals.inserted == 245
    rows = dict(db.execute("SELECT slug, names_ar FROM canonical_products").fetchall())
    assert rows["milk-fresh-3"] == ["حليب طازج 3%", "حليب 3%"]
    assert all(rows[c.slug] == list(c.names_ar) for c in catalog.canonicals)
    again = seed_all(db, catalog)
    assert (again.canonicals.inserted, again.canonicals.updated) == (0, 0)
    assert again.canonicals.unchanged == 245


@pytest.mark.db
def test_a_changed_name_is_an_update(db, catalog) -> None:
    seed_all(db, catalog)
    db.execute("UPDATE canonical_products SET names_ar = '{x}' WHERE slug = 'butter'")
    report = seed_all(db, catalog)
    assert report.canonicals.updated == 1
    names = db.execute("SELECT names_ar FROM canonical_products WHERE slug = 'butter'").fetchone()
    assert names[0] == ["زبدة"]
