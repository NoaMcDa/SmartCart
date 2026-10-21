"""Tests for the real-fixture path of the portal probe: trimming, the manifest, the log lines.

uv run pytest scripts/unblock/tests -q
"""

from __future__ import annotations

import gzip
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import portal_probe  # noqa: E402

FIXTURES = REPO / "services" / "ingest" / "tests" / "fixtures"
VICTORY_PF = FIXTURES / "victory" / "PriceFull7290696200003-001-202610060300.xml.gz"
VICTORY_STORES = "Stores7290696200003-000-202610060100.xml.gz"


def _parse(name: str, data: bytes):
    from smartcart_ingest.adapters.victory import VictoryAdapter

    adapter = VictoryAdapter()
    return adapter.parse(adapter.raw_file_for(name, data), data)


def test_trim_keeps_header_encoding_and_container() -> None:
    from smartcart_ingest import xmlutil
    from smartcart_ingest.adapters.fetch_fixtures import trim_price_file

    data = VICTORY_PF.read_bytes()
    out, before, after = trim_price_file(data, 3)
    assert (before, after) == (8, 3)
    assert out[:2] == b"\x1f\x8b"  # still gzip
    payload, _ = xmlutil.unwrap(out)
    assert payload.startswith(b'<?xml version="1.0" encoding="windows-1255"?>')
    assert xmlutil.detect_encoding(payload) == "windows-1255"
    full, trimmed = _parse(VICTORY_PF.name, data), _parse(VICTORY_PF.name, out)
    assert len(trimmed.prices) == 3
    assert trimmed.prices == full.prices[:3]  # the first rows, unchanged
    assert trimmed.items == full.items[:3]  # Hebrew names survive the round trip
    assert trim_price_file(data, 50) == (data, 8, 8)  # nothing to trim: bytes untouched


def test_trim_utf16_with_bom_in_a_zip_and_updates_count() -> None:
    from smartcart_ingest import xmlutil
    from smartcart_ingest.adapters.fetch_fixtures import trim_price_file

    text = gzip.decompress(VICTORY_PF.read_bytes()).decode("windows-1255")
    text = text.replace('encoding="windows-1255"', 'encoding="UTF-16"')
    text = text.replace("<Products>", '<Products Count="8">')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PriceFull.xml", b"\xff\xfe" + text.encode("utf-16-le"))
    out, before, after = trim_price_file(buf.getvalue(), 2)
    assert (before, after) == (8, 2)
    assert out[:4] == b"PK\x03\x04"
    payload, _ = xmlutil.unwrap(out)
    assert payload.startswith(b"\xff\xfe")
    decoded = payload[2:].decode("utf-16-le")
    assert decoded.startswith('<?xml version="1.0" encoding="UTF-16"?>')
    assert '<Products Count="2">' in decoded
    assert len(_parse(VICTORY_PF.name, out).prices) == 2


def test_trim_refuses_a_file_without_price_rows() -> None:
    from smartcart_ingest.adapters.fetch_fixtures import trim_price_file

    with pytest.raises(ValueError, match="no price rows"):
        trim_price_file((FIXTURES / "victory" / VICTORY_STORES).read_bytes(), 3)
    with pytest.raises(ValueError, match="not a readable XML"):
        trim_price_file(b"\x1f\x8bnot gzip", 3)


