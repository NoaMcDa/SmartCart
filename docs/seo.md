# Static SEO pages, sitemap and the basket index

Issues #35 (static SEO pages), #21 (methodology page and quality metric) and #44 (monthly basket
index); decision D8 (separate static SEO pages on the same domain). Pages live in
`apps/web/src/app/(seo)/`, their logic in `apps/web/src/features/seo/`, the generator in
`services/catalog/smartcart_catalog/{export_seo,basket_index,cli_seo}.py`.

Labels follow `docs/README.md`: **verified**, **estimate**, **target**.

## What is generated

```
data/*.yaml ─┐
              ├─► smartcart-catalog export-seo ─► apps/web/public/seo/
Postgres ─────┘                                     categories.json   levels 1-2, canonical counts
 canonical_products, effective_prices, match_runs   products.json     every MVP canonical
                                                    quality.json      public matching metric
                                                    basket-index.json fixed basket + months
                                       next build ─► /c/[slug]  /p/[slug]  /methodology
                                                     /basket-index  /accessibility
                                                     /sitemap.xml  /robots.txt
```

The JSON is committed, so `next build` needs no database (CI builds from the snapshot). The Next.js
pages read it with `fs` while prerendering `generateStaticParams`; `dynamicParams = false`, so an
unknown slug is a 404, never an empty page. No page content is written by hand: the text around the
data is a template (docs/methodology.md is the only hand-written page, and it says so).

| File | Content |
|---|---|
| `categories.json` | Taxonomy levels 1 and 2 (19 departments, 56 categories in the seed): slug, Hebrew name, `canonical_count`, `has_page`, parent and breadcrumb path |
| `products.json` | Every MVP canonical (245 in the seed): slug, Hebrew name, taxonomy path, base unit, critical attributes, rank, `has_page`. With prices: per chain the minimum and median unit price, store count, `is_estimated`, and the latest `price_valid_from`. Without: `prices: null`, `price_valid_from: null`, `no_prices_yet: true`. A price the export kept off the page (see "Prices the export keeps off the pages") is listed in `withheld` (only when there is one) |
| `quality.json` | Latest `evaluate` row of `match_runs`: precision and sample per flexibility level, run date, gold set size, `synthetic`, the 98% target. `{"available": false}` when no run exists |
| `basket-index.json` | The published basket definition (version 1, 25 items) and the months, each `draft` or `published` |

Slugs are ASCII: a category slug is the taxonomy id with dots replaced by hyphens (`dairy.milk` is
`dairy-milk`), a product slug is the canonical's slug (`milk-fresh-3`). The issue asks for "clean Hebrew
RTL URLs": the pages are Hebrew and RTL, but the URLs are ASCII on purpose, because they stay stable
when a Hebrew name is edited and survive copy and paste in every messenger.

### Page budget (D8: 50 to 200)

A page exists for every level 1 and 2 category that has at least one canonical (70 in the seed: 17
departments and 53 categories), plus the best-ranked canonicals until `--max-pages` (default 200) is
reached: 130 product pages. Total **200** generated pages, plus `/methodology`, `/basket-index`,
`/accessibility` and the home page in the sitemap (204 URLs). Departments with no canonicals (health,
pets) get no page. The other 115 canonicals are in `products.json` with `has_page: false` and appear as
plain rows on their category page. The rank that decides which products get pages is an **estimate**
(`catalog.md`, "Choosing the canonicals"): replace it with a measured one before reading anything into
which products are covered.

## What each page has

- Hebrew `<title>` and description from the data, `lang="he" dir="rtl"` (root layout), a canonical URL,
  Open Graph title and description.
- JSON-LD: `BreadcrumbList` on every page; `Product` on product pages with `offers` **only when prices
  exist** (one `Offer` per chain at the median unit price, with a `UnitPriceSpecification` that says what
  the price is per: 100 g is `GRM` 100, 100 ml is `MLT` 100, unit is `C62`, kg is `KGM`); `CollectionPage`
  with an `ItemList` on category pages; `WebPage` with `dateModified` on the methodology, basket index and
  accessibility pages. Text is escaped so it cannot close the script tag.
- A visible update date (`<time>`): the latest `price_valid_from` when prices exist, otherwise the
  catalog snapshot date, labeled as such. The "המחיר הקובע הוא בקופה" line and a link to `/methodology`.
