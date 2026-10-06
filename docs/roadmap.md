# Roadmap

Timelines are the research's estimates for a solo developer. Phases 0 and 1 are detailed; 2 and 3 are
outlines.

## Phase 0: Data foundation (4–6 weeks)

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

## Growth plan

Publish a monthly basket index the press will quote (what Pricez does today). The Ater and Rigbi study
showed press, not comparison sites, is how price transparency reached consumers. First audiences with
proven demand: large families, Haredi shoppers with kosher filters, periphery.
