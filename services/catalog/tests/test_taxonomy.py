"""Taxonomy v1 (issue #10): file validation, structure, and the "canonicals under a node" query."""

from __future__ import annotations

import psycopg
import pytest

from smartcart_catalog.seed import load_catalog, seed_all
from smartcart_catalog.taxonomy import (
    DEPARTMENT_COUNT,
    TaxonomyError,
    canonicals_under,
    load_taxonomy,
    parse_taxonomy,
)

STAPLES = ["dairy", "bakery", "pantry", "beverages", "produce", "meat", "fish", "cleaning"]


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy()


def test_nineteen_departments(taxonomy) -> None:
    deps = taxonomy.departments()
    assert len(deps) == DEPARTMENT_COUNT == 19
    assert all(d.name_he and d.name_en for d in deps)


def test_every_node_has_stable_id_hebrew_name_and_existing_parent(taxonomy) -> None:
    for node in taxonomy.nodes:
        assert node.name_he.strip()
        assert 1 <= node.level <= 4
        if node.parent_id:
            assert node.parent_id in taxonomy
            assert taxonomy.get(node.parent_id).level == node.level - 1


@pytest.mark.parametrize("department", STAPLES)
def test_staples_reach_product_type_level(taxonomy, department: str) -> None:
    deep = [n for n in taxonomy.nodes if n.id.startswith(department + ".") and n.level >= 3]
    assert len(deep) >= 3, f"{department} is not deepened to product types"


def test_path_he(taxonomy) -> None:
    assert taxonomy.path_he("dairy.milk.fresh") == "מוצרי חלב וביצים > חלב ומשקאות חלב > חלב טרי"
    assert [n.id for n in taxonomy.path("dairy.milk.fresh")] == [
        "dairy",
        "dairy.milk",
        "dairy.milk.fresh",
    ]


def _doc(*ids: str) -> dict:
    deps = [{"id": f"d{i}", "name_he": f"מחלקה {i}"} for i in range(19)]
    return {"nodes": deps + [{"id": i, "name_he": "x"} for i in ids]}


def test_missing_parent_rejected() -> None:
    with pytest.raises(TaxonomyError, match="parent d0.nope does not exist"):
        parse_taxonomy(_doc("d0.nope.milk"))


def test_bad_id_and_duplicate_rejected() -> None:
    with pytest.raises(TaxonomyError) as exc:
        parse_taxonomy(_doc("d0.Milk", "d0.milk", "d0.milk"))
    assert "bad id 'd0.Milk'" in str(exc.value)
    assert "d0.milk: duplicate id" in str(exc.value)


def test_too_deep_rejected() -> None:
    with pytest.raises(TaxonomyError, match="deeper than 4"):
        parse_taxonomy(_doc("d0.a", "d0.a.b", "d0.a.b.c", "d0.a.b.c.d"))


def test_department_count_enforced() -> None:
    doc = _doc()
    doc["nodes"] = doc["nodes"][:18]
    with pytest.raises(TaxonomyError, match="expected 19 departments, found 18"):
        parse_taxonomy(doc)


def test_missing_hebrew_name_rejected() -> None:
    doc = _doc("d0.a")
    doc["nodes"][-1]["name_he"] = " "
    with pytest.raises(TaxonomyError, match="d0.a: missing name_he"):
        parse_taxonomy(doc)


@pytest.mark.db
@pytest.mark.pgvector
def test_canonicals_under_a_category(db: psycopg.Connection) -> None:
    seed_all(db, load_catalog())
    milk = dict(canonicals_under(db, "dairy.milk")).values()
    assert {"milk-fresh-3", "milk-fresh-1", "milk-long-life-3", "chocolate-milk"} <= set(milk)
    assert "cottage-5" not in milk
    dairy = {slug for _, slug in canonicals_under(db, "dairy")}
    assert set(milk) < dairy and "cottage-5" in dairy
    assert {slug for _, slug in canonicals_under(db, "dairy.milk.fresh")} == {
        "milk-fresh-3",
        "milk-fresh-1",
    }
    # prefix match is on whole segments: "dairy.mil" is not a node and matches nothing
    assert canonicals_under(db, "dairy.mil") == []
