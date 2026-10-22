"""Proposals for new canonicals (issue #52): grouping, derivation, ranking, exclusions.

Synthetic items with known answers, plus the committed real fixtures for the invariants that must
hold on any data: a proposal is never a duplicate of an existing canonical, never states a value
no member states, and is sold by at least two chains.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_catalog import proposals as P
from smartcart_catalog.embed import HashEmbedder
from smartcart_catalog.seed import load_catalog

CHAINS = {
    "c1": "רשת א",
    "c2": "רשת ב",
    "c3": "רשת ג",
    "c4": "רשת ד",
}


def gtin(prefix12: str) -> str:
    """An EAN-13 with its correct check digit."""
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(prefix12))
    return prefix12 + str((10 - total % 10) % 10)


def item(chain, code, name, *, barcode=None, qty=None, unit=None, stores=3, price="9.90",
         events=2, weighed=False, maker=None):  # fmt: skip
    return P.CandidateItem(
        chain_id=chain, chain_name=CHAINS[chain], item_code=code, raw_name=name, barcode=barcode,
        manufacturer=maker, quantity=None if qty is None else Decimal(str(qty)), unit=unit,
        is_weighed=weighed, stores=stores, price=Decimal(price), price_events=events,
    )  # fmt: skip


def pool_of(items, mapped=0):
    return P.ItemPool(
        items=list(items), total_items=len(items) + mapped, mapped_items=mapped, source="test",
        chains=dict(CHAINS),
    )  # fmt: skip


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def run(items, catalog, **kw):
    return P.propose(pool_of(items), catalog, **kw)


# --- barcodes -------------------------------------------------------------------------------------


def test_valid_barcode_needs_a_gs1_check_digit() -> None:
    good = gtin("729000112233")
    assert P.valid_barcode(good) == good
    assert P.valid_barcode("0" + good) == good  # a leading zero is the same product
    assert P.valid_barcode(good[:-1] + str((int(good[-1]) + 1) % 10)) is None
    assert P.valid_barcode("12345") is None  # a chain's own code
    assert P.valid_barcode("") is None and P.valid_barcode(None) is None
    assert P.valid_barcode("72900011223a4") is None


def test_the_same_barcode_at_several_chains_is_one_product(catalog) -> None:
    code = gtin("729000112233")
    items = [
        item("c1", "1", "רוטב טבסקו חריף 60 מל", barcode=code),
        item("c2", "2", "טבסקו רוטב חריף 60מל", barcode=code),
        item("c3", "3", "רוטב חריף טבסקו 60 מיליליטר", barcode=code),
    ]
    prepared = P.prepare(items, catalog)
    clusters, conflicts = P.cluster_by_barcode(prepared)
    assert conflicts == 0
    assert len(clusters) == 1 and len(clusters[0].chains) == 3


def test_a_wrong_barcode_in_one_chain_is_split_off_not_merged(catalog) -> None:
    code = gtin("729000112244")
    items = [
        item("c1", "1", "רוטב טבסקו חריף 60 מל", barcode=code),
        item("c2", "2", "רוטב טבסקו חריף 60 מל", barcode=code),
        item("c3", "3", "מטאטא לרצפה עם ידית", barcode=code),
    ]
    clusters, conflicts = P.cluster_by_barcode(P.prepare(items, catalog))
    assert conflicts == 1
    assert sorted(len(c.members) for c in clusters) == [1, 2]


def test_a_code_without_a_check_digit_never_merges_two_products(catalog) -> None:
    items = [
        item("c1", "1", "רוטב טבסקו חריף", barcode="123456789012"),
        item("c2", "2", "מטאטא לרצפה", barcode="123456789012"),
    ]
    clusters, _ = P.cluster_by_barcode(P.prepare(items, catalog))
    assert len(clusters) == 2


# --- the sparse vector is the hash embedder's ---------------------------------------------------------


def test_sparse_hash_vector_equals_the_hash_embedder() -> None:
    text = "גבינה בולגרית 24%"
    dense = HashEmbedder().embed([text])[0]
    sparse = P.sparse_hash_vector(text)
    assert {i: v for i, v in enumerate(dense) if v} == pytest.approx(sparse)


# --- core names -----------------------------------------------------------------------------------


def test_the_core_name_drops_sizes_packaging_and_the_brand() -> None:
    items = [
        item("c1", str(n), f"כוסמת לבנה {b} 500 גרם", maker=b) for n, b in enumerate(("תבל",) * 3)
    ]
    lex = P.BrandLexicon.build(items)
    words, folded = P.core_tokens(items[0], lex)
    assert words == ("כוסמת", "לבנה")
    assert "תבל" not in words and not any(w.isdigit() for w in words)


def test_a_percentage_stays_in_the_core_name() -> None:
    lex = P.BrandLexicon(frozenset())
    words, _ = P.core_tokens(item("c1", "1", "גבינה בולגרית 18% 250 גרם"), lex)
    assert "18%" in words


def test_the_last_word_of_a_name_cut_at_the_chain_width_is_not_trusted() -> None:
    it = P.CandidateItem("7290058140886", "רמי לוי", "1", "סבון מוצק פלמוליב יר", stores=1)
    assert len(it.raw_name) == 20
    words, _ = P.core_tokens(it, P.BrandLexicon(frozenset()))
    assert words == ("סבון", "מוצק", "פלמוליב")


def test_cut_prefix() -> None:
    assert P._is_cut_prefix(("פילה", "סלמ"), ("פילה", "סלמון", "קפוא"))
    assert not P._is_cut_prefix(("פילה",), ("פילה", "סלמון"))  # one word is not enough
    assert not P._is_cut_prefix(("פילה", "דג"), ("פילה", "סלמון"))


# --- proposals: variants, gaps, nothing invented ----------------------------------------------------


def banana(chain, n, name="יוגורט פירות בננה"):
    return item(chain, n, name, qty=200, unit="גרם", barcode=gtin(f"72900022{n.zfill(4)}"))


def test_a_new_flavor_of_an_existing_type_is_a_variant_proposal(catalog) -> None:
    r = run([banana("c1", "1"), banana("c2", "2", "יוגורט פירות בננה 200 גרם"),
             banana("c3", "3", "יוגורט פירות בננה תנובה")], catalog)  # fmt: skip
    assert len(r.proposals) == 1
    p = r.proposals[0]
    assert p.kind == "variant" and p.product_type == "yogurt_fruit"
    assert p.critical_attrs == {"flavor": "banana"}
    assert p.taxonomy_id == "dairy.yogurt.fruit"
    assert p.base_unit == "100g" and p.soft_attrs == {"pack_size": 200, "unit": "g"}
    assert p.chains == 3 and p.items == 3 and p.slug == "yogurt-fruit-banana"
    assert "names_ar" not in p.uncertain  # an Arabic name is never proposed
    assert not any("critical_attrs" in u for u in p.uncertain)


def test_a_group_the_catalog_already_covers_is_a_matching_gap_not_a_proposal(catalog) -> None:
    items = [banana(c, str(n), "יוגורט פירות אפרסק") for n, c in enumerate(("c1", "c2", "c3"), 1)]
    r = run(items, catalog)
    assert r.proposals == []
    assert r.stats["matching_gaps"]["groups"] == 1 and r.stats["matching_gaps"]["items"] == 3
    assert r.stats["matching_gaps"]["top"][0]["canonical"] == "yogurt-peach"


def test_a_critical_value_no_name_states_is_never_invented(catalog) -> None:
    items = [item(c, str(n), "גבינה בולגרית 250 גרם") for n, c in enumerate(("c1", "c2", "c3"), 1)]
    r = run(items, catalog)
    assert r.proposals == []  # bulgarian cheese needs a fat percentage; none is stated
    assert r.stats["missing_critical"]["groups"] == 1


def test_a_stated_fat_percentage_gives_a_variant(catalog) -> None:
    items = [item(c, str(n), "גבינה בולגרית 18% 250 גרם") for n, c in enumerate(("c1", "c2"), 1)]
    p = run(items, catalog).proposals[0]
    assert p.product_type == "bulgarian_cheese" and p.critical_attrs == {"fat_pct": 18}


def pepper(chain, n):
    return item(chain, n, "כוסמת אדומה", weighed=False, qty=500, unit="גרם")


def test_an_unknown_product_is_a_new_type_with_the_uncertain_fields_marked(catalog) -> None:
    r = run([pepper("c1", "1"), pepper("c2", "2")], catalog)
    p = r.proposals[0]
    assert p.kind == "new_type" and p.product_type is None
    text = " | ".join(p.uncertain)
    assert "product_type" in text and "taxonomy_id" in text
    assert p.critical_attrs == {}  # no fat, state or base is stated


def test_pack_size_is_only_stated_when_the_members_agree(catalog) -> None:
    same = [
        item(c, str(n), "כוסמת אדומה", qty=500, unit="גרם")
        for n, c in enumerate(("c1", "c2", "c3"), 1)
    ]
    assert run(same, catalog).proposals[0].soft_attrs == {"pack_size": 500, "unit": "g"}
    varied = [
        item("c1", "1", "כוסמת אדומה", qty=250, unit="גרם"),
        item("c2", "2", "כוסמת אדומה", qty=500, unit="גרם"),
        item("c3", "3", "כוסמת אדומה", qty=900, unit="גרם"),
    ]
    p = run(varied, catalog).proposals[0]
    assert p.soft_attrs == {}
    assert any("sizes vary" in u for u in p.uncertain)


def test_a_group_sold_by_one_chain_is_not_proposed_by_default(catalog) -> None:
    items = [item("c1", "1", "כוסמת אדומה"), item("c1", "2", "כוסמת אדומה 500 גרם")]
    assert run(items, catalog).proposals == []
    assert len(run(items, catalog, min_chains=1).proposals) == 1


def test_word_order_and_brand_do_not_split_a_group(catalog) -> None:
    items = [
        item("c1", "1", "כוסמת אדומה", qty=500, unit="גרם", maker="תבל"),
        item("c2", "2", "אדומה כוסמת", qty=500, unit="גרם", maker="תבל"),
        item("c3", "3", "כוסמת אדומה", qty=500, unit="גרם", maker="תבל"),
        item("c4", "4", "כוסמת אדומה", qty=500, unit="גרם", maker="תבל"),
    ]
    r = run(items, catalog)
    assert len(r.proposals) == 1 and r.proposals[0].chains == 4


# --- ranking ------------------------------------------------------------------------------------------


def test_wider_groups_rank_first_and_shared_barcodes_break_ties(catalog) -> None:
    wide = [item(c, f"w{c}", "כוסמת אדומה", qty=500, unit="גרם") for c in ("c1", "c2", "c3", "c4")]
    code = gtin("729000333444")
    shared = [
        item("c1", "s1", "טופו קשה", barcode=code, qty=400, unit="גרם"),
        item("c2", "s2", "טופו קשה", barcode=code, qty=400, unit="גרם"),
    ]
    plain = [
        item("c1", "p1", "שמן שומשום", barcode=gtin("729000333555"), qty=250, unit="מיליליטר"),
        item("c2", "p2", "שמן שומשום", barcode=gtin("729000333666"), qty=250, unit="מיליליטר"),
    ]
    r = run(wide + plain + shared, catalog)
    names = [p.display_name_he for p in r.proposals]
    assert names[0] == "כוסמת אדומה"
    assert names.index("טופו קשה") < names.index("שמן שומשום")
    assert [p.rank for p in r.proposals] == [1, 2, 3]
    assert r.proposals[0].priority > r.proposals[1].priority >= r.proposals[2].priority
    assert r.proposals[0].components["chains"] == 1.0


def test_search_misses_raise_the_rank_of_the_group_they_name(catalog) -> None:
    a = [item(c, f"a{c}", "כוסמת אדומה", qty=500, unit="גרם") for c in ("c1", "c2")]
    b = [item(c, f"b{c}", "שמן שומשום", qty=250, unit="מיליליטר") for c in ("c1", "c2")]
    pool = pool_of(a + b)
    base = P.propose(pool, catalog).proposals
    pool.misses = [("שומשום", 12), ("כוסמת", 1)]
    boosted = P.propose(pool, catalog).proposals
    assert boosted[0].display_name_he == "שמן שומשום" and boosted[0].miss_hits == 12
    assert {p.display_name_he for p in base} == {p.display_name_he for p in boosted}


def test_top_limits_the_proposals_and_the_run_is_deterministic(catalog) -> None:
    items = []
    for n, word in enumerate(("כוסמת", "שומשום", "דוחן", "טופו")):
        items += [item(c, f"{n}{c}", f"{word} מלא", qty=500, unit="גרם") for c in ("c1", "c2")]
    one = run(items, catalog, top=2)
    two = run(list(reversed(items)), catalog, top=2)
    assert len(one.proposals) == 2
    assert [p.proposal_id for p in one.proposals] == [p.proposal_id for p in two.proposals]


def test_examples_show_a_real_item_per_chain_with_barcode_size_and_price(catalog) -> None:
    code = gtin("729000444555")
    items = [
        item("c1", "1", "כוסמת אדומה", barcode=code, qty=500, unit="גרם", price="14.90"),
        item("c2", "2", "כוסמת אדומה", barcode=code, qty=500, unit="גרם", price="13.50"),
    ]
    p = run(items, catalog).proposals[0]
    assert {e.chain for e in p.examples} == {"רשת א", "רשת ב"}
    e = next(e for e in p.examples if e.chain == "רשת א")
    assert (e.barcode, e.size, e.price, e.shared) == (code, "500 גרם", "14.90", True)
    assert p.shared_barcodes == 1


# --- invariants on the committed real fixtures ----------------------------------------------------------


@pytest.fixture(scope="module")
def real(catalog):
    pool = P.items_from_fixtures(catalog)
    return pool, P.propose(pool, catalog, top=60)


def test_the_real_fixtures_have_unmapped_items_and_proposals(real) -> None:
    pool, r = real
    assert pool.total_items > 1000 and 0 < pool.unmapped_items < pool.total_items
    assert r.proposals, "the real files should give at least one proposal"


def test_no_real_proposal_duplicates_a_canonical_or_states_an_invented_value(real, catalog) -> None:
    _, r = real
    existing = {c.slug for c in catalog.canonicals}
    slugs = [p.slug for p in r.proposals]
    assert len(set(slugs)) == len(slugs) and not set(slugs) & existing
    for p in r.proposals:
        assert p.chains >= 2 and len(p.chain_names) >= 2
        assert p.display_name_he.strip() and p.base_unit
        assert p.examples and {e.chain for e in p.examples} >= set(p.chain_names[:1])
        if p.kind == "variant":
            rule = catalog.rules[p.product_type]
            assert set(p.critical_attrs) == set(rule.critical_keys)  # all stated, none extra
            assert P.covered_by(catalog, p.product_type, p.critical_attrs) is None
            assert set(p.soft_attrs) <= set(rule.soft_keys) | {"unit"}
        else:
            assert p.product_type is None
            assert set(p.critical_attrs) <= set(P.UNTYPED_KEYS)
            assert any("product_type" in u for u in p.uncertain)


def test_real_proposals_are_ranked_by_priority(real) -> None:
    _, r = real
    pri = [p.priority for p in r.proposals]
    assert pri == sorted(pri, reverse=True)
    assert [p.rank for p in r.proposals] == list(range(1, len(r.proposals) + 1))


def test_the_run_accounts_for_every_group(real) -> None:
    _, r = real
    s = r.stats
    excluded = sum(s[k]["groups"] for k in ("matching_gaps", "missing_critical", "unspecific_critical",
                                           "below_min_chains", "low_cohesion", "no_base_unit"))  # fmt: skip
    assert s["candidate_groups"] + excluded <= s["groups"]
    assert s["candidate_groups"] + excluded == s["groups"]


def test_a_critical_value_that_says_something_else_is_never_proposed() -> None:
    assert P.is_unspecific("other") and P.is_unspecific("milk+other")
    assert not P.is_unspecific("milk") and not P.is_unspecific("strawberry")


def test_a_percentage_in_an_untyped_name_stays_in_the_name_and_is_not_called_fat(catalog) -> None:
    items = [
        item(c, str(n), "רוטב עגבניות 22% בשלות", qty=240, unit="גרם")
        for n, c in enumerate(("c1", "c2"), 1)
    ]
    p = run(items, catalog).proposals[0]
    assert "22%" in p.display_name_he and "fat_pct" not in p.critical_attrs
    assert any("reviewer" in u and "critical_attrs" in u for u in p.uncertain)


def test_a_name_from_a_single_product_is_marked_as_possibly_carrying_a_brand(catalog) -> None:
    code = gtin("729000777888")
    items = [
        item(c, str(n), "במבה נוגט", barcode=code, qty=150, unit="גרם")
        for n, c in enumerate(("c1", "c2"), 1)
    ]
    p = run(items, catalog).proposals[0]
    assert p.skus == 1 and any("single product" in u for u in p.uncertain)