- A call to action into the list builder (`/`).
- No images, no text from chain online stores, no third-party requests (the e2e suite checks this).

Without prices (all of them today) a product page says "עדיין לא נטענו מחירים" and explains what counts
as the same product. That is thin content for a search engine. Whether such pages are indexed is a
build-time setting, `NEXT_PUBLIC_INDEX_UNPRICED` (`features/seo/config.ts`):

| Value | Unpriced product pages |
|---|---|
| unset or `1` (default, as before) | indexable, listed in the sitemap |
| `0` (also `false`, `off`, `no`) | `<meta name="robots" content="noindex, follow">`, left out of the sitemap |

One rule (`isIndexable`) drives the page metadata and the sitemap, so they cannot disagree; the tests run
both values. Priced pages are always indexable, and category pages are not affected. Flip it back to `1`
(or drop the variable) when the catalog has prices; the next build puts the pages back. **Decide before
the domain goes live.** It is a build argument like `NEXT_PUBLIC_SITE_URL` (see `deploy.md`), not a
runtime switch, because Next.js inlines `NEXT_PUBLIC_*` values.

`robots.txt` deliberately does not `Disallow` those pages: a crawler that may not fetch a page never
reads its `noindex`, and the URL can still be indexed from links.

## Sitemap and robots

`/sitemap.xml` (`app/(seo)/sitemap.ts`, from `features/seo/sitemap-entries.ts`) lists the home page,
`/methodology`, `/basket-index`, `/accessibility` and every generated page with `lastmod`.
`/robots.txt` (`app/(seo)/robots.txt/route.ts`) allows everything except per-person and tooling pages
(`/compare`, `/profile`, `/onboarding`, `/store-mode`, `/offline`, `/design-system`) and names the
sitemap. It is a route handler, not `robots.ts`, because the metadata file only works at the app root.

`NEXT_PUBLIC_SITE_URL` is the public origin used in canonical URLs, the sitemap and JSON-LD. It defaults
to `https://smartcart.example` (a reserved name) because no domain exists yet; an empty value counts as
unset (the Dockerfile passes an empty build arg when the repository variable is missing). **Set it for
the build that goes live**, or every canonical URL points at the placeholder.

Build-time settings (all read in `features/seo/config.ts`):

| Variable | Values | Effect |
|---|---|---|
| `NEXT_PUBLIC_SITE_URL` | absolute https origin | canonical URLs, sitemap, robots `Sitemap:` line, JSON-LD |
| `NEXT_PUBLIC_INDEX_UNPRICED` | `1` (default) / `0` | index or `noindex` unpriced product pages, see above |
| `SEO_STRICT_SITE_URL` | `1` | opt-in guard: a `NODE_ENV=production` build **fails** when the site URL is unset, the placeholder, not absolute, or not https |
| `SEO_ALLOW_PLACEHOLDER` | `1` | switches the guard off again (CI and local builds) |
| `SEO_PREVIEW_DRAFTS` | `1` | preview builds only: the basket-index page shows the newest month even as a draft, under a visible "draft" label, `noindex`, out of the sitemap. Combined with `SEO_STRICT_SITE_URL=1` the build fails, so a deploy build cannot show a draft |

The strict guard also refuses any `.invalid` host (reserved by RFC 2606): the real-prices preview builds with
`https://preview.invalid`, so that build can never be the one that ships.

The guard is opt-in because `next build` always runs with `NODE_ENV=production`, including the CI build
that has no domain. Set `SEO_STRICT_SITE_URL=1` in the deploy build only (next to
`NEXT_PUBLIC_SITE_URL`), and the build cannot ship canonical URLs on the placeholder. The error names
the variable and the way out.

## Checks

| Check | Where | What it covers |
|---|---|---|
| Structured data, offline | `tests/unit/structured-data.test.ts` (`npm test`) | Renders every generated page (70 category, 130 product, methodology, basket index, accessibility) and validates the JSON-LD it emits against hand-written schema.org shape rules for the types in use: `BreadcrumbList`, `ItemList`, `CollectionPage`, `Product`, `Offer` / `AggregateOffer`, `UnitPriceSpecification`, `QuantitativeValue`, `WebPage`, `WebSite`, `Dataset`, `Organization`. Required fields; absolute URLs on the site origin; ISO 8601 dates; currency `ILS`; a price only on a page that shows an update date; offers exactly when prices exist; canonical equals the JSON-LD `url` and the last breadcrumb; no raw `<` in the script. An unknown `@type` fails, so a new type needs a validator. The snapshot has no prices yet, so a second pass runs every page with synthetic prices and a published basket month. Negative cases prove the validator rejects what it should |
| Index configuration | `tests/unit/structured-data-config.test.ts` | both values of `NEXT_PUBLIC_INDEX_UNPRICED` against the sitemap, the page `robots` metadata and `robots.txt`; the site URL guard |
| Live site | `.github/workflows/seo-check.yml` (manual) | see below |
| Lighthouse | `lighthouserc.seo.json`, CI | SEO, accessibility, best practices on the six page types |

