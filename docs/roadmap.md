# Roadmap

Timelines are the research's estimates for a solo developer. Phases 0 and 1 are detailed; 2 and 3 are
outlines.

## Phase 0: Data foundation (4–6 weeks)

**Status (2026-10-07).** Built and tested on synthetic fixtures: schema, eight chain adapters, ingestion
with quality gates, dashboard, exit-report generator. Not done: provisioning, real files and the two-week
window, so the go/no-go is NO-GO. Per-issue status and the owner's next steps are in
[phase-2-status.md](phase-2-status.md).

**Goal.** Nightly, trustworthy prices and promos for the 8–10 largest chains in Postgres, with quality
gates and an internal dashboard. No user-facing product yet.

| Week | Work |
|---|---|
| 1 | Monorepo layout, Supabase project (Postgres with PostGIS and pgvector), Israeli VPS, object storage for raw files, CI. |
| 1–2 | Schema: chains, stores with geography, chain-scoped items, prices as change events partitioned by month, structured promos, file tracking. Base price per chain plus per-store exceptions. |
| 2–3 | Ingestion: one adapter per chain wrapping the OpenIsraeliSupermarkets scraper and parser. Daily PriceFull, PromoFull and Stores, archived raw, loaded idempotently by hash. Full file before deltas. |
| 3–4 | Quality gates per file. Quarantine on failure. Breakage alerts per chain. |
| 4–5 | Internal dashboard (Streamlit): coverage, freshness, failed files, item and promo counts. |
| 5–6 | Hourly deltas for main chains. Identify each chain's online-store record. |

**Exit criteria.** Two consecutive weeks of nightly loads with over 95% success across the chosen
chains. Coordinates for every store. Promo parsing working for the top chains. A SQL query that prices
a barcode basket across all stores in a radius.

**Decisions to lock first.** Which 8–10 chains. Supabase versus self-hosted Postgres. LLM provider for
phase 1 attribute extraction.

## Phase 1: MVP (8–10 weeks)

**Status (2026-10-07).** The catalog, matching, API, web app, trust pages, SEO pages and beta
instrumentation are built and tested (PR #100, follow-ups in the MVP completion round). Everything that touches prices or matching runs on synthetic
data, and the 98% precision figure is measured on a synthetic gold set, so it is not evidence yet. Open:
real data, the extraction pilot, BGE-M3, human review, deployment, the screen-reader pass and recruiting the
beta. See [phase-2-status.md](phase-2-status.md).

**Goal.** A Hebrew web app where a user pastes a shopping list, sets flexibility per item, and sees
the cheapest nearby store plus a two-store split with travel cost.

**Track A, canonical catalog (weeks 1–5).** Taxonomy. 150–300 canonical products. Rule
normalization. LLM attribute extraction. BGE-M3 embeddings blocked by category and unit. Judge with
hard rules. Review UI. Gold set of 2,000–3,000 pairs. 98% precision at "any brand".

**Track B, backend (weeks 2–7).** Nightly effective-price precompute. FastAPI endpoints: parse-list,
search, compare, optimize (heuristic). Supabase Auth, RLS, lists and preferences.

**Track C, web app (weeks 3–9).** Next.js PWA, mobile-first, RTL, Heebo. Screens: onboarding (location
and radius, my store and clubs, travel mode and value of an extra stop), list builder, flexibility
sheet, results with three cards, split view, substitution card, product detail, profile. 50–200 static
SEO pages.

**Track D, trust and compliance (throughout).** Update timestamp on every price, "price at checkout
governs", every substitute labeled, report-a-gap, methodology page, AA accessibility, rounded location,
no data selling.

**Weeks 9–10.** Closed beta with 20–50 users (large families, kosher-conscious shoppers). Measure the
"not a good substitute" rate and fix matching before public launch.

**Exit criteria.** Paste-to-results in a few seconds. 150–300 canonicals at 98% precision on the gold
set. SEO pages indexed. Beta substitution rejection rate low enough that trust holds.

## Phase 2: Advanced savings (about 3 months)

**Status (2026-10-07).** Built: MILP optimizer, club filtering, price alerts with web push, price history,
shared lists in real time, barcode scanning and the smart-cart swap, all on synthetic data (PR #100 and the
MVP completion round). The whole stack runs end to end with `scripts/demo/up.sh` ([fullstack.md](fullstack.md)).
The native-app decision and catalog expansion need real users and real labels. See
[phase-2-status.md](phase-2-status.md).

MILP optimizer with cross-item promos and quantity rounding. Club filtering. Canonical-level price
alerts ("any soy drink under X"). Price history (90 days with promo markers). Shared family lists in
real time via Supabase Realtime. Barcode scanning in the PWA (camera API), mapping a shelf item to a
canonical and showing a cheaper substitute. "Smart cart" that proposes the single swap with the biggest
effect. Catalog expansion with active learning. Decide on a native app from retention data.

## Phase 3: Smart (6 months and beyond)

Receipt scanning (server-side OCR with Hebrew support, then LLM) to build a list. Voice list.
Handwritten list photo. Promo cycle prediction ("coffee promo returns roughly every 6 weeks").
Personalization. Monthly budget and spend tracking. Recipe to list. Cart transfer to chain online
stores. Arabic UI. Adaptation to the authority's new reporting schema.

## Regulatory watch

A proposed bill would raise the turnover threshold for price transparency and exempt more
retailers (see decisions.md D13, risk section). Check Knesset proceedings quarterly, first on
2027-01-05, and record the outcome in D13. If the bill advances, re-evaluate the chain list.

## Growth plan

Publish a monthly basket index the press will quote (what Pricez does today). The Ater and Rigbi study
showed press, not comparison sites, is how price transparency reached consumers. First audiences with
proven demand: large families, Haredi shoppers with kosher filters, periphery.