def test_build_fixtures_writes_real_dir_and_manifest(tmp_path: Path) -> None:
    gate_json = {
        "probe": {"chains": {"victory": {"downloads": {
            "stores": {"fetched_at": "2026-10-08T07:20:00+00:00"},
            "price_full": {"fetched_at": "2026-10-08T07:21:00+00:00"}}}}},
        "files": {
            "victory": {
                "stores": {"file": VICTORY_STORES, "published_at": "2026-10-06T01:00+03:00",
                           "parse": {"schema": "v1", "stores": 4},
                           "gate": {"status": "loaded", "gates": [], "reason": "items=4"}},
                "price_full": {"file": VICTORY_PF.name, "published_at": "2026-10-06T03:00+03:00",
                               "parse": {"schema": "v1", "items": 8},
                               "gate": {"status": "quarantined", "gates": ["stale_date"],
                                        "reason": "stale_date: 54 h old"}}},
            "shufersal": {"price_full": {"file": "x.gz", "parse": {"error": "AdapterError"}}},
        },
    }  # fmt: skip
    made = portal_probe.build_fixtures(FIXTURES, gate_json, tmp_path, 5)
    assert list(made) == ["victory"]
    real = tmp_path / "victory" / "real"
    assert sorted(p.name for p in real.iterdir()) == sorted(
        ["MANIFEST.json", VICTORY_STORES, VICTORY_PF.name]
    )
    assert (real / VICTORY_STORES).read_bytes() == (
        FIXTURES / "victory" / VICTORY_STORES
    ).read_bytes()
    manifest = json.loads((real / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["chain_id"] == "7290696200003" and manifest["max_items"] == 5
    pf = next(e for e in manifest["files"] if e["kind"] == "price_full")
    assert (pf["items_original"], pf["items_trimmed"], pf["parsed"]["prices"]) == (8, 5, 5)
    assert pf["source_file"] == VICTORY_PF.name
    assert pf["fetched_at"] == "2026-10-08T07:21:00+00:00"
    assert pf["published_at"] == "2026-10-06T03:00+03:00"
    assert pf["gate"] == {"status": "quarantined", "gates": ["stale_date"],
                          "reason": "stale_date: 54 h old"}  # fmt: skip
    assert pf["sha256_original"] != pf["sha256"]
    st = next(e for e in manifest["files"] if e["kind"] == "stores")
    assert st["sha256_original"] == st["sha256"] and st["stores"] == 4
    assert not (tmp_path / "shufersal").exists()  # the adapter rejected it: nothing written


def test_result_line_is_one_untruncated_json_line() -> None:
    reason = "parse failed: " + "x" * 600
    entry = {
        "file": "PriceFull7290058140886-039-202610080300.gz", "bytes": 10,
        "parse": {"schema": "v1", "items": 4512, "prices": 4512},
        "gate": {"status": "quarantined", "gates": ["zero_price"], "reason": reason},
    }  # fmt: skip
    line = portal_probe.result_line("ramilevy", "price_full", entry)
    assert line.startswith("RESULT {") and "\n" not in line
    data = json.loads(line[len("RESULT ") :])
    assert data["items"] == 4512 and data["gates"] == "zero_price" and data["reason"] == reason
    assert data["status"] == "quarantined" and data["schema"] == "v1"


# --- PromoFull: trimming whole promotions, the profile, the manifest ------------------------------------

SHUFERSAL_PROMO = FIXTURES / "shufersal" / "PromoFull7290027600007-001-202610060300.gz"
VICTORY_PROMO = FIXTURES / "victory" / "PromoFull7290696200003-001-202610060300.xml.gz"


def _parse_any(adapter_cls, name: str, data: bytes):
    adapter = adapter_cls()
    return adapter.parse(adapter.raw_file_for(name, data), data)


def test_trim_promo_keeps_whole_nested_promotions() -> None:
    from smartcart_ingest.adapters.fetch_fixtures import trim_promo_file
    from smartcart_ingest.adapters.shufersal import ShufersalAdapter

    data = SHUFERSAL_PROMO.read_bytes()
    full = _parse_any(ShufersalAdapter, SHUFERSAL_PROMO.name, data)
    out, before, after = trim_promo_file(data, 2)
    assert (before, after) == (len(full.promos), 2)
    trimmed = _parse_any(ShufersalAdapter, SHUFERSAL_PROMO.name, out)
    # Evenly spaced over the file (indexes 0 and 2 of 4), each with all its items.
    assert trimmed.promos == [full.promos[0], full.promos[2]]
    assert out[:2] == b"\x1f\x8b"
    assert trim_promo_file(data, 50) == (data, before, before)  # nothing to trim: untouched


def test_trim_promo_keeps_every_row_of_a_flat_sale_promotion() -> None:
    """Victory's legacy layout has one <Sale> row per item, grouped by PromotionID."""
    from smartcart_ingest.adapters.fetch_fixtures import trim_promo_file
    from smartcart_ingest.adapters.victory import VictoryAdapter

    data = VICTORY_PROMO.read_bytes()
    full = _parse_any(VictoryAdapter, VICTORY_PROMO.name, data)
    assert any(len(p.item_codes) > 1 for p in full.promos)
    out, before, after = trim_promo_file(data, 1)
    assert (before, after) == (len(full.promos), 1)
    trimmed = _parse_any(VictoryAdapter, VICTORY_PROMO.name, out)
    assert len(trimmed.promos) == 1
    assert trimmed.promos[0] == full.promos[0]  # all of its item rows kept


def test_trim_promo_refuses_a_price_file() -> None:
    from smartcart_ingest.adapters.fetch_fixtures import trim_promo_file

    with pytest.raises(ValueError, match="no promotion rows"):
        trim_promo_file(VICTORY_PF.read_bytes(), 3)


def test_promo_layout_counts_elements_and_samples_rows() -> None:
    from smartcart_ingest.adapters.fetch_fixtures import promo_layout

    layout = promo_layout(SHUFERSAL_PROMO.read_bytes(), sample=2)
    assert layout["row_tags"] == ["Promotion"] and layout["rows"] >= 2
    assert layout["children"]["RewardType"] == layout["rows"]
    assert layout["nested"]["PromotionItems/Item"] >= layout["rows"]
    assert layout["nested"]["PromotionItems/Item/ItemCode"] >= layout["rows"]
    assert len(layout["samples"]) == 2
    assert layout["samples"][0]["PromotionItems"]["Item"]["ItemCode"]
    with pytest.raises(ValueError, match="not a readable XML"):
        promo_layout(b"\x1f\x8bnot gzip")


def test_promo_profile_summarises_what_the_adapter_read() -> None:
    from smartcart_ingest.adapters.shufersal import ShufersalAdapter

    data = SHUFERSAL_PROMO.read_bytes()
    adapter = ShufersalAdapter()
    summary = portal_probe.parse_summary(adapter, SHUFERSAL_PROMO)
    assert summary["promos"] == sum(summary["reward_types"].values())
    profile = summary["profile"]
    assert profile["promos"] == summary["promos"]
    assert profile["fields"]["rewardtype"] == {"1": summary["promos"]}
    assert profile["confidence"] and profile["samples"] and profile["layout_samples"]
    assert profile["items_per_promo"]["min"] >= 1
    json.dumps(profile, ensure_ascii=False)  # all of it is plain data
    parsed = _parse_any(ShufersalAdapter, SHUFERSAL_PROMO.name, data)
    assert profile["club_only"] == sum(1 for p in parsed.promos if p.club_only)


def test_build_fixtures_trims_promo_full_whole_promotions(tmp_path: Path) -> None:
    gate_json = {
        "files": {"shufersal": {"promo_full": {
            "file": SHUFERSAL_PROMO.name, "published_at": "2026-10-06T03:00+03:00",
            "parse": {"schema": "v1", "promos": 4},
            "gate": {"status": "loaded", "gates": [], "reason": "items=4"}}}},
    }  # fmt: skip
    made = portal_probe.build_fixtures(FIXTURES, gate_json, tmp_path, 5, max_promos=2)
    assert list(made) == ["shufersal"]
    manifest = json.loads(
        (tmp_path / "shufersal" / "real" / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["max_promos"] == 2
    entry = manifest["files"][0]
    assert entry["kind"] == "promo_full"
    assert (entry["promos_original"], entry["promos_trimmed"]) == (4, 2)
    assert entry["parsed"]["promos"] == 2
    assert entry["sha256_original"] != entry["sha256"]


def test_result_line_and_report_carry_promo_rows() -> None:
    entry = {
        "file": "PromoFull7290027600007-001-202610080300.gz", "bytes": 900,
        "published_at": "2026-10-08T03:00+03:00",
        "parse": {"schema": "v1", "promos": 40, "promo_item_codes": 90, "club_only": 7,
                  "reward_types": {"bundle": 20, "other": 20},
                  "profile": {"promos": 40, "confidence": {1.0: 20, 0.1: 20},
                              "expired_at_publication": 1, "not_started_at_publication": 2}},
        "gate": {"status": "loaded", "reason": "items=40", "gates": [], "schema": "v1"},
        "db": {"promos": 40, "promo_items": 80},
    }  # fmt: skip
    line = portal_probe.result_line("shufersal", "promo_full", entry)
    data = json.loads(line[len("RESULT ") :])
    assert data["promos"] == 40 and data["promos_loaded"] == 40 and data["promo_items_linked"] == 80
    assert data["reward_types"] == {"bundle": 20, "other": 20} and data["club_only"] == 7
    gate = {"files": {"shufersal": {"promo_full": entry}}, "alerts": []}
    md = portal_probe.render(None, gate, ["shufersal"])
    assert "PromoFull file" in md and "40 promos (7 club-only)" in md
    assert "### PromoFull files as the adapter read them" in md
    assert "bundle 20, other 20" in md and "20 of 40" in md and "10 unknown items skipped" in md


def test_fetch_asks_for_ten_files_when_the_first_one_is_unusable(
    tmp_path: Path, monkeypatch
) -> None:
    """Yohananof's portal lists a stale ``PromoFull0000000000000-...`` first (chain id all zeros):
    ``fetch`` then asks for ten files and takes the newest one the adapter accepts."""
    from smartcart_ingest.adapters import fetch_fixtures

    junk = "PromoFull0000000000000-00-1-202411010501.gz"
    older = "PromoFull7290803800003-000-001-20261020-004031.gz"
    newer = "PromoFull7290803800003-000-001-20261021-004031.gz"
    asked: list[int] = []

    async def fake_download(scraper_name: str, kind: str, workdir: Path, limit: int = 1):
        asked.append(limit)
        names = [junk] if limit == 1 else [junk, older, newer]
        workdir.mkdir(parents=True, exist_ok=True)
        out = []
        for name in names:
            (workdir / name).write_bytes(b"not parsed here")
            out.append(workdir / name)
        return out

    monkeypatch.setattr(fetch_fixtures, "_download", fake_download)
    entry = fetch_fixtures.fetch("yohananof", "YOHANANOF", "promo_full", tmp_path / "out")
    assert asked == [1, 10]
    assert entry["file"] == newer  # not the stale junk file, not the older real one
    assert (tmp_path / "out" / "yohananof" / newer).exists()


def test_fetch_keeps_one_file_when_the_first_is_usable(tmp_path: Path, monkeypatch) -> None:
    from smartcart_ingest.adapters import fetch_fixtures

    good = "PromoFull7290803800003-000-001-20261021-004031.gz"
    asked: list[int] = []

    async def fake_download(scraper_name: str, kind: str, workdir: Path, limit: int = 1):
        asked.append(limit)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / good).write_bytes(b"x")
        return [workdir / good]

    monkeypatch.setattr(fetch_fixtures, "_download", fake_download)
    assert fetch_fixtures.fetch("yohananof", "YOHANANOF", "promo_full", tmp_path)["file"] == good
    assert asked == [1]


def test_promo_shapes_describes_multi_group_promotions() -> None:
    real = FIXTURES / "tivtaam" / "real" / "PromoFull7290873255550-000-002-20261021-004004.gz"
    shapes = portal_probe.promo_shapes(real.read_bytes())
    assert sum(shapes["signatures"].values()) == 3  # the three two-group promotions of the file
    assert any("[rt=0 q=1 r=-][rt=1 q=1 r=100]" in sig for sig in shapes["signatures"])
    assert shapes["days"] == {"(empty)": 100}
    json.dumps(shapes, ensure_ascii=False)  # plain data, printable as a log line
