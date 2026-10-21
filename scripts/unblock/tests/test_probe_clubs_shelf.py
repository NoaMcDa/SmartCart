"""The probe's club log lines and the same-store shelf check (no network, no database).

uv run pytest scripts/unblock/tests -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import portal_probe  # noqa: E402

FIXTURES = REPO / "services" / "ingest" / "tests" / "fixtures"


def _profile(slug: str):
    from smartcart_ingest.adapters.fetch_fixtures import adapters_by_slug

    adapter = adapters_by_slug()[slug]()
    folder = FIXTURES / slug / "real"
    promo = next(folder.glob("PromoFull*"))
    price = next(folder.glob("PriceFull*"))
    return portal_probe.parse_summary(adapter, promo, price)["profile"]


# --- the same-store PriceFull ------------------------------------------------------------------


def _fake_fetch(listing: dict[str, set[int]]):
    """A ``fetch_one`` stand-in: ``listing`` says which stores each kind has files for."""
    asked: list[tuple] = []

    def fetch(slug, kind, work, files, timeout, store=None, candidates=1):  # noqa: ANN001
        asked.append((kind, store, candidates))
        have = listing[kind]
        if store is not None and store not in have:
            return {"kind": kind, "error": f"no file downloaded for store {store}"}
        code = store if store is not None else min(have)
        return {"kind": kind, "file": f"{kind}-{code:03}.gz", "store_code": f"{code:03}"}

    return fetch, asked


def test_the_price_file_is_fetched_for_the_promo_files_store(tmp_path: Path) -> None:
    fetch, asked = _fake_fetch({"stores": {0}, "promo_full": {310}, "price_full": {36, 310}})
    got = portal_probe.fetch_chain("shufersal", tmp_path, tmp_path, 5, fetch=fetch)
    assert list(got) == ["stores", "price_full", "promo_full"]  # the order of KINDS
    assert asked == [
        ("stores", None, 1),
        ("promo_full", None, portal_probe.PROMO_CANDIDATES),  # the largest of ten
        ("price_full", 310, 1),  # and the PriceFull of that store
    ]
    assert got["price_full"]["file"] == "price_full-310.gz"
    assert got["price_full"]["same_store"] is True


def test_the_first_price_file_is_the_fallback_and_says_it_is_another_store(
    tmp_path: Path,
) -> None:
    fetch, asked = _fake_fetch({"stores": {0}, "promo_full": {9}, "price_full": {1, 2}})
    got = portal_probe.fetch_chain("yohananof", tmp_path, tmp_path, 5, fetch=fetch)
    assert asked[-2:] == [("price_full", 9, 1), ("price_full", None, 1)]
    assert got["price_full"]["file"] == "price_full-001.gz"
    assert got["price_full"]["same_store"] is False
    assert got["price_full"]["wanted_store"] == 9


def test_no_promo_file_means_an_unfiltered_price_file(tmp_path: Path) -> None:
    def fetch(slug, kind, work, files, timeout, store=None, candidates=1):  # noqa: ANN001
        if kind == "promo_full":
            return {"kind": kind, "error": "no file downloaded"}
        assert store is None
        return {"kind": kind, "file": f"{kind}.gz", "store_code": "004"}

    got = portal_probe.fetch_chain("victory", tmp_path, tmp_path, 5, fetch=fetch)
    assert got["price_full"]["same_store"] is False
    assert "wanted_store" not in got["price_full"]
    assert "error" in got["promo_full"]


def test_fetch_fixtures_passes_the_store_and_keeps_the_largest_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    from smartcart_ingest.adapters import fetch_fixtures

    small = "PromoFull7290027600007-001-001-20261021-043100.gz"
    big = "PromoFull7290027600007-001-310-20261021-043100.gz"
    calls: list[tuple] = []

    async def fake_download(scraper_name, kind, workdir, limit=1, store_id=None):  # noqa: ANN001
        calls.append((limit, store_id))
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / small).write_bytes(b"x")
        (workdir / big).write_bytes(b"x" * 50)
        return [workdir / small, workdir / big]

    monkeypatch.setattr(fetch_fixtures, "_download", fake_download)
    entry = fetch_fixtures.fetch(
        "shufersal", "SHUFERSAL", "promo_full", tmp_path, store_id=310, candidates=10
    )
    assert calls == [(10, 310)]
    assert entry["file"] == big and entry["store_code"] == "310"
    # without candidates the newest usable file wins, as before, and no store is asked for
    calls.clear()
    fetch_fixtures.fetch("shufersal", "SHUFERSAL", "promo_full", tmp_path / "b")
    assert calls == [(1, None)]


# --- the shelf check ---------------------------------------------------------------------------


class _Adapter:
    def __init__(self, stores: list[str]) -> None:
        self.stores = stores

    def raw_file_for(self, name, data):  # noqa: ANN001
        return name

    def parse(self, raw, data):  # noqa: ANN001
        prices = [SimpleNamespace(store_code=s, item_code=f"i{n}", price=10 + n)
                  for n, s in enumerate(self.stores)]  # fmt: skip
        return SimpleNamespace(prices=prices)


def test_shelf_prices_only_when_both_files_are_for_one_store(tmp_path: Path) -> None:
    price = tmp_path / "PriceFull"
    price.write_bytes(b"x")
    promos = SimpleNamespace(promos=[SimpleNamespace(store_code="310")])
    shelf, info = portal_probe._shelf_prices(_Adapter(["36", "36"]), promos, price)
    assert shelf is None and info["checked"] is False
    assert info["promo_stores"] == ["310"] and info["price_stores"] == ["36"]
    assert "another store" in info["why"]
    shelf, info = portal_probe._shelf_prices(_Adapter(["310", "310"]), promos, price)
    assert shelf == {"i0": 10, "i1": 11} and info["checked"] is True
    assert portal_probe._shelf_prices(_Adapter(["310"]), promos, None)[0] is None


def test_the_shelf_check_counts_one_group_and_pair_promotions() -> None:
    """Rami Levy's committed files are for one store: the prices are checked against its shelf."""
    prof = _profile("ramilevy")
    assert prof["shelf"]["checked"] is True
    assert prof["shelf"]["promo_stores"] == prof["shelf"]["price_stores"]
    check = prof["shapes"]["shelf_check"]
    assert check["single_items_with_shelf"] >= 1
    assert check["single_unit_within_rate_rounding"] == check["single_items_with_shelf"]
    assert check["single_unit_below_shelf"] == check["single_items_with_shelf"]
    assert check["mismatches"] == []