The offline test replaces the external validator run in CI. **Google's Rich Results Test (and the
Schema.org validator) is still a one-time manual check after the first deploy**: it knows what Google
accepts for rich results, which a shape check cannot.

### `seo-check` workflow (needs the live domain)

Actions, "SEO check", `workflow_dispatch`, inputs `site_url` (for example `https://www.example.co.il`)
and `sample_size` (default 10). With `site_url` empty it passes with a notice, so it is safe to run
before the domain exists. Otherwise it fetches `/robots.txt` (200, text/plain, no `Disallow: /`, a
`Sitemap:` line on this origin), `/sitemap.xml` (200, at least 50 URLs, every URL on the origin, no
duplicates, none disallowed by robots.txt) and the sampled sitemap pages, spread evenly and always
including a category, a product and the methodology page when the sitemap has them. Per page: status
200, `lang="he" dir="rtl"`, a title and one `h1`, the canonical equal to the sitemap URL, **no `noindex`
(meta or `X-Robots-Tag`) on a page the sitemap lists**, JSON-LD that parses with every URL on the origin,
and a visible update date wherever offers exist. The table goes to the job summary and the log; any
failed check fails the job. It does not replace Search Console: submit the sitemap and record the
indexed count weekly.

## Regenerating

| When | Command |
|---|---|
| `data/taxonomy.yaml` or `data/canonicals.yaml` changed | `uv run smartcart-catalog export-seo --from-files` (no database). A unit test fails when the committed `categories.json` or `products.json` differs from the seed files |
| Prices changed (nightly in production) | `uv run smartcart-catalog export-seo` with `DATABASE_URL`, then build. Do it after the nightly precompute |
| The evaluation was re-run | `uv run smartcart-catalog export-seo` (writes `quality.json`) |
| Rewrite the committed snapshot from seeded test data (catalog from the seed files, a fresh evaluation of the synthetic gold set for `quality.json`) | `SMARTCART_REGEN_SEO=1 uv run pytest services/catalog/tests/test_export_seo.py -k regenerate` |
| Page budget | `--max-pages N` |

`--from-files` leaves `quality.json` untouched. Every `export-seo` run also refreshes the basket
definition in `basket-index.json` and keeps stored months.

**Last regenerated: 2026-10-07** (issue #102, `base` made critical for the plant drinks), with

```
SMARTCART_REGEN_SEO=1 uv run pytest services/catalog/tests/test_export_seo.py -k regenerate
uv run smartcart-catalog export-seo --from-files      # same files, plus the basket definition
```

Changes: `products.json` gives `soy-drink`, `almond-drink` and `oat-drink` their `critical_attrs`
(`{"base": "soy"}`, `almond`, `oat`); they rank 141 to 143, so they stay `has_page: false` and
show as rows on `/c/beverages-plant_drinks`. `quality.json` comes from a fresh evaluation of the
enlarged synthetic gold set (857 items, 2,523 pairs). `categories.json` changed only its
`generated_at`, and `basket-index.json` not at all (the basket has no plant drink). As a check,
`export-seo` against a database seeded with `smartcart-catalog seed` writes the same
`categories.json`, `products.json` and `basket-index.json` (apart from `generated_at`); its
`quality.json` has no number because that database has no evaluate run. `next build` passes with
the new snapshot. The page template has Hebrew labels for `fat_pct`, `state` and `flavor` only:
if a plant drink ever gets a product page, `base` and its value would show untranslated until
`features/seo/format.ts` learns them.

Prices in `products.json` follow the app: the "any brand" row of `effective_prices` per store, physical
stores only, promos included unless they need a club (then the row's `noclub` option, or the store is
left out). Unit is the canonical's base unit; weighed goods are per kg and flagged estimated.

## Monthly basket index (#44)

`smartcart-catalog basket-index --month 2026-10 [--reviewed-by NAME] [--acknowledge CODE]` prices the
fixed basket from `effective_prices`, runs the pre-publication checks, and writes
`public/seo/basket-index.json` and `docs/reports/basket-index-YYYY-MM.md`.

**Basket v1.** 25 staples, all within the 60 best-ranked MVP canonicals, with amounts for a small
household's week, defined in `basket_index.py` (`BASKET_V1`) and published on `/basket-index`. The choice of
items and amounts is a judgement (**estimate**), not a measured basket. It is fixed inside a version; a
new basket is a new version, and a month priced with another version is flagged as not comparable.

**Method.** A line is an amount in the canonical's base unit (2 liters of milk is 20 units of 100 ml),
priced at the unit price, so pack size does not distort the total (D6). A chain's price for a line is the
**median** over its physical stores of the app's effective unit price (promos included except club
promos). A chain is ranked only when it prices every line; others are listed with their missing items.
Delta is from the cheapest ranked chain, never from the most expensive (D7). `effective_prices` holds only
the current state, so a month is a snapshot taken when the command runs, and the stored JSON and report
are the record.

