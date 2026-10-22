"""Temporary: the raw PriceFull rows (and what the loader and the precompute made of them) behind
the implausible unit prices of the real day. Reads the files the real-day run downloaded; writes
JSON and Markdown. Removed again once the regression tests carry the rows."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from smartcart_ingest import xmlutil

PATTERN = re.compile(sys.argv[3] if len(sys.argv) > 3 else r"נייר טואלט|מגבות נייר|שקיות אשפה|מים מינרל|שמן חמניות|סודה")


def rows_of(path: Path):
    xml, _enc = xmlutil.to_utf8(xmlutil.unwrap(path.read_bytes())[0])
    for el in xmlutil.iter_rows(xml, ("Item", "Product")):
        fields = xmlutil.scalar_children(el)
        if PATTERN.search(fields.get("itemname", "")):
            yield fields


def main() -> int:
    work = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    found = []
    for base in ("probe/files", "extra"):
        for path in sorted((work / base).glob("*/PriceFull*")):
            slug = path.parent.name
            try:
                for fields in rows_of(path):
                    found.append({"chain": slug, "file": path.name, "row": fields})
            except Exception as exc:  # noqa: BLE001
                found.append({"chain": slug, "file": path.name, "error": repr(exc)})
    (out / "raw_rows.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), "utf-8")
    print(f"{len(found)} raw rows")

    import psycopg

    try:
        conn = psycopg.connect(os.environ["DATABASE_URL"])
        cur = conn.execute(
            """
            SELECT c.id, i.id, i.item_code, i.raw_name, i.quantity, i.unit, i.is_weighed,
                   (SELECT string_agg(DISTINCT p.price || '|' || coalesce(p.unit_price::text, '-') || '|' || coalesce(p.uom, '-') || '|' || coalesce(s.store_code, 'base'), '; ')
                      FROM prices p LEFT JOIN stores s ON s.id = p.store_id WHERE p.item_id = i.id) AS prices,
                   (SELECT string_agg(DISTINCT e.effective_unit_price || '|' || e.uom || '|' || coalesce(e.pack_units::text, '-'), '; ')
                      FROM effective_prices e WHERE e.item_id = i.id) AS effective,
                   (SELECT string_agg(DISTINCT cp.slug || ':' || ic.flex_level, ',')
                      FROM item_canonical ic JOIN canonical_products cp ON cp.id = ic.canonical_id
                     WHERE ic.item_id = i.id) AS canon
              FROM items i JOIN chains c ON c.id = i.chain_id
             WHERE i.raw_name ~ %s
             ORDER BY c.id, i.raw_name
            """,
            (PATTERN.pattern,),
        )
        rows = [list(map(str, r)) for r in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        rows = [["error", repr(exc)]]
    (out / "db_items.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    print(f"{len(rows)} db items")
    # every pack note of one more precompute over what the run left in the database (the stress
    # variant's accepted mappings), not the 20 samples of the metrics
    try:
        from smartcart_api.precompute import precompute_effective_prices

        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            res = precompute_effective_prices(conn)
        notes = res.pack_notes or []
    except Exception as exc:  # noqa: BLE001
        notes = [{"kind": "error", "detail": repr(exc)}]
    (out / "pack_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1), "utf-8")
    print(f"{len(notes)} pack notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
