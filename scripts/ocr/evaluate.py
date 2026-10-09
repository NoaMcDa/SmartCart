"""Evaluate the OCR pipeline on the synthetic images of ``render.py`` (issues #61, #68).

    uv run --no-sync python scripts/ocr/evaluate.py --dir DIR [--provider tesseract]
        [--prepare-db] [--json-out FILE] [--max N] [--debug-samples N]

For each ``*.json`` truth file: the image goes through the same code the API runs (``prepare``,
the provider chosen by ``--provider``, ``parse_receipt`` for a receipt, the catalog resolver for
the rows), and ``score.py`` compares the result with the truth. The report goes to stdout and,
when set, to ``$GITHUB_STEP_SUMMARY``.

``DATABASE_URL`` (a migrated Postgres) turns on the catalog metrics for lists and receipts;
``--prepare-db`` seeds the MVP catalog with hash embeddings first (the demo stack's setup).
Without a database only the reading metrics are reported.

Every number is on SYNTHETIC images (render.py): it shows the pipeline works and where it breaks
on clean-ish input, not how it does on real receipts or real handwriting.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score  # noqa: E402


def prepare_db(conn: Any, *, commit: bool = False) -> None:
    """Seed the MVP catalog with hash embeddings. ``commit`` only for a throwaway database."""
    from smartcart_api.embedding import query_embedder, to_pgvector
    from smartcart_catalog.seed import load_catalog, seed_all

    seed_all(conn, load_catalog())
    emb = query_embedder()
    rows = conn.execute("SELECT id, display_name_he FROM canonical_products").fetchall()
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE canonical_products SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
            [(to_pgvector(emb.embed_one(name)), emb.model_name, cid) for cid, name in rows],
        )
    if commit:
        conn.commit()


def row_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": r.canonical.display_name_he if r.canonical else "",
            "input_text": r.input_text,
            "needs_confirmation": r.needs_confirmation,
            "candidates": [c.display_name_he for c in r.candidates],
        }
        for r in rows
    ]


def debug_dump(truth: dict[str, Any], lines: list[str], receipt: Any | None) -> None:
    """Raw provider lines next to the printed lines, untruncated (synthetic images only: the
    runner log is the only thing the maintainers can read)."""
    print(f"\n=== debug sample {truth['file']} ({truth['kind']}) ===")
    print(f"-- provider lines ({len(lines)}) --")
    for i, ln in enumerate(lines, 1):
        print(f"{i:3d} | {ln!r}")
    print(f"-- ground truth lines ({len(truth.get('lines', []))}) --")
    for i, ln in enumerate(truth.get("lines", []), 1):
        print(f"{i:3d} | {ln!r}")
    if receipt is not None:
        print(f"-- structured: chain={receipt.chain_id} branch={receipt.store_hint!r} total={receipt.total} --")
        for it in receipt.items:
            print(f"    item {it.text!r} qty={it.quantity} unit={it.unit} price={it.price}")
        print(f"-- truth items (total {truth['total']}) --")
        for it in truth["items"]:
            print(f"    item {it['printed']!r} qty={it['quantity']} price={it['price']}")
    sys.stdout.flush()


def evaluate(
    directory: Path, provider_name: str, conn: Any, limit: int | None, debug_samples: int = 0
) -> dict[str, Any]:
    from smartcart_api.ocr import config
    from smartcart_api.ocr.image import prepare
    from smartcart_api.ocr.providers import select_provider
    from smartcart_api.ocr.rows import rows_from_list_lines, rows_from_receipt
    from smartcart_catalog.receipt import parse_receipt

    os.environ["OCR_PROVIDER"] = provider_name
    provider = select_provider()
    truths = sorted(directory.glob("*.json"))
    if limit:
        truths = truths[:limit]
    receipts, lists = score.Tally(), score.Tally()
    cost, seconds, failures, diagnostics = 0.0, 0.0, 0, []
    counts = {"receipt": 0, "list": 0}
    dumped = {"receipt": 0, "list": 0}
    for path in truths:
        truth = json.loads(path.read_text(encoding="utf-8"))
        kind = truth["kind"]
        counts[kind] += 1
        image = prepare((directory / truth["file"]).read_bytes())
        start = time.monotonic()
        try:
            result = provider.read(image, kind)
        except Exception as exc:  # report and go on; one bad image must not hide the rest
            failures += 1
            diagnostics.append(f"{truth['file']}: provider error {type(exc).__name__}")
            continue
        seconds += time.monotonic() - start
        cost += result.est_cost_usd
        receipt = parse_receipt(result.lines) if kind == "receipt" else None
        if dumped[kind] < debug_samples:
            dumped[kind] += 1
            debug_dump(truth, result.lines, receipt)
        if kind == "receipt":
            tally = score.score_receipt(truth, receipt)
            if conn is not None:
                rows, _ = rows_from_receipt(conn, receipt)
                tally.merge(score.score_rows(
                    {"items": [{"canonical": i["canonical"]} for i in truth["items"]]}, row_dicts(rows)
                ))
            receipts.merge(tally)
            bad = [m for m in ("item text", "quantity", "price", "total", "chain")
                   if tally.hit[m] != tally.total[m]]
            if bad and len([d for d in diagnostics if d.startswith("receipt")]) < 3:
                diagnostics.append(
                    f"receipt {truth['file']} wrong in {bad}\n  read : {result.lines[:14]}\n"
                    f"  items: {[(i.text, str(i.quantity), str(i.price)) for i in receipt.items][:8]}\n"
                    f"  truth: {[(i['printed'], i['quantity'], i['price']) for i in truth['items']][:8]}"
                )
        else:
            tally = score.score_list_lines(truth, result.lines)
            if conn is not None:
                rows, _ = rows_from_list_lines(
                    conn, result.lines, confirm_all=result.provider == "tesseract"
                )
                tally.merge(score.score_rows(truth, row_dicts(rows)))
            lists.merge(tally)
            if tally.hit["list line read"] != tally.total["list line read"] and len(
                [d for d in diagnostics if d.startswith("list")]
            ) < 3:
                diagnostics.append(
                    f"list {truth['file']}\n  read : {result.lines}\n  truth: {truth['lines']}"
                )
    return {
        "provider": provider.name, "model": config.claude_model() if provider.name == "claude" else None,
        "images": counts, "failures": failures, "est_cost_usd": round(cost, 4),
        "seconds_per_image": round(seconds / max(1, sum(counts.values()) - failures), 2),
        "receipts": {m: [receipts.hit[m], receipts.total[m]] for m in receipts.total},
        "lists": {m: [lists.hit[m], lists.total[m]] for m in lists.total},
        "_tallies": (receipts, lists), "diagnostics": diagnostics,
    }


def report(res: dict[str, Any], with_catalog: bool) -> str:
    receipts, lists = res["_tallies"]
    n = res["images"]
    out = [
        "### OCR evaluation (SYNTHETIC images)",
        "",
        f"Provider **{res['provider']}**" + (f" (model `{res['model']}`)" if res["model"] else "")
        + f", {n['receipt']} synthetic receipts and {n['list']} handwritten-style lists "
        "(printed font drawn with jitter, blur and noise; not real handwriting).",
        f"Provider errors: {res['failures']}. Estimated cost: ${res['est_cost_usd']:.4f} "
        f"({res['seconds_per_image']} s per image). Catalog metrics: "
        + ("on (seeded MVP catalog, hash embeddings)." if with_catalog else "off (no database)."),
        "",
        "These numbers come from generated images. They check the pipeline and show where it breaks; "
        "they are not an accuracy estimate for real receipts or real handwriting.",
        score.table(receipts, "Receipts, per field"),
        score.table(lists, "Handwritten-style lists"),
    ]
    if res["diagnostics"]:
        out += ["", "<details><summary>examples of mistakes</summary>", "", "```", *res["diagnostics"], "```", "</details>"]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--provider", default="tesseract", choices=["auto", "fake", "tesseract", "claude"])
    ap.add_argument("--prepare-db", action="store_true", help="seed the MVP catalog first")
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--max", type=int, help="evaluate at most this many images")
    ap.add_argument("--debug-samples", type=int, default=0,
                    help="print the raw provider lines next to the truth for this many receipts and lists")
    args = ap.parse_args(argv)

    conn = None
    if os.environ.get("DATABASE_URL"):
        import psycopg

        conn = psycopg.connect(os.environ["DATABASE_URL"])
        if args.prepare_db:
            prepare_db(conn, commit=True)
    elif args.prepare_db:
        print("--prepare-db needs DATABASE_URL", file=sys.stderr)
        return 2
    try:
        res = evaluate(args.dir, args.provider, conn, args.max, args.debug_samples)
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()
    text = report(res, conn is not None)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if args.json_out:
        args.json_out.write_text(
            json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    return 0 if sum(res["images"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