def test_a_whole_percent_rate_is_within_its_rounding() -> None:
    from collections import Counter

    check: Counter = Counter()
    bad: list = []
    # 83.90 at "11 %" is 74.67; the file says 74.90 (a rate of 10.7 rounded to 11)
    item = {"itemcode": "1", "minqty": "1.00", "discountrate": "11", "discountedprice": "74.90"}
    portal_probe._single_check([item], {"1": "83.90"}, check, bad, "p")
    assert check["single_items_with_shelf"] == 1
    assert check["single_unit_equals_shelf_x_rate"] == 0
    assert check["single_unit_within_rate_rounding"] == 1 and bad == []
    # a bundle: 3 for 30 at "10 %" on a 12.00 shelf (10.80 per unit), a real mismatch
    bundle = {"itemcode": "2", "minqty": "3", "discountrate": "10", "discountedprice": "30"}
    portal_probe._single_check([bundle], {"2": "12.00"}, check, bad, "q")
    assert check["single_unit_within_rate_rounding"] == 1 and len(bad) == 1
    # weighed and all-zeros rows are not checked
    weighed = {**item, "bisweighted": "1"}
    wild = {**item, "itemcode": "0000000000000"}
    portal_probe._single_check(
        [weighed, wild], {"1": "83.90", "0000000000000": "1"}, check, bad, "r"
    )
    assert check["single_items_with_shelf"] == 2


