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
