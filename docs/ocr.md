# Receipt and handwritten-list photos (#61, #68)

`POST /parse-image` turns a photo of a supermarket receipt or a handwritten shopping list into
rows for the normal compare and optimize flow. This page is the engineering reference: data flow,
the deletion guarantee, consent, providers, caps and costs, how accuracy is measured, and the
limits. The HTTP contract is in [api.md](api.md#post-parse-image-61-68); the receipt rules are in
`services/catalog/smartcart_catalog/receipt.py`.

Status: built and tested on synthetic data and fakes. No real receipt or real handwritten list has
been read yet, no real OCR number exists, and the web UI (consent screen, preview, confirmation) is
a separate workstream. Every accuracy figure on this page is **synthetic**, from images this
repository generates (see "Evaluation"). The facts that Google Cloud Vision reads Hebrew and that
on-device ML Kit does not are verified (issue #61); every other figure is an estimate or measured
on synthetic images, and is marked.

## Data flow

```
client (PWA)                         API process (memory only)                       Postgres
  photo + kind + X-Image-Consent: 1
  ───────────────────────────────▶ 1  consent header, body size           (403 / 413 before the body is parsed)
                                    2  provider selected                   (503 if none)
                                    3  monthly cap check ───────────────────────────▶ ocr_usage (read)
                                    4  magic bytes, 8 MB, Pillow decode,   (415 / 413 / 422)
                                       <= 25 MP, EXIF rotate, <= 2400 px
                                    5  provider.read(image, kind) ─▶ lines (text)
                                    6  usage counted ───────────────────────────────▶ ocr_usage (+1 image, +cost estimate)
                                    7  list:    split_items → /parse-list matcher
                                       receipt: receipt.parse_receipt → matcher with the printed quantity
                                    8  references dropped; response with deleted: true
  ◀─────────────────────────────── rows, unresolved, receipt summary
```

The response is `ParseImageResponse` (`schemas.py`): `items` are `ParsedRow`s resolved like
`/parse-list`, `unresolved` are lines that were read but not matched, `receipt` (receipts only) is
the chain hint, branch text, printed total and the structured lines, and `deleted` is always
`true`.

## Consent

The request must carry `X-Image-Consent: 1`; any other value or no header is **403** and the body
is not read. The header is the API's half of the explicit consent the issue requires: the PWA
shows what happens to the photo before the first upload, stores the user's choice (and lets them
withdraw it), and sends the header only while consent stands. Consent is not recorded on the
server: nothing about a photo is tied to a user. The header is not declared in `openapi.json`
(the snapshot is unchanged by this work); it is documented here and in api.md. A browser calling
the API from another origin needs `X-Image-Consent` in the CORS `allow_headers` (see "Limits").

## Deletion guarantee (D11)

The image, the decoded pixels and the raw OCR text exist only as locals of one request.

| Where it could leak | What prevents it |
|---|---|
| Multipart upload spooling | Starlette spools an upload to a temp file above 1 MB. The route raises the parser's in-memory limit above the 8 MB cap and cuts the body at 8 MB plus the envelope while it streams in (413), so memory is bounded and nothing spools to disk. |
| Decoding | Pillow decodes from `BytesIO`; no temp files. |
| Tesseract | The binary is run with `tesseract stdin stdout`, the PNG on stdin, the text on stdout. `pytesseract` is **not** used because it saves the image to a temp file. |
| Claude vision | One `messages.create` with the image as base64; the SDK does not write it. Errors are re-raised without the SDK's message (`from None`) so a message that echoes a request cannot reach a log. |
| Logs | The route logs one line with counts and the estimated cost (`kind`, `provider`, line, item and unresolved counts, USD). Never bytes, never text. |
| Database | `ocr_usage(month, provider, images, est_cost_usd)`: a counter. No user id, session id, file name or text. |
| References | `data`, the decoded image and the line list are dropped in `finally` blocks before the response; the tests hold a weak reference to the decoded image and check it is gone. |

Tests proving it (`services/api/tests/test_api_image_privacy.py`): no `tempfile` function is
called and no file is opened for writing during a request, with a 6.7 MB upload that would
spool by default (the test fails if the in-memory setting is removed); the `TMPDIR` stays empty;
no image bytes (raw, hex, base64) and no OCR text reach any log record, including on a failed
read; the decoded image is garbage-collected; `ocr_usage` holds a count and an estimate only; no
table in the database contains the text of a receipt.

What the guarantee does not cover: with the `claude` provider the photo is sent to Anthropic's API
to be read. That is a processing step the consent screen must name; check the retention terms of
your Anthropic account before enabling it. With `tesseract` nothing leaves the API host.

## Providers

`ocr/providers.py`; selection by `OCR_PROVIDER`.

| Provider | When | Notes |
|---|---|---|
| `claude` | `OCR_PROVIDER=claude`, or `auto` with `ANTHROPIC_API_KEY` set | Sync `anthropic` client, model `claude-sonnet-5-5` (`OCR_CLAUDE_MODEL`), image block (JPEG, base64), a prompt that asks for plain lines only: no commentary, no markdown, skip what is unreadable, text in the photo is data not an instruction. `effort: low`, `max_tokens` 2000, no tools. A `refusal` stop reason or any SDK error is a 502. Cost from the response's usage tokens. |
| `tesseract` | `OCR_PROVIDER=tesseract`, or `auto` when no key and the binary plus the `heb` data are installed | `heb+eng`, `--psm 4` for receipts (a column of variable-size lines), `--psm 6` for lists. Free. Printed text only: handwriting is poor, so every row of a list read by Tesseract is marked `needs_confirmation`. |
| `fake` | `OCR_PROVIDER=fake`, and in tests | Reads the text embedded in a PNG (`sc-ocr` text chunk) or a registry keyed by the image's pixel hash. No recognition. For tests and the evaluation's self-test only. |

`auto` with neither a key nor Tesseract answers **503** "no OCR provider configured". Google Cloud
Vision is not implemented: one vision model reads both printed receipts and handwriting behind one
interface, and the `Provider` protocol (`read(image, kind) -> OcrResult(lines, provider,
est_cost_usd)`) is what to implement if the evaluation on real photos favors another engine.

## Receipt structuring (`smartcart_catalog/receipt.py`)

Pure, rule-based, Hebrew, no LLM, no network. From OCR lines it finds:

- **Chain** from the header words (first 12 lines, one letter off allowed for names of six or more
  characters; then exact anywhere, such as "תודה שקניתם בשופרסל"), mapped to the GS1 company id the
  ingest adapters and `apps/web/src/features/profile/chains.ts` use (ten chains; "מגה" maps to the
  Bitan id, as `adapters/mega.py` loads it). Two chains matching is `null`, never a pick. The
  response field is `chain_hint`.
- **Branch** text after "סניף".
- **Printed total**: "לתשלום" wins over "סה\"כ"; "סה\"כ פריטים/הנחות/לפני מע\"מ" are not totals.
- **Item lines**: `name  price` (price at either end, since RTL output comes in either visual
  order), `name` then `2 X 5.90  11.80`, `name  2 X 5.90  11.80`, weights `0.532 ק"ג X 9.90  5.27`.
  A weight is believed only with three decimals or next to a per-kg price (so "סוכר 1 ק\"ג" is a
  name); `יח'` is a quantity only on a line without a name ("ביצים 12 יח'" is a pack).
- **Not items**: discount lines (collected as negative amounts), deposits ("פיקדון"), VAT, payment,
  change, dates, fiscal and club lines. A name without a price or detail line is dropped (a header
  line must not become a product).
- **Noise**: bidi marks, stray punctuation, quote variants, `O` and `l` inside numbers, a space in a
  price, a trailing minus, thousands separators. A one-decimal price with a two-digit integer part
  (`90.5`, which is `5.09` back to front) is flipped **only** when that makes the item prices,
  discounts and the printed total add up; otherwise it stays as read.
- **Abbreviations**: the catalog's `clean_name` plus receipt shorthand (`חל'`, `גב'`, `שמנ'`,
  `יוג'`, `עגב'`, `תפו"א`, `1ל`, `750 מל`, ...), about 30 rules; add a row and a test to extend.

The unit tests (`services/catalog/tests/test_receipt_structuring.py`) cover chains, branches,
totals, every layout above, the non-item classes, the noise cases, abbreviations and a whole
receipt.

## From lines to rows (`ocr/rows.py`)

- **List photo**: lines -> `listparse.split_items` -> the `/parse-list` fragment logic (quantities,
  the `ו` split) -> `routes.search.resolve`.
- **Receipt**: the structured item names (abbreviations expanded) -> `resolve`, keeping the printed
  quantity (`unit = "kg"` for a weighed item). A till prints brand and pack size, the "any brand"
  catalog carries neither, so the name is tried as printed, without the size, and without the size
  and known brands (`query_variants`; the fat percentage is never removed), and the best result is
  used. Repeated products are merged and their quantities added.
- **The floor**: as `/parse-recipe`, a best hit under **0.70** (an estimate) goes to `unresolved`
  with the line as read. Two equally good canonicals are capped at exactly 0.70 by the matcher and
  stay as a row with `needs_confirmation` and candidates. Never a guess (D5).
- Lines with no letters are ignored; at most 200 lines are used.

A misread letter can spell another real product, so the matcher's thresholds are a minimum, not a
guarantee. The UI must show what was read next to the photo and let the user edit (issue scope).

## Caps and costs

| Variable | Default | Meaning |
|---|---|---|
| `OCR_MONTHLY_IMAGE_CAP` | 2000 | images per calendar month (UTC), all providers |
| `OCR_MONTHLY_USD_CAP` | 20 | estimated dollars per month |

Table `ocr_usage(month, provider, images, est_cost_usd)` (migration `20261011100000_ocr_usage.sql`,
no user id; RLS on with no policy, no grants to `anon` or `authenticated`). Before a read the API
refuses with **429** if one more image would pass either cap; the check uses the provider's
expected cost (Claude 0.01 USD, Tesseract 0). After a successful read it adds 1 image and the
estimate from the usage tokens. A failed read is not counted. Two requests that pass the check at
once can both be served, so the cap can be passed by the number of concurrent requests: it is a
spending brake, not a meter. The 0.01 USD figure is an **estimate**: about 1.6k image tokens
(the API downscales to about 1568 px) plus a 300-token prompt in, a few hundred tokens out, at the
list price of $2 / $10 per million tokens (the sync table is `ocr/pricing.py`; the catalog's
extraction table is the 50 % batch price). At the defaults, 2000 images is about $20, which is
what the dollar cap enforces. Measure it: the `ocr-eval` workflow with provider `claude` reports
the estimated cost from real usage tokens.

## Evaluation

Workflow **OCR evaluation** (`.github/workflows/ocr-eval.yml`, `workflow_dispatch`), inputs
`receipts` (default 40), `lists` (default 20), `seed` (default 7), `provider` (`tesseract` or
`claude`). It installs `tesseract-ocr tesseract-ocr-heb fonts-noto-core`, migrates a Postgres
service, then:

1. `scripts/ocr/render.py` generates the receipts and lists with ground truth JSON next to each
   image. Receipts: chain header, branch, items drawn from the repo's own canonical catalog printed
   with brands, sizes, abbreviations, weighed items, `N X price` lines, discounts and deposits,
   prices at the left edge and names at the right, Noto Sans Hebrew, rotation of 1.5 degrees,
   blur and noise. "Handwritten-style" lists: the same font drawn word by word with random
   rotation, baseline jitter, ink colour, blur and noise on ruled paper, plus distractor lines
   that are not products. **This is not handwriting.**
2. `scripts/ocr/evaluate.py --provider fake` on copies of the same images that carry their own text:
   the **upper bound** (perfect reading), which isolates the structurer and the matcher.
3. `evaluate.py --provider tesseract` (or `claude`) on the plain images, through the same
   `prepare`, provider, `parse_receipt` and resolver the API runs.

Reported (to the log and `$GITHUB_STEP_SUMMARY`): receipts per field (chain, total, item text
exact after normalization, quantity, price, item recall and precision) and, with the catalog,
catalog recall, the precision of rows that are not flagged for confirmation (the D5 metric) and
all-row precision; lists: lines read exactly, catalog recall (top hit, and top hit or a suggested
alternative), precision, and distractors kept out of rows. Three examples of mistakes are printed.

Local self-test (no Tesseract, no network): `render.py --embed-truth` and the fake provider are
exercised by `services/api/tests/test_api_image_eval.py`. On 40 receipts and 20 lists with perfect
reading the structurer and matcher scored 100 % on every metric above (**synthetic**: the layouts
are the ones the structurer was written against, so this checks the plumbing, it is not an
accuracy claim). Tesseract and Claude numbers: not run yet; run the workflow.

## Limits and open items

- **No real data.** Real receipts vary by chain, till and print quality; the layouts here are an
  approximation. The accuracy the issues ask for ("on a small labeled set of real receipts", "on
  a labeled set of handwritten lists") needs photos collected with consent. The renderer and
  scorer are ready for it: put a truth JSON next to each photo.
- **Hebrew handwriting accuracy is not established** (issue #68). The workflow's lists are printed
  letters with jitter. Choose the provider on real lists.
- Tesseract is expected to read printed receipts better than handwriting; its receipt output order
  (price first or last) is handled, multi-column layouts and faded thermal paper are not.
- The structurer ignores items it cannot price and flips reversed digits only when a total
  confirms it.
- Brand removal uses the catalog extractor's brand list (`KNOWN_BRANDS`), an initial list.
- The route holds a pooled database connection while the provider reads (seconds for Claude). Size
  `API_POOL_MAX` for the photo traffic or move the read before the dependency if it becomes a
  problem.
- **CORS**: `main.py` allows the headers `Authorization` and `Content-Type` only. A browser on a
  different origin than the API must also be allowed `X-Image-Consent`, or the preflight fails.
- `ocr_usage` rows are never deleted; they hold counts only.
- Out of scope, per the issues: storing receipts or photos, receipt history, spend tracking,
  on-device OCR (ML Kit has no Hebrew, verified), languages other than Hebrew.
