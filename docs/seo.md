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
| `products.json` | Every MVP canonical (245 in the seed): slug, Hebrew name, taxonomy path, base unit, critical attributes, rank, `has_page`. With prices: per chain the minimum and median unit price, store count, `is_estimated`, and the latest `price_valid_from`. Without: `prices: null`, `price_valid_from: null`, `no_prices_yet: true` |
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

## What is still synthetic or not done

- **No prices.** The committed snapshot has none: `effective_prices` is empty in seeded data, so every
  product page says so, no `offers` data exists, and the basket index has no month. All of it fills in on
  regeneration once ingestion and the precompute run.
- **The quality metric is synthetic.** It comes from the template-generated gold set. The page says so.
- **The product ranking is an estimate** (decides which products have pages).
- **Structured data is validated offline, not by Google.** `structured-data.test.ts` checks the shape of
  every page's JSON-LD (see "Checks"); there is no network from the build environment. Run each page type
  through Google's Rich Results Test and the Schema.org validator once after the first deploy
  (`beta-plan.md` checklist). Lighthouse (accessibility, best practices, SEO) is 100 on all six page types
  in the `a11y` CI job. Known gap: the `Offer` nodes carry no `validFrom`, so the date of a price is
  the visible `<time>` on the same page, not part of the JSON-LD (`jsonld.ts`).
- **Not indexed yet.** There is no domain, so nothing is submitted to Search Console and no indexed-page
  count exists. After launch: submit `/sitemap.xml`, record the indexed count weekly in the beta report
  (issue #35's last criterion).
- **The results footer and the substitution card** (W4b) do not link to the methodology page yet.
  `MethodologyLink` is exported for them.
