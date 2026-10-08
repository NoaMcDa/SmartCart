"""The LLM attribute-extraction pilot (issue #25): prepare the synthetic items, then compare the
model's attributes with the rule extractor's and report the cost. What
``.github/workflows/extraction-pilot.yml`` runs around ``smartcart-catalog extract``:

    DATABASE_URL=... uv run smartcart-ingest migrate && uv run smartcart-catalog seed
    DATABASE_URL=... uv run --no-sync python scripts/unblock/extraction_pilot.py prepare
    DATABASE_URL=... ANTHROPIC_API_KEY=... uv run smartcart-catalog extract \\
        --extractor claude --limit 200 --batch-size 200
    DATABASE_URL=... uv run --no-sync python scripts/unblock/extraction_pilot.py compare \\
        --out extraction-pilot.md --json-out extraction-pilot.json

``prepare`` loads the chains' synthetic transparency fixtures through the real loader and gates
(``scripts/demo/load_fixtures.py``, about 80 items with chain-style names) and then the synthetic gold
set's items (857 template names), so ``extract --limit N`` takes the fixtures first. ``compare``
reads every ``item_attributes`` row written by ``--model-extractor`` (default ``claude``), runs
the rule extractor in memory on the same items (nothing is written), and reports agreement per
attribute, coverage, statuses, sample disagreements and the cost from ``match_runs``. Without a
key it is tested with ``--model-extractor rule`` after ``extract --extractor rule``.

Neither extractor is ground truth: agreement is not accuracy. The disagreement sample is what a
person reads to decide D14.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from _common import REPO, git_sha, md_escape, run, write_text

KEYS = (
    "product_type", "category_path", "state", "fat_pct", "base", "pack_size", "unit", "brand",
    "is_private_label", "flavor", "variety", "kosher", "diet_flags",
)  # fmt: skip
CRITICAL_FIRST = ("product_type", "state", "fat_pct", "base", "pack_size", "unit")
MAX_ITEMS_CAP = 1000  # the runbook's pilot size; a larger run is a decision, not a click

_ROWS = """
SELECT i.id, i.chain_id, c.name AS chain_name, i.item_code, i.barcode, i.raw_name,
       i.manufacturer, i.quantity, i.unit, i.is_weighed,
       a.status, a.attrs, a.confidence, a.model
FROM item_attributes a
JOIN items i ON i.id = a.item_id
LEFT JOIN chains c ON c.id = i.chain_id
WHERE a.extractor = %s
ORDER BY i.id
"""


def _norm(value: Any) -> Any:
    """Comparable form of an attribute value (numbers as Decimal, lists as sorted tuples)."""
    if value is None or value == () or value == []:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value)).normalize()
    if isinstance(value, list | tuple):
        return tuple(sorted(str(v) for v in value))
    if isinstance(value, str):
        return value.strip().lower() or None
    return value


def compare_rows(model_attrs: dict[int, dict], rule_attrs: dict[int, dict]) -> dict[str, Any]:
    """Per key: both set and equal, both set and different, only the model, only the rules."""
    per_key: dict[str, Counter] = {k: Counter() for k in KEYS}
    diffs: list[dict[str, Any]] = []
    for item_id, m in model_attrs.items():
        r = rule_attrs.get(item_id, {})
        for key in KEYS:
            mv, rv = _norm(m.get(key)), _norm(r.get(key))
            if mv is None and rv is None:
                per_key[key]["neither"] += 1
            elif mv is None:
                per_key[key]["rule_only"] += 1
            elif rv is None:
                per_key[key]["model_only"] += 1
            elif mv == rv:
                per_key[key]["agree"] += 1
            else:
                per_key[key]["differ"] += 1
                diffs.append({"item_id": item_id, "key": key, "model": m.get(key),
                              "rule": r.get(key)})  # fmt: skip
    return {"per_key": {k: dict(v) for k, v in per_key.items()}, "diffs": diffs}


def rule_attributes(rows: list[dict[str, Any]]) -> dict[int, dict]:
    """The rule extractor's output for these items, in memory (nothing is written)."""
    from smartcart_catalog.extract.base import attrs_json
    from smartcart_catalog.extract.rule import RuleExtractor
    from smartcart_catalog.models import Attributes
    from smartcart_catalog.normalize import normalize

    items = [normalize(r, item_id=r["id"]) for r in rows]
    results = RuleExtractor().extract(items)
    out: dict[int, dict] = {}
    for row, res in zip(rows, results, strict=True):
        out[row["id"]] = json.loads(attrs_json(res)) if isinstance(res, Attributes) else {}
    return out


