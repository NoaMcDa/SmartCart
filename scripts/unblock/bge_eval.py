"""Measure BGE-M3 on the gold set and write a Markdown report (issue #29).

What ``.github/workflows/bge-eval.yml`` runs; also runnable anywhere with a fresh database:

    DATABASE_URL=... uv run smartcart-ingest migrate
    DATABASE_URL=... uv run --no-sync python scripts/unblock/bge_eval.py \\
        --embedder bge-m3 --out bge-eval-report.md --json-out bge-eval.json [--max-items 200]

With ``--embedder hash`` it runs without torch or network (that is how it is tested). Steps,
each one the real catalog CLI, timed:

1. ``smartcart-catalog evaluate --embedder hash`` on the gold set: loads the gold set exactly
   as ``matching-eval.yml`` does and gives the hash baseline on the same items.
2. ``smartcart-catalog embed --target all --embedder <embedder>``: the embed time reported.
3. ``smartcart-catalog evaluate --no-load --embedder <embedder>`` with the gate's judge and k.

``--max-items N`` evaluates a deterministic sample of N gold items (round robin over the
categories so every department is in it) written to a temporary gold directory. It needs a
database without the full gold set already loaded, because ``evaluate`` scores every row of
``gold_pairs``. The run never fails because a number is below the gate: it is a measurement.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import shutil
import sys
import tempfile
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path

from _common import REPO, fmt, git_sha, json_lines, last_json_document, run, venv_bin, write_text

GOLD_DIR = REPO / "data" / "gold"
LEVELS = ("exact", "any_brand", "close")
GATE_PRECISION = 0.98  # MATCH_PRECISION_THRESHOLD in matching-eval.yml (decision D5)
RECALL_AT_K_TRIGGER = 0.95  # evaluate.RECALL_AT_K_TRIGGER, fine-tuning trigger (estimate)
ANY_BRAND_RECALL_TRIGGER = 0.80  # docs/matching.md, fine-tuning trigger (estimate)


# --- gold subset ----------------------------------------------------------------------------------


def sample_items(rows: list[dict[str, str]], max_items: int) -> list[str]:
    """``max_items`` item keys, round robin over categories in first-seen order, each category's
    items in file order. Deterministic, so two runs with the same N score the same items."""
    by_cat: OrderedDict[str, list[str]] = OrderedDict()
    seen: set[str] = set()
    for r in rows:
        key = r["item_key"]
        if key in seen:
            continue
        seen.add(key)
        by_cat.setdefault(r["category"] or "?", []).append(key)
    chosen: list[str] = []
    queues = [list(v) for v in by_cat.values()]
    while len(chosen) < max_items and any(queues):
        for q in queues:
            if q and len(chosen) < max_items:
                chosen.append(q.pop(0))
    return chosen


def write_subset(gold_dir: Path, out_dir: Path, max_items: int) -> dict[str, int]:
    """Copy the gold catalog and the pairs of a ``max_items`` sample into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(gold_dir / "gold_catalog.yaml", out_dir / "gold_catalog.yaml")
    with (gold_dir / "gold_pairs.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        rows = list(reader)
    keep = set(sample_items(rows, max_items))
    kept = [r for r in rows if r["item_key"] in keep]
    with (out_dir / "gold_pairs.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)
    return {"items": len(keep), "pairs": len(kept)}


# --- model provenance -----------------------------------------------------------------------------


def hub_cache_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    home = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
    return Path(home) / "hub"


def model_revision(model_name: str, cache: Path | None = None) -> str | None:
    """The commit of ``model_name`` in the local Hugging Face cache (``refs/main``)."""
    if "/" not in model_name:
        return None
    ref = (cache or hub_cache_dir()) / f"models--{model_name.replace('/', '--')}" / "refs" / "main"
    try:
        return ref.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


# --- report ---------------------------------------------------------------------------------------


def gate_lines(metrics: dict, k: int, threshold: float) -> list[str]:
    p = metrics.get("precision", {}).get("any_brand")
    r = metrics.get("recall", {}).get("any_brand")
    rak = metrics.get("recall_at_k")

    def verdict(value: float | None, bar: float, good: str, bad: str) -> str:
        if value is None:
            return "n/a"
        return good if value >= bar else bad

    return [
        f"- any_brand precision {fmt(p)} against the CI gate {threshold}: "
        f"**{verdict(p, threshold, 'meets the gate', 'below the gate')}** (not enforced here).",
        f"- retrieval recall@{k} {fmt(rak)} against the fine-tuning trigger "
        f"{RECALL_AT_K_TRIGGER}: {verdict(rak, RECALL_AT_K_TRIGGER, 'above', 'below: plan fine-tuning')}.",
        f"- any_brand recall {fmt(r)} against the fine-tuning trigger "
        f"{ANY_BRAND_RECALL_TRIGGER}: {verdict(r, ANY_BRAND_RECALL_TRIGGER, 'above', 'below')}.",
    ]


def render(result: dict) -> str:
    main, base = result["metrics"], result.get("baseline")
    name, k = result["embedder_model"], result["k"]
    lines = [
        f"## Gold-set evaluation with {name}",
        "",
        "> The gold set is **synthetic** (`data/gold/build_gold.py`). These numbers show how the "
        "embedder behaves on the pipeline's regression set; they are not a precision estimate on "
        "real chain data. `sim_floor`/`sim_ceil` are calibrated for the hash embedder, so a "
        "different embedder also shifts confidences (recalibrate on the real gold set).",
        "",
        f"| level | precision ({name}) | recall ({name}) | served | gold items |"
        + (" precision (hash) | recall (hash) |" if base else ""),
        "|---|---|---|---|---|" + ("---|---|" if base else ""),
    ]
    for lvl in LEVELS:
        row = (
            f"| {lvl} | {fmt(main['precision'].get(lvl))} | {fmt(main['recall'].get(lvl))}"
            f" | {main['support'].get(f'predicted_{lvl}', 0)} | {main['support'].get(lvl, 0)} |"
        )
        if base:
            row += f" {fmt(base['precision'].get(lvl))} | {fmt(base['recall'].get(lvl))} |"
        lines.append(row)
    rak_line = f"Retrieval recall@{k}: **{fmt(main.get('recall_at_k'))}**"
    if base:
        rak_line += f" (hash: {fmt(base.get('recall_at_k'))})"
    s = main["support"]
    lines += [
        "",
        rak_line + ".",
        f"Items {s.get('items', 0)}, pairs {s.get('pairs', 0)}: served {s.get('served', 0)}, "
        f"review queue {s.get('review', 0)}, unmapped {s.get('unmapped', 0)}.",
        "",
        "### Against the gate and the fine-tuning trigger",
        "",
        "The triggers (0.95 and 0.80, planning choices) are defined for the real gold set; on the "
        "synthetic set, and on a `--max-items` sample, they are indicative only.",
        "",
        *gate_lines(main, k, result["threshold"]),
        "",
        "### Run",
        "",
        "| | |",
        "|---|---|",
        f"| embedder | `{result['embedder']}` (`{name}`) |",
        f"| model revision | `{result.get('model_revision') or 'n/a'}` |",
        f"| judge, k | `{result['judge']}`, {k} |",
        f"| gold items | {result['gold']['items']} of {result['gold']['items_total']}"
        f" ({'sample, --max-items' if result['gold']['sampled'] else 'full set'}) |",
        f"| embed time | {result['embed']['seconds']:.1f} s for "
        f"{result['embed']['canonicals']} canonicals and {result['embed']['items']} items |",
        f"| evaluate time | {result['evaluate_seconds']:.1f} s |",
        f"| sentence-transformers, torch | {result['versions'].get('sentence-transformers') or '-'},"
        f" {result['versions'].get('torch') or '-'} |",
        f"| commit, date | `{result['commit']}`, {result['finished_at']} |",
        "",
    ]
    return "\n".join(lines)


# --- main -----------------------------------------------------------------------------------------


def catalog(*args: str) -> list[str]:
    return [venv_bin("smartcart-catalog"), *args]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--embedder", default=os.environ.get("BGE_EVAL_EMBEDDER") or "bge-m3",
                    help="bge-m3 (default, or $BGE_EVAL_EMBEDDER) or hash")  # fmt: skip
    ap.add_argument("--max-items", type=int, default=0, help="sample N gold items (0: all)")
    ap.add_argument("--judge", default="rule", help="judge, as in the gate (default rule)")
    ap.add_argument("--k", type=int, default=10, help="candidates per item (default 10)")
    ap.add_argument("--threshold", type=float, default=GATE_PRECISION)
    ap.add_argument("--gold-dir", type=Path, default=GOLD_DIR)
    ap.add_argument("--out", type=Path, default=None, help="Markdown report (default stdout)")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args(argv)
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    with (args.gold_dir / "gold_pairs.csv").open(encoding="utf-8", newline="") as fh:
        items_total = len({r["item_key"] for r in csv.DictReader(fh)})
    tmp = Path(tempfile.mkdtemp(prefix="bge-eval-gold-"))
    try:
        gold_dir = args.gold_dir
        sampled = 0 < args.max_items < items_total
        if sampled:
            gold_dir = tmp / "gold"
            write_subset(args.gold_dir, gold_dir, args.max_items)
        common = ["--gold-dir", str(gold_dir), "--judge", args.judge, "--k", str(args.k), "--json"]

        # evaluate's load step is the gold set's only loader, so the baseline also loads it.
        baseline = last_json_document(
            run(catalog("evaluate", "--embedder", "hash", *common)).stdout
        )
        emb = run(catalog("embed", "--target", "all", "--embedder", args.embedder))
        counts = {d.get("target"): d for d in json_lines(emb.stdout)}
        ev = run(catalog("evaluate", "--no-load", "--embedder", args.embedder, *common))
        metrics = last_json_document(ev.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    model = metrics.get("embedder") or args.embedder
    result = {
        "embedder": args.embedder,
        "embedder_model": model,
        "model_revision": model_revision(model),
        "judge": metrics.get("judge", args.judge),
        "k": args.k,
        "threshold": args.threshold,
        "gold": {
            "items": metrics.get("support", {}).get("items", 0),
            "items_total": items_total,
            "sampled": sampled,
        },
        "embed": {
            "seconds": emb.seconds,
            "canonicals": counts.get("canonicals", {}).get("embedded", 0),
            "items": counts.get("items", {}).get("embedded", 0),
        },
        "evaluate_seconds": ev.seconds,
        "metrics": metrics,
        "baseline": baseline,
        "versions": {
            p: package_version(p) for p in ("sentence-transformers", "torch", "transformers")
        },
        "commit": git_sha(),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    report = render(result)
    write_text(args.out, report)
    if args.json_out:
        write_text(args.json_out, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("\n".join(gate_lines(metrics, args.k, args.threshold)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
