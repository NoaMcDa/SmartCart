"""Tests for the scripts behind the unblock workflows (no network, no database).

    uv run pytest scripts/unblock/tests -q

The database paths (``bge_eval.py``, ``portal_probe.py gate``, ``extraction_pilot.py``) are run
end to end against a throwaway Postgres as described in docs/unblock.md.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import bge_eval  # noqa: E402
import extraction_pilot  # noqa: E402
import portal_probe  # noqa: E402
import supabase_provision  # noqa: E402

# --- bge_eval ----------------------------------------------------------------------------------------


def _rows(spec: dict[str, int]) -> list[dict[str, str]]:
    rows = []
    for cat, n in spec.items():
        for i in range(n):
            for label in ("exact", "no_match"):
                rows.append({"item_key": f"{cat}-{i}", "category": cat, "label": label})
    return rows


def test_sample_items_round_robin_and_deterministic() -> None:
    rows = _rows({"dairy": 5, "bakery": 1, "drinks": 3})
    chosen = bge_eval.sample_items(rows, 5)
    assert chosen == ["dairy-0", "bakery-0", "drinks-0", "dairy-1", "drinks-1"]
    assert bge_eval.sample_items(rows, 5) == chosen
    assert len(bge_eval.sample_items(rows, 100)) == 9


def test_write_subset_keeps_every_pair_of_the_sampled_items(tmp_path: Path) -> None:
    info = bge_eval.write_subset(REPO / "data" / "gold", tmp_path, 40)
    assert info["items"] == 40
    with (tmp_path / "gold_pairs.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len({r["item_key"] for r in rows}) == 40
    assert len(rows) == info["pairs"] > 40  # hard negatives come along with each item
    cats = {r["category"] for r in rows}
    assert len(cats) > 5  # round robin reaches many departments
    assert (tmp_path / "gold_catalog.yaml").read_bytes() == (
        REPO / "data" / "gold" / "gold_catalog.yaml"
    ).read_bytes()


def test_model_revision_reads_the_hub_cache(tmp_path: Path) -> None:
    ref = tmp_path / "models--BAAI--bge-m3" / "refs"
    ref.mkdir(parents=True)
    (ref / "main").write_text("5617a9f61b028005a4858fdac845db406aefb181\n")
    assert bge_eval.model_revision("BAAI/bge-m3", tmp_path) == (
        "5617a9f61b028005a4858fdac845db406aefb181"
    )
    assert bge_eval.model_revision("BAAI/other", tmp_path) is None
    assert bge_eval.model_revision("hash-ngram-2-3-4-v1", tmp_path) is None


def _metrics(p_any: float | None, r_any: float, rak: float) -> dict:
    return {
        "precision": {"exact": 1.0, "any_brand": p_any, "close": 0.97},
        "recall": {"exact": 1.0, "any_brand": r_any, "close": 0.7},
        "recall_at_k": rak,
        "support": {
            "items": 857,
            "pairs": 2523,
            "served": 600,
            "review": 200,
            "unmapped": 57,
            "any_brand": 672,
            "predicted_any_brand": 500,
        },  # fmt: skip
        "embedder": "BAAI/bge-m3",
        "judge": "rule-v1",
    }


def test_gate_lines_compare_without_enforcing() -> None:
    below = bge_eval.gate_lines(_metrics(0.95, 0.7, 0.9), 10, 0.98)
    assert "below the gate" in below[0] and "not enforced" in below[0]
    assert "plan fine-tuning" in below[1]
    assert "below" in below[2]
    above = bge_eval.gate_lines(_metrics(0.99, 0.85, 0.99), 10, 0.98)
    assert "meets the gate" in above[0] and "above" in above[1] and "above" in above[2]
    assert "n/a" in bge_eval.gate_lines(_metrics(None, 0.0, 0.5), 10, 0.98)[0]


def test_render_names_the_model_revision_and_baseline() -> None:
    result = {
        "embedder": "bge-m3", "embedder_model": "BAAI/bge-m3", "model_revision": "abc123",
        "judge": "rule-v1", "k": 10, "threshold": 0.98,
        "gold": {"items": 857, "items_total": 857, "sampled": False},
        "embed": {"seconds": 41.2, "canonicals": 58, "items": 857}, "evaluate_seconds": 12.0,
        "metrics": _metrics(0.99, 0.8, 0.97), "baseline": _metrics(1.0, 0.81, 0.9988),
        "versions": {"sentence-transformers": "6.1.0", "torch": "2.14.1"},
        "commit": "deadbeef", "finished_at": "2026-10-08T00:00:00+00:00",
    }  # fmt: skip
    md = bge_eval.render(result)
    assert "`abc123`" in md and "41.2 s for 58 canonicals and 857 items" in md
    assert "precision (hash)" in md and "**synthetic**" in md
    assert "| any_brand | 0.9900 | 0.8000 |" in md


# --- portal_probe ------------------------------------------------------------------------------------


def test_the_ten_d13_chains_have_a_portal_and_an_adapter() -> None:
    from smartcart_ingest.adapters.fetch_fixtures import adapters_by_slug

    assert len(portal_probe.PORTALS) == 10
    assert set(portal_probe.BY_SLUG) == set(adapters_by_slug())
    cerberus = {p.slug for p in portal_probe.PORTALS if p.ftp_user}
    assert cerberus == {"ramilevy", "tivtaam", "osherad", "yohananof"}


@pytest.mark.parametrize(
    ("code", "label"),
    [(0, "UNREACHABLE"), (403, "BLOCKED?"), (429, "BLOCKED?"), (200, "OK"), (302, "OK"),
     (206, "OK"), (404, "REACHABLE"), (503, "ERROR")],
)  # fmt: skip
def test_classify_matches_check_portals(code: int, label: str) -> None:
    assert portal_probe.classify(code) == label


def test_pick_files_takes_the_newest_stores_and_price_full() -> None:
    from smartcart_ingest.adapters.victory import VictoryAdapter

    picked = portal_probe.pick_files(REPO / "services" / "ingest" / "tests" / "fixtures",
                                     "victory", VictoryAdapter())  # fmt: skip
    assert set(picked) == {"stores", "price_full"}
    assert picked["stores"].name.startswith("Stores")
    assert picked["price_full"].name.startswith("PriceFull")


def test_render_probe_table() -> None:
    probe = {
        "runner": "GitHub Actions 1", "started_at": "a", "finished_at": "b",
        "chains": {
            "ramilevy": {"http_status": 200, "reachable": "OK", "login": "ok",
                         "downloads": {"stores": {"kind": "stores", "file": "Stores1.xml"},
                                       "price_full": {"kind": "price_full",
                                                      "error": "no file downloaded",
                                                      "log_tail": "x\nConnectionRefused"}}},
            "victory": {"http_status": 403, "reachable": "BLOCKED?", "login": "n/a",
                        "downloads": {}},
        },
    }  # fmt: skip
    gate = {
        "files": {"ramilevy": {"stores": {
            "file": "Stores7290058140886-202610080100.xml", "bytes": 2048,
            "published_at": "2026-10-08T01:00+03:00",
            "parse": {"schema": "v1", "stores": 60, "online_stores": 1, "items": 0, "prices": 0},
            "gate": {"status": "loaded", "reason": "items=60", "gates": [], "schema": "v1"},
        }}, "victory": {}},
        "alerts": [],
    }  # fmt: skip
    md = portal_probe.render(probe, gate, ["ramilevy", "victory"])
    assert "| Rami Levy | OK (200) | ok | `Stores7290058140886-202610080100.xml` 2 KB" in md
    assert "60 stores (1 online)" in md and "| loaded |" in md and "| v1 |" in md
    assert "| Victory | BLOCKED? (403) | n/a |" in md
    assert "Download errors (1)" in md and "ConnectionRefused" in md


def test_gate_cell_lists_the_failed_gates() -> None:
    cell = portal_probe._gate_cell({"gate": {"status": "quarantined",
                                             "gates": ["stale_date", "zero_price"]}})  # fmt: skip
    assert cell == "quarantined (stale_date, zero_price)"


# --- fetch_fixtures extension --------------------------------------------------------------------------


def test_fetch_plan_filters_kinds() -> None:
    from smartcart_ingest.adapters.fetch_fixtures import plan

    steps = plan(["victory", "shufersal"], ["price_full", "stores"])
    assert [(s, k) for s, _, k in steps] == [
        ("victory", "stores"), ("victory", "price_full"),
        ("shufersal", "stores"), ("shufersal", "price_full"),
    ]  # fmt: skip
    with pytest.raises(SystemExit):
        plan(["victory"], ["prices"])


# --- extraction_pilot ----------------------------------------------------------------------------------


def test_compare_rows_counts_each_case() -> None:
    model = {1: {"product_type": "milk", "fat_pct": 3, "brand": "תנובה", "diet_flags": ["x"]},
             2: {"product_type": "yogurt", "state": "chilled"}}  # fmt: skip
    rule = {1: {"product_type": "milk", "fat_pct": 3.0, "diet_flags": ["x"]},
            2: {"product_type": "cheese", "flavor": "natural"}}  # fmt: skip
    res = extraction_pilot.compare_rows(model, rule)
    pk = res["per_key"]
    assert pk["product_type"] == {"agree": 1, "differ": 1}
    assert pk["fat_pct"] == {"agree": 1, "neither": 1}  # 3 == 3.0
    assert pk["brand"] == {"model_only": 1, "neither": 1}
    assert pk["flavor"] == {"rule_only": 1, "neither": 1}
    assert pk["diet_flags"] == {"agree": 1, "neither": 1}
    assert res["diffs"] == [{"item_id": 2, "key": "product_type", "model": "yogurt",
                             "rule": "cheese"}]  # fmt: skip


def test_render_pilot_report() -> None:
    res = {
        "model_extractor": "claude", "model": "claude-sonnet-5-5", "items": 2,
        "statuses": {"ok": 2}, "mean_confidence": 0.9,
        "per_key": {"product_type": {"agree": 1, "differ": 1}},
        "diffs": [{"item_id": 2, "key": "product_type", "model": "yogurt", "rule": "cheese",
                   "raw_name": "יוגורט | 3%"}],
        "cost": {"batches": 1, "requests": 2, "input_tokens": 100, "output_tokens": 50,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                 "estimated_usd": "0.0004", "estimated_usd_per_item": "0.00020"},
        "commit": "x", "finished_at": "y",
    }  # fmt: skip
    md = extraction_pilot.render(res)
    assert "| product_type | 1 | 1 | 50% |" in md
    assert "**$0.0004**" in md and "$0.00020 per item" in md
    assert "יוגורט \\| 3%" in md  # a pipe in a name cannot break the table


def test_spend_cap() -> None:
    assert extraction_pilot.main(["check-limit", "200"]) == 0
    assert extraction_pilot.main(["check-limit", "0"]) == 2
    assert extraction_pilot.main(["check-limit", "1001"]) == 2


# --- supabase_provision --------------------------------------------------------------------------------


class FakeApi:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = statuses
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, path: str, body: dict | None):
        self.calls.append((method, path, body))
        if (method, path) == ("POST", "/v1/projects"):
            return {"id": "abcdefghij", "status": "COMING_UP"}
        if path.endswith("/database/query"):
            return [{"extname": "pg_trgm"}, {"extname": "postgis"}, {"extname": "vector"}]
        if path.endswith("/pooler"):
            return [{"pool_mode": "transaction", "connection_string":
                     "postgresql://postgres.abcdefghij:[YOUR-PASSWORD]@pooler.example:6543/postgres"}]  # fmt: skip
        return {"status": self.statuses.pop(0)}


def test_provision_creates_waits_enables_and_prints() -> None:
    api = FakeApi(["COMING_UP", "COMING_UP", "ACTIVE_HEALTHY"])
    out = supabase_provision.provision(api, org_id="org", ref=None, name="smartcart",
                                       region="eu-central-1", password="pw",
                                       sleep=lambda s: None)  # fmt: skip
    assert out["ref"] == "abcdefghij"
    assert api.calls[0] == ("POST", "/v1/projects", {"name": "smartcart", "organization_id": "org",
                                                      "region": "eu-central-1", "db_pass": "pw"})  # fmt: skip
    assert [c[1] for c in api.calls[1:4]] == ["/v1/projects/abcdefghij"] * 3
    query = api.calls[4][2]["query"]
    for ext in ("postgis", "vector", "pg_trgm"):
        assert f"create extension if not exists {ext} with schema extensions" in query
    conns = list(out["connections"].values())
    assert conns[0] == ("postgresql://postgres:<password>@db.abcdefghij.supabase.co:5432/"
                        "postgres?sslmode=require")  # fmt: skip
    assert conns[1].endswith(":<password>@pooler.example:6543/postgres?sslmode=require")
    assert all("pw" not in c for c in conns)


def test_provision_existing_ref_and_failed_project() -> None:
    api = FakeApi(["ACTIVE_HEALTHY"])
    supabase_provision.provision(api, org_id=None, ref="r1", name="n", region="x",
                                 password="", sleep=lambda s: None)  # fmt: skip
    assert all(c[0:2] != ("POST", "/v1/projects") for c in api.calls)
    with pytest.raises(SystemExit, match="INIT_FAILED"):
        supabase_provision.provision(FakeApi(["INIT_FAILED"]), org_id="o", ref=None, name="n",
                                     region="x", password="p", sleep=lambda s: None)  # fmt: skip
    with pytest.raises(SystemExit, match="not ready"):
        supabase_provision.provision(FakeApi(["COMING_UP"] * 5), org_id="o", ref=None, name="n",
                                     region="x", password="p", timeout=30, poll=15,
                                     sleep=lambda s: None)  # fmt: skip


def test_dry_run_redacts_the_password() -> None:
    buf = io.StringIO()
    call = supabase_provision.dry_run_transport(buf)
    supabase_provision.provision(call, org_id="org", ref=None, name="smartcart", region="r",
                                 password="secret-pw", sleep=lambda s: None)  # fmt: skip
    text = buf.getvalue()
    assert "secret-pw" not in text and '"db_pass": "<redacted>"' in text
    assert text.splitlines()[0].startswith("POST https://api.supabase.com/v1/projects ")
