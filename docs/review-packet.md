# Canonical review packet (issue #15)

Issue #15 asks for one thing only a person can give: a domain-aware reviewer signs off the 245
canonical products before matching builds on them (`catalog.md` section 2, "Open: domain-aware
reviewer sign-off"). This page is the shortest path for that person. An engineer runs two
commands to make the packet; the reviewer reads one page or one spreadsheet and ticks a decision per
row; an engineer imports the answers, which produces a signed record and the exact change to
`data/canonicals.yaml`, applied by hand.

Labels follow `docs/README.md`: **measured** is read from the repository or a run, **estimate** is a
judgement.

## 1. Make the packet (engineer, about a minute)

```bash
uv run smartcart-catalog review-packet --out dist/review/
```

No database and no network are needed. It writes, into `dist/review/` (a `.gitignore` inside keeps
it out of git):

| File | For whom |
|---|---|
| `canonicals-review.html` | The reviewer who wants to read, or print and tick on paper. One self-contained page: Hebrew, right to left, system fonts only, no script, no external file, A4 landscape when printed. |
| `canonicals-review.csv` | The reviewer who prefers a spreadsheet (Excel, Google Sheets, Numbers). Same rows, empty `decision` and `comment` columns. UTF-8 with a BOM so Excel reads the Hebrew. |

Send the reviewer both. Options: `--examples real,gold` (default; also `db` to use matched items of
a loaded database, or `none`) and `--per-canonical 5`.

### What each row shows

Rows are grouped by department and category of the taxonomy, in rank order inside a group.

| Column | Meaning |
|---|---|
| Rank (**estimate**) and tier | 1 is the most common product in an Israeli weekly shop. The rank is a judgement, not a measurement (`catalog.md`, "Choosing the canonicals and the ranking"); tiers 1 to 5 hold 24, 54, 77, 75 and 15 products. |
| Product | The Hebrew display name, the slug, and the taxonomy path. |
| Base unit | The unit prices are compared in: per 100 g, per 100 ml, per unit or per kg. |
| Critical attributes | What must be equal for two items to match at "any brand": fat percentage, fresh or frozen, flavor, the base of a plant drink. The product type itself is always critical. A 3% milk and a 1% milk are different canonicals because of this column. |
| Soft attributes | Typical values that may differ at "close substitute": pack size, brand. |
| Product type rule | The product type, which attribute keys are critical and soft for it, and the first words the automatic extractor uses to recognise the type. |
| Up to 5 examples | Real item names that the repository's rule pipeline maps to this canonical, with the chain, the level (`זהה`, `כל מותג`, `תחליף קרוב`), a `לבדיקה` tag when the pipeline was not sure enough to show it to a user, and a label saying where the name comes from. |
| Decision | `☐ תקין (OK)`, `☐ שינוי (change)`, `☐ הסרה (remove)` and two lines for a note. |

### Where the examples come from (read this before trusting them)

- **`קובץ אמיתי של רשת` (real).** The 200-row price files of seven chains, fetched on 2026-10-08 and
  committed as regression fixtures (`services/ingest/tests/fixtures/<chain>/real/`). They are real
  chain data, but small: 1,400 items in total (**measured**), so many canonicals have no real example.
  Five of the seven chains cut item names at 20 to 24 characters (**measured**).
- **`סינתטי (סט הזהב)` (synthetic).** Names written by us for the gold set (`data/gold`), used only
  to fill what the real files do not reach. Not chain data.
- **`מסד הנתונים` (database).** With `--examples db`, items already matched in a loaded database.
- **The examples are a machine's suggestion.** Each name went through the same steps as
  `smartcart-catalog normalize`, `extract --extractor rule`, `embed --embedder hash` and
  `judge --judge rule`, done in memory. On all 1,400 real items the in-memory result and the
  database run give the same canonical, level and review flag (**measured**, 1,400 of 1,400; a test
  checks a small set of the same kind, `test_in_memory_matching_equals_the_database_pipeline`).
  Because they are rule matches, some are wrong. That is useful to the reviewer: a
  juice mapped to tomatoes, or chickpeas mapped to a hummus salad, is a sign that the canonical
  or its keywords need a look. Report it in the comment; do not treat a wrong example as a wrong
  canonical by itself.
- The page prints how many items were checked and how many mapped, and how many canonicals have a
  real, only a synthetic, or no example. On the current files: 133 canonicals with a real example,
  26 synthetic only, 86 none (**measured** on 2026-10-08).

## 2. The review (reviewer, about two to four hours, estimate)

The estimate: 245 rows at about 30 seconds each is two hours, plus about 30 minutes for the
tier 1 and 2 rows (the 78 most common products), plus 15 to 30 minutes for the missing-products
pass. `unblock.md` says two to four hours for the same task. It is an estimate; nobody has timed it.

What to check, in this order (the list is `catalog.md` section 2):

1. **Fat percentages** match common Israeli products: for example lactose-free milk 2%, yellow
   cheese 28% and 9%, bulgarian cheese 5% and 24%, whipping cream 32% and 38%.
2. **Nothing important is missing from tiers 1 and 2** (ranks 1 to 78).
3. **The critical attributes are right** for each product type: does "sliced" need to split yellow
   cheese; is fresh versus frozen critical for this product; is flavor critical here.
4. **The ranks look plausible.** Only the order matters, and only as a review aid for now.
5. **The name is what a shopper would type**, and the base unit makes sense.

For each row pick one:

| Decision | Use it when | What to write |
|---|---|---|
| **OK** / `תקין` | The row is right as it is. | Nothing. |
| **change** / `שינוי` | Something in the row is wrong. | A comment saying what and why. Optionally fill the `proposed_*` columns (below). |
| **remove** / `הסרה` | The product should not be on the list. | A comment with the reason. |
| **add** / `הוספה` | A product is missing. Append a new row at the end of the CSV, leave `slug` empty. | `display_name_he` and a comment (why it is common). |

Rows left empty count as undecided and the import refuses them (section 3). The decision words are
not case-sensitive, and the Hebrew forms `תקין`, `שינוי`, `הסרה`, `הוספה`, `כן` and a leading `☑`
are accepted.

### Optional: say exactly what to change

For a `change` row the `proposed_*` columns make the answer machine-readable, so the import can show
the diff. Leave a column empty to keep the value.

| Column | Format | Example |
|---|---|---|
| `proposed_display_name_he` | The new name. | `גבינה צהובה פרוסה 9%` |
| `proposed_base_unit` | `100g`, `100ml`, `unit` or `kg`. | `100g` |
| `proposed_critical_attrs` | `key=value; key=value`, or `{}` for none. | `fat_pct=9` |
| `proposed_soft_attrs` | Same. | `pack_size=200; unit=g` |
| `proposed_rank` | The position it should take, a whole number from 1. | `12` |

Attribute keys: `fat_pct`, `state` (`fresh`, `frozen`, `chilled`, `canned`, `dry`), `flavor`, `base`
(`soy`, `almond`, `oat`, `rice`, `coconut`), `variety`, `pack_size`, `unit`, `brand`. If you are not
sure of a key, write the change in the comment and leave the columns empty; an engineer finishes it.

### In a spreadsheet

- **Excel:** open `canonicals-review.csv` (double-click works; the BOM makes the Hebrew show).
  Fill `decision`, `comment` and, if wanted, the `proposed_*` columns. Save with **File, Save As,
  CSV UTF-8 (Comma delimited)**. Plain "CSV (Comma delimited)" on a Hebrew Windows saves Windows-1255
  and a semicolon; the import accepts that too and says so.
- **Google Sheets:** File, Import, Upload, "Replace spreadsheet". Fill it in. File, Download,
  "Comma-separated values (.csv)".
- Do not rename, delete or reorder columns, and do not edit `slug` or `row_hash` (the import uses
  them to match rows and to notice that the list changed after the packet was made).

### On paper

Print the HTML (landscape, background graphics off is fine), tick a box per row and write notes on
the two lines. Someone then types the ticks into the CSV, or you photograph the pages and send them
back with the name and date; the import itself only reads the CSV.

## 3. Import the decisions (engineer, a minute)

```bash
uv run smartcart-catalog review-import filled.csv --reviewer "Dana Cohen" --date 2026-10-20
```

`--date` defaults to today; `--note "domain: dairy and produce"` adds a line to the record. The
command:

1. **Validates** the CSV and reports every problem together without writing anything: a missing
   column, an unknown or repeated slug, a decision it cannot read, a `change` or `remove` without a
   comment or a proposal, a bad `proposed_*` cell, canonicals with no decision, and rows whose
   content changed in `data/canonicals.yaml` since the packet was made (`row_hash`).
2. **Writes** `data/signoff/canonicals-2026-10-20.yaml`: the reviewer's name, the date, the
   fingerprint of the canonicals file, a count per decision and one entry per canonical
   (format: `data/signoff/FORMAT.md`; the empty form is `data/signoff/template.yaml`). It will not
   overwrite an existing file without `--force`.
3. **Prints the diff** the decisions imply for `data/canonicals.yaml` (removals, changed fields,
   ranks renumbered `1..N`), whether the result would pass `smartcart-catalog seed --check`, and a
   list of things only an engineer can do: `change` rows without a `proposed_*` value, and added
   products (which need a taxonomy node, a product type and critical attributes). **It never edits
   `data/canonicals.yaml`.** `--patch-out FILE` also saves the diff.

Options for a review that is not finished: `--allow-partial` records a partial sign-off with the
undecided slugs listed under `pending` (issue #15 asks for a complete one); `--allow-stale` accepts
rows changed since the packet.

## 4. After the import (engineer)

The sign-off file is evidence; the list changes only when a person applies it.

1. Apply the decisions to `data/canonicals.yaml` by hand from the diff, and the follow-ups from the
   printed list. Keep the ranks `1..N`.
   A change to a critical attribute (fat percentage, fresh or frozen, plant base) must also be made
   in that canonical's Arabic names (`names_ar`): the import lists every Arabic name that still
   states the old value as a problem, and `seed --check` refuses the file until they agree.
2. `uv run smartcart-catalog seed --check`, then `seed`.
3. `uv run smartcart-catalog evaluate --fail-below 0.98` (a changed canonical can move the gold
   set's numbers; report precision per flexibility level, `CLAUDE.md`).
4. `uv run smartcart-catalog export-seo --from-files` (`seo.md`: a unit test fails while the
   committed snapshot differs from the seed files).
5. Commit the sign-off file with the change. Then update `catalog.md` section 2 ("Open:
   domain-aware reviewer sign-off") to say who reviewed and when, and the methodology page sentence
   "הרשימה טרם נסקרה בידי מומחה תחום" (`apps/web/src/app/(seo)/methodology/page.tsx`), which is true
   only until then.
6. Close #15 when the sign-off file is `complete` and the list is applied. The measured rank
   (frequency from loaded data) is a separate step after #60.

## 5. What the packet does not do

- It does not rank by measured frequency; there is no loaded data yet (`catalog.md`).
- It does not check that the examples are right; they are rule output.
- It does not review the product type rules' keywords or the taxonomy itself; the rule cell shows
  them so a wrong type word can be reported in a comment.
- It does not verify kosher or diet attributes; the chains' files do not carry them (`catalog.md`).