**Checks before release** (thresholds are **proposals**, constants at the top of `basket_index.py`):

| Code | Level | Flags |
|---|---|---|
| `no_prices` | error | nothing priced |
| `too_few_chains` | error | fewer than 2 chains price the whole basket |
| `implausible_spread` | error | cheapest and dearest differ by more than 50% (the verified 67-item gap between Rami Levy and Tiv Taam was 26%) |
| `stale_prices` | error | effective prices computed more than 48 hours before the run |
| `implausible_change` | error | a chain's total moved more than 15% against the previous published month |
| `line_outlier` | error | one basket line costs 4 times or more at one chain than at another, or costs nothing (the first real day: a 24-roll pack read as a unit, 38.9x). Named by line; each month's chain rows carry `line_costs` |
| `missing_items` | warning | a chain lacks prices for some basket items (it is not ranked) |
| `estimated_items`, `new_chain`, `chain_dropped`, `basket_version_changed`, `no_computed_at` | warning | listed in the report |

A month is `draft` (the page does not show it) until `--reviewed-by NAME` is given and no error is open.
An error that a human looked at and accepts is passed with `--acknowledge CODE`; it is recorded in the
month. A published month also gets a public copy of the press report at
`public/seo/reports/basket-index-YYYY-MM.md`, linked from the page.

**Review process.** (1) Run without `--reviewed-by`: read the checks and the report. (2) Spot-check three
lines against a chain's own site (shelf prices; never copy content). (3) Run again with
`--reviewed-by`. (4) Commit `basket-index.json`, `public/seo/reports/`, `docs/reports/`, rebuild and
deploy. The first month needs real prices: none are loaded, so `months` is empty and the page says so.