def cost_summary(conn, extractor_model: str | None) -> dict[str, Any]:  # noqa: ANN001
    from smartcart_catalog.extract.queue import cost_report

    lines = cost_report(conn, runs=50)
    if extractor_model:
        lines = [ln for ln in lines if ln.model == extractor_model]
    usd = sum((Decimal(ln.estimated_usd) for ln in lines if ln.estimated_usd), Decimal(0))
    return {
        "batches": len(lines),
        "requests": sum(ln.requests for ln in lines),
        "input_tokens": sum(ln.input_tokens for ln in lines),
        "output_tokens": sum(ln.output_tokens for ln in lines),
        "cache_read_input_tokens": sum(ln.cache_read_input_tokens for ln in lines),
        "cache_creation_input_tokens": sum(ln.cache_creation_input_tokens for ln in lines),
        "estimated_usd": str(usd),
    }


def compare(model_extractor: str) -> dict[str, Any]:
    from psycopg.rows import dict_row

    from smartcart_ingest import db as dbmod

    with dbmod.connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(_ROWS, (model_extractor,)).fetchall()
        model_name = next((r["model"] for r in rows if r["model"]), None)
        cost = cost_summary(conn, model_name)
    statuses = Counter(r["status"] for r in rows)
    ok_rows = [r for r in rows if r["status"] == "ok"]
    model_attrs = {r["id"]: dict(r["attrs"] or {}) for r in ok_rows}
    rules = rule_attributes(ok_rows) if ok_rows else {}
    result = compare_rows(model_attrs, rules)
    names = {r["id"]: r["raw_name"] for r in rows}
    order = {k: i for i, k in enumerate(CRITICAL_FIRST)}
    result["diffs"].sort(key=lambda d: (order.get(d["key"], 99), d["item_id"]))
    for d in result["diffs"]:
        d["raw_name"] = names.get(d["item_id"])
    confidences = [float(r["confidence"]) for r in ok_rows if r["confidence"] is not None]
    items = len(rows)
    per_item = (
        (Decimal(cost["estimated_usd"]) / items).quantize(Decimal("0.00001")) if items else None
    )
    return {
        "model_extractor": model_extractor,
        "model": model_name,
        "items": items,
        "statuses": dict(statuses),
        "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "cost": {**cost, "estimated_usd_per_item": str(per_item) if per_item is not None else None},
        **result,
        "commit": git_sha(),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def render(res: dict[str, Any], max_diffs: int = 40) -> str:
    label = f"`{res['model_extractor']}`" + (f" (`{res['model']}`)" if res["model"] else "")
    st = res["statuses"]
    lines = [
        f"## Extraction pilot: {label} against the rule extractor",
        "",
        "> Items are **synthetic** (the chains' synthetic fixtures, then the synthetic gold set's "
        "names). Neither extractor is ground truth, so agreement is not accuracy; the "
        "disagreements below are what a person reads before confirming or changing D14. The cost "
        "is the repo's estimate at batch rates from the token counts the API reported; the bill "
        "is the source of truth.",
        "",
        f"Items: {res['items']} (ok {st.get('ok', 0)}, retry {st.get('retry', 0)}, failed "
        f"{st.get('failed', 0)}); mean confidence of ok rows: {res['mean_confidence']}.",
        "",
        "| attribute | agree | differ | agreement (both set) | model only | rule only | neither |",
        "|---|---|---|---|---|---|---|",
    ]
    for key in KEYS:
        c = res["per_key"].get(key, {})
        both = c.get("agree", 0) + c.get("differ", 0)
        lines.append(
            f"| {key} | {c.get('agree', 0)} | {c.get('differ', 0)} | {_pct(c.get('agree', 0), both)}"
            f" | {c.get('model_only', 0)} | {c.get('rule_only', 0)} | {c.get('neither', 0)} |"
        )
    cost = res["cost"]
    lines += [
        "",
        "### Cost (estimate)",
        "",
        f"{cost['batches']} batch(es), {cost['requests']} requests: {cost['input_tokens']} input "
        f"tokens, {cost['output_tokens']} output, {cost['cache_read_input_tokens']} cache reads, "
        f"{cost['cache_creation_input_tokens']} cache writes. Estimated **${cost['estimated_usd']}**"
        f" (${cost['estimated_usd_per_item'] or 'n/a'} per item). The runbook's planning figure is "
        "0.002 to 0.003 USD per item (estimate, D14).",
        "",
    ]
    diffs = res["diffs"]
    if diffs:
        lines += [
            f"### Disagreements ({len(diffs)}; critical attributes first, first {min(len(diffs), max_diffs)})",
            "",
            "| item | name | attribute | model | rule |",
            "|---|---|---|---|---|",
        ]
        for d in diffs[:max_diffs]:
            lines.append(
                f"| {d['item_id']} | {md_escape(d['raw_name'])} | {d['key']} | "
                f"{md_escape(d['model'])} | {md_escape(d['rule'])} |"
            )
        lines.append("")
    lines.append(f"Commit `{res['commit']}`, {res['finished_at']}.")
    return "\n".join(lines) + "\n"


def prepare(raw_dir: Path | None, with_gold: bool) -> dict[str, Any]:
    from smartcart_catalog.evaluate import load_gold
    from smartcart_ingest import db as dbmod

    raw = raw_dir or Path(tempfile.mkdtemp(prefix="pilot-raw-"))
    run([sys.executable, str(REPO / "scripts" / "demo" / "load_fixtures.py"),
         "--no-neighborhood", "--raw-dir", str(raw)])  # fmt: skip
    out: dict[str, Any] = {}
    with dbmod.connect() as conn:
        if with_gold:
            out["gold"] = load_gold(conn)
            conn.commit()
        out["items"] = conn.execute("SELECT count(*) FROM items").fetchone()[0]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="load the synthetic items (fixtures, then gold set)")
    p.add_argument("--raw-dir", type=Path, default=None)
    p.add_argument(
        "--no-gold", action="store_true", help="only the chain fixtures (about 80 items)"
    )
    c = sub.add_parser("compare", help="model against rules, plus cost")
    c.add_argument("--model-extractor", default="claude")
    c.add_argument("--out", type=Path, default=None)
    c.add_argument("--json-out", type=Path, default=None)
    m = sub.add_parser("check-limit", help="exit 2 when N is outside 1..1000 (the spend cap)")
    m.add_argument("n", type=int)
    args = ap.parse_args(argv)

    if args.cmd == "check-limit":
        if not 1 <= args.n <= MAX_ITEMS_CAP:
            print(f"max_items must be between 1 and {MAX_ITEMS_CAP}, got {args.n}", file=sys.stderr)
            return 2
        return 0
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    if args.cmd == "prepare":
        print(json.dumps(prepare(args.raw_dir, not args.no_gold)))
        return 0
    res = compare(args.model_extractor)
    write_text(args.out, render(res))
    if args.json_out:
        write_text(args.json_out, json.dumps(res, ensure_ascii=False, indent=2, default=str) + "\n")
    if not res["items"]:
        print(f"no item_attributes rows from extractor {args.model_extractor!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