def test_the_report_has_a_shelf_section() -> None:
    files = {
        "shufersal": {"promo_full": {"parse": {"profile": {
            "shelf": {"checked": False, "promo_stores": ["310"], "price_stores": ["36"],
                      "why": "the PriceFull is for another store than the PromoFull"},
        }}}},
        "ramilevy": {"promo_full": {"parse": {"profile": {
            "shelf": {"checked": True, "promo_stores": ["1"], "price_stores": ["1"]},
            "shapes": {"shelf_check": {
                "single_items_with_shelf": 10, "single_unit_equals_shelf_x_rate": 9,
                "single_unit_within_rate_rounding": 10, "single_unit_below_shelf": 10,
                "items_with_shelf": 4, "reward_equals_shelf_x_rate": 4,
                "trigger_priced": 3, "trigger_equals_shelf": 3,
            }},
        }}}},
    }  # fmt: skip
    md = "\n".join(portal_probe._shelf_section(files, ["shufersal", "ramilevy"]))
    assert "not checked: the PriceFull is for another store" in md
    assert "9 of 10 equal shelf x (1 - rate), 10 within the rate's rounding" in md
    assert "4 of 4 rewards equal shelf x (1 - rate); 3 of 3 priced triggers equal shelf" in md


# --- the club log lines ------------------------------------------------------------------------


def test_the_club_histogram_counts_each_clubid_text_of_the_real_file() -> None:
    clubs = _profile("ramilevy")["clubs"]
    assert clubs["promos"] == 100 and clubs["without_club_id"] == 0
    by_text = {v["text"]: v for v in clubs["values"]}
    assert by_text["0"] == {"text": "0", "n": 98, "rule": "everyone"}
    and_text = "((1=מועדון שיווק   השקמה|1=מועדון לקוחות אשראי))&(3=ישראכרט מגנטי|3=תווי זיכוי מימוש|3=עיגול אגורות)"
    assert by_text[and_text]["n"] == 1
    assert by_text[and_text]["rule"] == (
        "(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)"
    )
    names = dict(map(tuple, clubs["names"]))
    assert names["עיגול אגורות"] == 1 and names["מועדון נטען"] == 1


def test_club_lines_copy_texts_verbatim_and_cut_long_lines() -> None:
    text = "3 - " + " & ".join(f"כרטיס {n}" for n in range(400))  # one very long label
    rows = [{"text": text, "n": 7, "rule": "אחר"}] + [
        {"text": f"1 - מועדון {n}", "n": n, "rule": "x"} for n in range(1, 700)
    ]
    clubs = {"promos": 900, "without_club_id": 0, "distinct_values": len(rows),
             "distinct_names": 0, "values": rows, "names": [["כרטיס 1", 7]]}  # fmt: skip
    lines = portal_probe.club_lines("shufersal", clubs)
    assert lines[0].startswith("PROMO_CLUBS ") and '"distinct_values": 700' in lines[0]
    body = [json.loads(ln.removeprefix("PROMO_CLUBS ")) for ln in lines[1:]]
    value_parts = [b for b in body if "values" in b]
    assert len(value_parts) > 1 and value_parts[0]["part"] == f"1/{len(value_parts)}"
    assert all(len(json.dumps(b, ensure_ascii=False)) < portal_probe.CLUB_LINE_CHARS + 4000
               for b in body)  # fmt: skip
    first = value_parts[0]["values"][0]
    assert first["length"] == len(text) and first["text"] == text[: portal_probe.CLUB_TEXT_CHARS]
    # every other text is whole, in order, and nothing is lost between parts
    kept = [v["text"] for b in value_parts for v in b["values"]][1:]
    assert kept == [r["text"] for r in rows[1:]]
    assert any("names" in b for b in body)
    assert portal_probe.club_lines("x", None) == []


def test_club_atoms_split_a_joined_label() -> None:
    atoms = portal_probe._club_atoms("3 - מועדון א & מועדון ב")
    assert atoms == ["מועדון א", "מועדון ב"]
    assert portal_probe._club_atoms("(1=א|1=ב)") == ["א", "ב"]
    assert portal_probe._club_atoms("0 - כלל הלקוחות") == ["כלל הלקוחות"]


