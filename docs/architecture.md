# System architecture

How SmartCart works end to end. The decisions behind each part are in `decisions.md`.

## Overview

```
~30 chain transparency portals
  -> (1) Ingestion workers (Python, Israeli-IP VPS) -> raw archive (R2/S3)
  -> (2) Parse and normalize (il-supermarket-parser + per-chain adapters, quality gates)
  -> (3) PostgreSQL on Supabase: PostGIS + pgvector, monthly partitions for prices
  -> (4) Canonical catalog and matching (rules + LLM extraction + BGE-M3 + judge + review UI)
  -> (5) Nightly precompute: effective price per (canonical, store)
  -> (6) FastAPI: /parse-list, /search, /compare, /optimize
  -> (7) Next.js PWA + static SEO pages
  Supabase Auth, Realtime (shared lists), RLS for user data
```

## 1. Ingestion

- **Sources.** Each chain publishes Stores, PriceFull/Price and PromoFull/Promo files as gzip XML on its own portal (Shufersal's own portal, publishedprices.co.il with a public username per chain, matrixcatalog, laibcatalog). Dialects differ per chain: windows-1255 versus UTF-16, `<Item>` versus `<Product>`, zip versus gzip.
- **Tooling.** Wrap `israeli-supermarket-scarpers` and `il-supermarket-parser` (OpenIsraeliSupermarkets) in one adapter per chain. The upstream project is beta, so every chain gets a regression fixture from a real file and alerting on breakage.
- **Schedule.** Full sync of PriceFull and PromoFull once a day, early morning. Price and Promo deltas every 30–60 minutes for the main chains. Downloads are idempotent by file hash. A `file_tracking` table ensures the full file loads before any delta.
- **Where it runs.** A VPS with an Israeli IP, because at least one portal blocks cloud IP ranges.
- **Quality gates per file.** Price of zero, jump above 3x, sharp drop in item count, stale date. A failing file is quarantined, never loaded. An internal dashboard shows coverage, freshness, failed files and counts per chain.
- **Schema change.** The consumer authority is rolling out an improved reporting model through 2026. Adapters isolate source schema from the internal model so both can coexist.

## 2. Data model

| Table | Notes |
|---|---|
| `chains` | Chain id, name, club names |
| `stores` | Chain, store code, name, address, `geography(Point)` with GiST index, channel (physical or online) |
| `items` | Chain-scoped: chain id, item code, barcode (may be internal), raw name, quantity, unit, manufacturer, raw attributes |
| `prices` | Change events only: item, store (nullable for chain base price), price, unit price, valid_from. Partitioned by month. |
| `promos` | Structured: item(s), store or chain, dates and hours, club restriction, min quantity, max quantity, reward type, raw description |
| `canonical_products` | Taxonomy path, display name, critical attributes, soft attributes, base unit, `vector` embedding with HNSW index |
| `item_canonical` | Item to canonical mapping, flexibility level at which it qualifies, confidence, source (rule, model, human) |
| `effective_prices` | Nightly precompute: canonical, store, best item, effective unit price, promo applied, club required |
| `file_tracking` | File hash, chain, store, type, timestamp, status |
| `users`, `lists`, `list_items`, `preferences` | Supabase Auth user id, RLS per user. Location rounded to neighborhood. |
| `gold_pairs` | Labeled matching pairs for evaluation |

Base price per chain plus per-store exceptions keeps the price table an order of magnitude smaller
than per-store rows.

## 3. Canonical catalog and matching

This is the core of the product and the riskiest piece.

**Step A, deterministic normalization.** Clean names (abbreviations like "ש.ז.", "מהד'", "ק\"ג"),
extract quantity and unit from the quantity fields and the name with regex, normalize to grams and
milliliters, detect multipacks ("6*1.5 ל'").

**Step B, LLM attribute extraction.** For each new item, once, in batch, extract structured JSON:
`{category_path, product_type, brand, is_private_label, fat_pct, state: fresh|frozen|chilled|canned,
flavor, kosher, diet_flags, pack_size, unit}`. Use a cheap commercial model in batch mode or an
open Hebrew model (Dicta-LM) locally. Estimated cost for the full catalog: tens of dollars.
Research support: GPT-4-class models led all product entity-matching benchmarks (Peeters, Der, Bizer,
arXiv 2310.11244); "variant product matching" (VARM, 2026) formalizes the distinction between
"same product" and "which attributes differ", which is exactly "any brand" versus "close substitute".

**Step C, blocking and embeddings.** Block by category and unit first, then embed. BGE-M3 dense
embeddings as the base (100+ languages, stable on Hebrew). multilingual-e5 scored 0.397 NDCG@20 on
the Hebrew national retrieval challenge, NeoDictaBERT 0.404, so Hebrew retrieval quality is mediocre
out of the box. Plan: contrastive fine-tuning on our own labeled pairs (Peeters and Bizer, supervised
contrastive learning for product matching). DictaBERT for segmentation and classification where
morphology matters.

**Step D, decision.** Cross-encoder or LLM judge on the top-k candidates, with hard rules on critical
attributes: never merge 3% with 1%, fresh with frozen, soy drink with almond drink at the "any brand"
level. Output: item to canonical mapping with a confidence score.

**Step E, human review.** Streamlit or Label Studio review UI for medium-confidence items and for the
300 best-selling canonicals. Active learning on hard cases. User feedback ("not a good substitute")
is a labeling signal.

**Evaluation.** Gold set of 2,000–3,000 labeled pairs across categories. Precision and recall
measured separately per flexibility level. Target: 98% precision at "any brand".

**Taxonomy.** 3–4 levels (department, category, product type, canonical product), seeded from
Hazol's 19 departments and deepened in staples first. MVP covers 150–300 canonical products that
make up most of a typical basket, not all 170,000 SKUs.

### Why embeddings work here, and where they fail

They work because the problem is "same thing, different words": chains name the same product
differently, abbreviations and typos are common, user free text must match catalog names, and 170k
items cannot be hand-mapped. Embeddings are the recall engine.

They fail on small differences that matter (3% versus 1%, fresh versus frozen, 250 g versus 500 g),
on numbers and units, on small Israeli brand names the model has never seen, on cross-category
near-neighbors (olive oil versus canola oil), and on Hebrew morphology generally. That is why
attribute extraction, hard rules, a judge and human review sit on top. Embeddings never decide a
match alone.

## 4. Price comparison mechanism

**Layer 1, unit price.** Every item is normalized to a unit price: per 100 g for solids, per 100 ml
for liquids, per unit for counted goods, per kg for weighed produce (labeled estimated). Multipacks
are parsed to total quantity so a six-pack is not six times too expensive.

**Layer 2, product choice per list item.** The flexibility level decides which variants compete.
Exact: only that barcode. Any brand: every variant with the same critical attributes; lowest unit
price wins. Close substitute: soft attributes open; still ranked by unit price. Unit price makes
"any brand" fair across pack sizes.

**Layer 3, effective price.** Nightly, for each (canonical, store), fold in promos: 1+1 halves the
unit price when buying two, "3 for 20" is 6.67 each, club deals only if the user marked that club.
When a promo needs a quantity the user did not ask for, the app offers "add one more and save X"
instead of assuming.

**Layer 4, basket totals and split.** For every store in the user's radius, sum the effective price
of the chosen variant times quantity. Missing items count as missing, never ignored, so a store
cannot look cheap by not stocking half the list. The split optimizer then subtracts travel cost and
the user's value of an extra stop. The headline is net saving versus the user's usual store.

## 5. Cart optimizer

**Phase 1 heuristic.** N nearest stores (N=10). For each subset of size up to K (K=2 gives 55
subsets), pick the cheapest item per subset, apply promos greedily. Exact when no cross-item promos
exist.

**Phase 2 MILP.** Variables: x[i,p,s] binary (buy product p for need i at store s), y[s] binary (visit
store s), b[k] integer (promo bundles of promo k). Objective: minimize sum of price times x minus
promo discounts plus (travel cost + delivery fee) per visited store plus preference penalties.
Constraints: every need satisfied, x only at visited stores, at most K stores, promo bundles bounded
by what is bought, quantity limits, club promos only if the user is a member. 40 items and 10 stores
solve in tens of milliseconds with OR-Tools CP-SAT or HiGHS via PuLP.

**Output.** Three alternatives, not one: single cheapest store, split (net saving X), minimum effort.
The GroceryChop pattern, and it is good UX.

## 6. Search

Hybrid: pg_trgm for typos, Postgres full-text search, and pgvector similarity, merged with reciprocal
rank fusion. The list parser maps free text ("חלב, 2 רסק עגבניות, סלמון") to canonical items with
quantities and a confidence; low-confidence rows are flagged for the user to confirm.

## 7. API surface

| Endpoint | Purpose |
|---|---|
| `POST /parse-list` | Free text to canonical items with quantity and confidence |
| `GET /search` | Hybrid search over canonical products |
| `POST /compare` | Basket total per store in radius, with substitutions and missing items |
| `POST /optimize` | Single store, split, minimum effort, each with net saving breakdown |
| Supabase PostgREST | Lists, list items, preferences, profile, under RLS |
| Supabase Realtime | Shared family lists (phase 2) |

FastAPI emits OpenAPI 3.1; the web client is generated from it in CI.

## 8. Web app

Next.js PWA, mobile-first, true RTL, Heebo font, installable. Static SEO pages (category, leading
product, methodology, monthly basket index) generated from the catalog on the same domain. Details
and screens in `ux-design.md`.

## 9. Infrastructure and cost (estimates)

| Item | Monthly |
|---|---|
| Supabase Pro | 25 USD (verified), includes 10 USD compute credit |
| Israeli VPS for ingestion | 10–20 USD |
| Container for FastAPI (Fly.io, Railway) | 10–30 USD |
| Object storage | ~5 USD |
| LLM and embeddings | Tens of dollars one-off, then small |
| Total | ~40–100 USD at MVP; grows with MAU, egress, compute |

Scaling pattern: heavy reads, batched writes. Read replicas and the nightly precompute keep request
paths cheap. Redis is optional, for caching optimization results.

## 10. Privacy and security

Location rounded to neighborhood. Receipts (future) processed and deleted. No third-party ad SDKs.
RLS on every user table. No scraping of chain online stores. Only the legally mandated transparency
files.