The page never shows a draft in a normal build. A preview build (`SEO_PREVIEW_DRAFTS=1`, see "SEO on real prices")
shows the newest month under a **draft label** (a tag in the heading and a note that it must not be quoted, with the open
error checks listed), `noindex`, out of the sitemap, and without the press-report link; the methodology section keeps its
`measured`/`estimate` markers either way (the basket's composition is marked an estimate).

## Prices the export keeps off the pages

The first real day showed that `effective_prices` can hold rows that must not become a public page: a tray of
twelve eggs read as one egg (14.20 where the others say 1.18), a unit price that rounds to nothing. Pricing and
matching are not changed here (they belong to the precompute and the catalog); the export decides only what a
public page may show. `export_seo.screen_prices` withholds, in this order (thresholds are **proposals**, constants
at the top of `export_seo.py`):

| Reason | Rule |
|---|---|
| `bad_price` | zero, negative, not finite, or below half an agora (it would print as 0.00) |
| `above_cap` | above the cap of its unit: 150 per 100 g, 100 per 100 ml, 300 per unit, 1,000 per kg |
| `store_outlier` | a store 5 times above or below its own chain's median, in a chain with at least three stores |
| `chain_outlier` | with three or more chains, a chain median 4 times above or below the median of all the chains' medians |
| `chains_disagree` | with exactly two chains, medians 4 times apart: nobody can tell which is right, so both are withheld |

A withheld row is not deleted and not corrected. `products[].withheld` lists chain, reason, detail and row count;
the product page then says either that a price of one or more chains is not shown because it is far from the
others, or (nothing left to show) that the product's prices are being checked, never that none were loaded.
`smartcart-catalog seo-audit --dir DIR [--json-out F] [--md-out F] [--fail-on-error]` reads an export and reports
page counts, priced against unpriced, and what still looks wrong (codes `bad_price`, `above_cap`, `chain_outlier`,
`store_spread`, `missing_field`, `bad_name`, `bad_date`, `old_price`, `no_stores`, `withheld`, `basket_line`).
After the screen, the first six should be zero; `old_price` and `store_spread` are listed for a human.

The basket index is **not** screened: it prices the raw rows, so a bad row shows as a failed check instead of
disappearing. Its new `line_outlier` error (a basket line costing 4 times or more at one chain than at another,
or a line costing nothing) names the line; each chain row of a month now carries `line_costs` (median store x
amount per line).

Which products get a page is still decided by rank alone, not by whether they have prices: a URL that was
published must not turn into a 404 the day a price disappears. Priced products beyond the budget stay plain rows.

## SEO on real prices (preview)

The static pages and the basket index were built from synthetic data only. The **Real day** workflow
(`.github/workflows/real-day.yml`, `docs/real-day-dry-run.md`) now also runs them on the prices it loaded, as a
**validated preview**: nothing is deployed (no domain), the export is a workflow artifact kept 7 days, never
committed, and the committed snapshot in `apps/web/public/seo` stays the seeded synthetic one.

**What runs** (input `seo`, always on in a push run; `real_day.py run --seo-out DIR`, `scripts/unblock/seo_preview.py`):

1. After the production precompute (reviewed mappings only) and again after the stress precompute (unreviewed
   mappings counted, a performance variant, not product behaviour): `export-seo` and `basket-index` into `DIR/<variant>`
   (a draft: no `--reviewed-by`, so it can never be published from here), then `seo-audit`.
2. In the same job, the web app is built from that export (`npm run build`) with
   `NEXT_PUBLIC_SITE_URL=https://preview.invalid`, `NEXT_PUBLIC_INDEX_UNPRICED=0` and `SEO_PREVIEW_DRAFTS=1` (the
   draft basket month is shown under its draft label). The committed snapshot is put back afterwards.
3. Against that build: the offline structured-data validation and the SEO unit tests (`structured-data*.test.ts`,
   `src/features/seo`, run without the build's preview switches); a crawl of **every** generated page from `next start`
   (the checks of `seo-check.yml` instead of a sample: status, `lang`/`dir`, one `h1`, canonical on the preview origin,
   robots meta equal to the sitemap, JSON-LD parses with URLs on the origin, offers equal to the exported prices, a visible
   update date, the checkout line and the methodology link, no `NaN`/`undefined`/`null` and no `₪ 0` in the visible text,
   and the sitemap equal to the set of indexable pages); and `tests/e2e/seo-preview.spec.ts` in Chromium at 390 px (the
   product with the most chains, the longest name, a weighed one, one with a withheld price, an unpriced one, the biggest
   category, the basket index: no horizontal scroll, no console error, no serious or critical WCAG 2.0 AA violation).
   The spec is skipped in a normal `npm run e2e` (it reads whatever export is in `public/seo`).
4. The job summary has both tables; the report branch `real-day/report-<run id>` (workflow input `commit_report`, always on a
   push run) gets the Markdown and JSON of the audit and the checks, never the export itself.

The crawler and the audit have their own tests on hand-made pages and real-shaped rows
(`scripts/unblock/tests/test_seo_preview.py`, `services/catalog/tests/test_export_seo_screen.py`,
`apps/web/src/features/seo/real-shaped.test.tsx`).

**What the first real prices showed, and what was changed** (runs 39797274019 and 39804455160, 2026-10-22; the second ran the final code, the first failed 3 unit tests that assumed an unpriced milk):

| Found | Change |
|---|---|
| Unit prices that cannot be true reach `effective_prices`: toilet paper 24 rolls at 813.60 (Shufersal) against 20.93 (King Store), mineral water at 6.8 times, paper towels and garbage bags at 9.90 where the others say 1 to 2, sunflower oil 10.90 per 100 ml, soda water 0.03 | The export keeps them off the pages (`screen_prices`, above) and says so; pricing is not touched here. The precompute's unit-price rules were then fixed on the real rows ([real-day-dry-run.md](real-day-dry-run.md), "Unit-price outliers"): of 41 withheld rows 11 remain in the next real run (the mineral water is a correct price of a different product), and the screen stays as the safety net |
| The cross-chain check first compared each chain with the median of the *other* chains; with three chains one wild value pulled the two honest ones into "outliers" (found on a seeded test) | It compares with the median of all the chains' medians (two chains: with each other) |
| A tray read as one unit shows in the basket as a line costing 38.9 times more at one chain | New `line_outlier` check of the basket index (error: blocks publication until acknowledged) and `line_costs` per chain in each month |
| Prices have one page-level date; chains' own dates differ | A dated column per chain (`<time>`) in the price table and `validFrom` in each `Offer` (the known JSON-LD gap is closed) |
| The new date column made the price table wider than a 390 px screen for a weighed product: axe `scrollable-region-focusable` (serious) on the preview spec | `ScrollRegion`: when a table scrolls sideways its wrapper becomes a focusable named region; a table that fits adds no tab stop |
| A preview build that shows a draft basket month would be `noindex` yet listed in the sitemap (the crawl check) | The page is out of the sitemap whenever it shows a draft (`basketShowsDraft`, one function for the metadata and the sitemap) |
| `https://preview.invalid` passes the strict site-URL guard (it is https, not the placeholder) | The guard refuses `.invalid` hosts and a strict build with `SEO_PREVIEW_DRAFTS=1` |
| Three unit tests assumed the committed snapshot's milk has no prices; a real export has them | They follow the data |
| The real export has no evaluation, so `quality.json` says `available: false` | The methodology page shows "not yet measured" instead of a number (already the behaviour; its test now covers both) |

Hebrew edge cases the preview exercises and found no defect in: chain names with quotes, brackets and a stray `<b>`
(escaped in the page and in the JSON-LD, `real-shaped.test.tsx`), the 21 October evening UTC dates that are already 22
October in Jerusalem (dates are Israel dates), weighed goods (155 of 697 price cells in the first run carry the
estimate label, in the table and in the heading), single-store single-chain prices (38 cells), and chains without store
coordinates (the page never uses coordinates). Product and category names are our own catalog names (none over 80
characters; the audit's `bad_name` would say), chain names are the six chains' short names.

**Numbers** (run 39804455160, 2026-10-22, commit 32f596f; six of the ten chains answered the runner; each run is one day and differs by the files the portals return):

| | Production semantics (reviewed mappings only) | Stress (unreviewed counted; performance variant) |
|---|---|---|
| Pages generated | **200** (70 category, 130 product) | 200 (70, 130) |
| Canonicals priced / unpriced (of 245) | **190 / 55** | 237 / 8 |
| Product pages priced / unpriced | **107 / 23** | 128 / 2 |
| Price cells (chain x product), estimated among them | 697, 155 | 1,141, 234 |
| Chains per priced product (1, 2, 3, 4, 5, 6) | 32, 27, 27, 25, 44, 35 | 13, 18, 19, 20, 47, 120 |
| Price rows kept off the pages (entries) | 41 (14) | 37 (14) |
| Audit error-level findings left after the screen | **0** | 0 |
| Dates of the prices on the pages | 21 and 22 October (464 cells on the 22nd, 233 on the 21st) | |
| Sitemap URLs (unpriced product pages are `noindex`) | 180 of 203 pages | 201 |
| `next build` | passed, 24 s | passed, 7 s |
| **Structured-data errors** (offline validation of every page's JSON-LD, plus the SEO unit tests: 121 tests) | **0** | 0 |
| Crawl of every generated page (203 pages, 1,870 / 1,891 checks) | **0 failed** | 0 failed |
| Playwright at 390 px with axe (the pages the spec picks) | passed | passed |
| Basket index 2026-10 | **draft**; no chain prices all 25 lines (18, 17, 13, 13, 13, 10 lines); errors `too_few_chains`, `line_outlier` x2 (toilet paper 38.9x, mineral water 6.8x) | draft; 5 chains rank (346.36 at Tiv Taam to 1,132.06 at Shufersal, spread 226.8%, `implausible_spread`); `line_outlier` x2 (toilet paper, chicken breast 4.5x) |
| Pages whose price looked implausible before the screen | 14 entries on 8 products: toilet paper (3), mineral water, garbage bags (2), paper towels (3), sunflower oil (2), salt, chicken soup powder, brown rice | 14 entries on 10 products (soda water 0.03, wet wipes, whole frozen chicken 99.90, cauliflower 85.00 per kg, ...) |

Per-line outliers in the unscreened basket (the old 170 egg line has become): toilet paper at Shufersal 813.60 for 24 rolls
against 20.93 (a pack read as a unit again), mineral water at Osher Ad 67.73 against 9.94 for 6 liters. These are in the
precompute's unit prices, not in the pages: the pages no longer show them.

**Reading.** These are counts on one day's files and one hand-made basket, not a price survey, and nothing here is a
publishable index: the basket stays a draft (no chain prices all 25 lines in the production variant, and the stress
variant's totals are not credible, see the withheld rows and `line_outlier` above). The thresholds (4x between chains,
5x within a chain, the per-unit caps) are **proposals**: in the production export no priced product with three or more
chains had a chain at 3x its median or more (largest 2.86x, peanut butter), so 4x does not cut real shelf competition; in
the stress export 12 of 206 were at 3x or more (up to 3.84x), where the unreviewed mappings add genuine mismatches
that the 4x line lets through (chicken breast 8.90 against 27.90 per kg is a 3.4x gap that only the basket check names).
Google's Rich Results Test and the Schema.org validator remain a one-time manual check after the first deploy.

**To run it again:** Actions, "Real day", `seo` on (after about 08:00 Israel time, as for the real day itself); or offline on
any database that has been through the real day: `smartcart-catalog export-seo --out DIR`, `basket-index --out DIR
--reports DIR/reports-draft`, `seo-audit --dir DIR`, then `scripts/unblock/seo_preview.py web --export DIR --variant NAME
--out OUT [--e2e]` (it replaces `apps/web/public/seo` for the build and puts the committed snapshot back).

## Arabic UI and the indexed Hebrew (#73)

The static pages are generated at build time in Hebrew and must stay Hebrew in the server HTML,
because that is what search engines index; they are not made dynamic and carry no Arabic
alternates yet (the `hreflang` decision for Arabic SEO pages is still open). The page bodies and the
shared chrome (`components.tsx`, `SeoShell`, the quality metric, the basket tables, and the
`*Content` components used by `/methodology`, `/c/*`, `/p/*` and `/basket-index`) are client
components that read the UI locale. On the server the locale context is always Hebrew, so the HTML
is Hebrew; after hydration a visitor with the Arabic locale sees the Arabic messages
(`src/i18n/messages/{seo,methodology}.ts`, machine-drafted, native review pending). `<title>`,
descriptions, Open Graph data and JSON-LD stay Hebrew. Catalog names (products, categories, chains)
are Hebrew data and are not translated; Arabic canonical display names are a catalog task.
`tests/e2e/locale-ar-2.spec.ts` checks that the server HTML is Hebrew even with the Arabic cookie.

## What is still synthetic or not done

- **No prices in the committed snapshot** (the real-prices preview above has 190 of 245 canonicals priced, in a workflow artifact): `effective_prices` is empty in seeded data, so every
  product page says so, no `offers` data exists, and the basket index has no month. All of it fills in on
  regeneration once ingestion and the precompute run.
- **The quality metric is synthetic.** It comes from the template-generated gold set. The page says so.
- **The product ranking is an estimate** (decides which products have pages).
- **Structured data is validated offline, not by Google.** `structured-data.test.ts` checks the shape of
  every page's JSON-LD (see "Checks"); there is no network from the build environment. Run each page type
  through Google's Rich Results Test and the Schema.org validator once after the first deploy
  (`beta-plan.md` checklist). Lighthouse (accessibility, best practices, SEO) is 100 on all six page types
  in the `a11y` CI job. Each `Offer` carries `validFrom` (the chain's own price date, in Israel time) and the
  price table has a dated row per chain (`<time>`), so no price is dated only by the page-level line.
- **Not indexed yet.** There is no domain, so nothing is submitted to Search Console and no indexed-page
  count exists. After launch: submit `/sitemap.xml`, record the indexed count weekly in the beta report
  (issue #35's last criterion).
- **The results footer and the substitution card** (W4b) do not link to the methodology page yet.
  `MethodologyLink` is exported for them.