def test_the_manifest_keeps_the_whole_files_clubs_and_shelf_check(tmp_path: Path) -> None:
    """The committed fixture holds the first promotions; the manifest records what the whole
    file held (its ClubID texts and the shelf check), readable from the fixtures branch."""
    name = "PromoFull7290058140886-001-001-20261021-001146.gz"
    profile = {
        "clubs": {"promos": 2660, "values": [{"text": "0", "n": 2600, "rule": "everyone"}]},
        "shelf": {"checked": True, "promo_stores": ["1"], "price_stores": ["1"]},
        "shapes": {"shelf_check": {"single_items_with_shelf": 5}},
    }
    gate_json = {
        "probe": {"chains": {"ramilevy": {"downloads": {"price_full": {"same_store": True}}}}},
        "files": {"ramilevy": {
            "promo_full": {"file": name, "parse": {"schema": "v1", "promos": 2660,
                                                   "profile": profile},
                           "gate": {"status": "loaded"}},
            "price_full": {"file": "PriceFull7290058140886-001-001-20261021-001002.gz",
                           "parse": {"schema": "v1"}, "gate": {"status": "loaded"}},
        }},
    }  # fmt: skip
    files = tmp_path / "files"
    (files / "ramilevy").mkdir(parents=True)
    for f in (FIXTURES / "ramilevy" / "real").glob("*Full*"):
        (files / "ramilevy" / f.name).write_bytes(f.read_bytes())
    out = tmp_path / "out"
    portal_probe.build_fixtures(files, gate_json, out, 5, max_promos=3)
    manifest = json.loads((out / "ramilevy" / "real" / "MANIFEST.json").read_text("utf-8"))
    by_kind = {e["kind"]: e for e in manifest["files"]}
    assert by_kind["promo_full"]["full_file"] == {
        "promos": 2660, "clubs": profile["clubs"], "shelf": profile["shelf"],
        "shelf_check": {"single_items_with_shelf": 5},
    }  # fmt: skip
    assert by_kind["price_full"]["same_store_as_promo"] is True


# --- the reachability column -------------------------------------------------------------------


def test_reachability_reports_what_was_actually_reachable() -> None:
    cerberus = {
        "http_status": 0, "reachable": "UNREACHABLE", "login": "ok (certificate not verified)",
        "downloads": {"stores": {"file": "S.xml"}, "price_full": {"file": "P.gz"},
                      "promo_full": {"error": "timed out"}},
    }  # fmt: skip
    got = portal_probe.reachability(cerberus)
    assert got == "OK (files downloaded: 2 of 3; HTTP root 0)"
    # the login alone, before (or without) any download
    none = portal_probe.reachability({**cerberus, "downloads": {}})
    assert none == "OK (FTP login passes; HTTP root 0)"
    # King Store: the root answers 403, the files download
    king = {
        "http_status": 403, "reachable": "BLOCKED?", "login": "n/a",
        "downloads": {"stores": {"file": "S.gz"}, "price_full": {"file": "P.gz"},
                      "promo_full": {"file": "R.gz"}},
    }  # fmt: skip
    assert portal_probe.reachability(king) == "OK (files downloaded: 3 of 3; HTTP root 403)"
    # nothing came: the root's own verdict stays (Victory, Hazi Hinam from a cloud runner)
    blocked = {"http_status": 403, "reachable": "BLOCKED?", "login": "n/a",
               "downloads": {"stores": {"error": "no file downloaded"}}}  # fmt: skip
    assert portal_probe.reachability(blocked) == "BLOCKED? (403)"
    failed = {"http_status": 0, "reachable": "UNREACHABLE", "login": "failed: timeout"}
    assert portal_probe.reachability(failed) == "UNREACHABLE (0)"
    # a root that answers is reported as it is
    assert portal_probe.reachability({"http_status": 200, "reachable": "OK"}) == "OK (200)"


def test_the_probe_table_uses_the_reachability_column() -> None:
    probe = {
        "runner": "r", "started_at": "a", "finished_at": "b",
        "chains": {"tivtaam": {"http_status": 0, "reachable": "UNREACHABLE", "login": "ok",
                               "downloads": {"promo_full": {"file": "x.gz"}}}},
    }  # fmt: skip
    md = portal_probe.render(probe, {"files": {"tivtaam": {}}, "alerts": []}, ["tivtaam"])
    assert "| Tiv Taam | OK (files downloaded: 1 of 1; HTTP root 0) | ok |" in md
    assert "UNREACHABLE" not in md
