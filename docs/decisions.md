# Architecture decisions

Each decision records the context, the choice, the alternatives considered, and the consequences.
Dates are October 2026. Sources are the two research documents in `research/` and the design
discussions that followed.

## D1. Web-first PWA for the MVP, native app deferred

**Context.** The Flutter feasibility research assumed the phone app is the primary product. The market
research's MVP feature list (paste a list, flexibility per item, basket comparison, two-store split,
saved lists) needs nothing native. Native-only features (in-store barcode scanning, push alerts,
receipt OCR, voice) are all phase 2 or 3.

**Decision.** Build the MVP as a mobile-first progressive web app on a DOM framework (Next.js
preferred, SvelteKit acceptable). Make it installable. Decide on a native app after phase 1 using
retention data. If native is needed, wrap the PWA with Capacitor or build React Native, which shares
the language with Next.js.

**Alternatives rejected.**
- Flutter mobile app (the Flutter research's recommendation): adds 2–4 weeks of Dart learning, app store review cycles, a separate SEO site, and a smaller hiring pool, for no MVP feature that needs it.
- Flutter Web: canvas rendering is unusable for SEO, adds 1.1–1.5 MB before app code, and screen readers need an explicit opt-in. Flutter's own docs point content sites to Jaspr or plain HTML.
- Python-only web (FastAPI + Jinja + HTMX): viable for a Python-only developer but weaker for the drag-between-stores split UI. Kept as a fallback.

**Consequences.** One codebase for the app and the SEO pages. Zero-friction trial, which matters
because adoption, not technology, is the category's historic failure. iOS PWAs support camera and
push since iOS 16.4, so barcode scanning and alerts can start on web too.

## D2. Python owns ingestion, catalog ML, and optimization

**Decision.** All backend logic beyond CRUD is Python: ingestion workers, normalization, LLM attribute
extraction, embeddings, the cross-encoder judge, the optimizer.

**Why.** The parsers for all chains already exist in Python (OpenIsraeliSupermarkets). The embedding
and LLM ecosystem (sentence-transformers, PyTorch, Hugging Face) is Python. OR-Tools has no Dart
bindings and only community Node bindings. Rewriting any of this elsewhere is months of work for no
benefit.

**Rejected.** Serverpod or Dart Frog backend (third layer to maintain, frequent breaking changes,
small community). Node backend (would still need a Python service for ML and ILP).

## D3. Supabase-hosted Postgres with PostGIS and pgvector, plus a thin FastAPI

**Decision.** One Postgres database. Supabase provides hosting, Auth, Realtime (shared lists), row-level
security, and PostgREST for simple CRUD. A thin FastAPI service exposes the Python logic:
`/parse-list`, `/search`, `/compare`, `/optimize`. Ingestion and catalog workers write directly to
Postgres.

**Why.** Prices, store locations and semantic matches can be joined in one SQL query. Supabase ships
PostGIS and pgvector enabled and removes the need to build Auth and Realtime. Estimated cost at MVP is
40–100 USD per month (Supabase Pro at 25 USD verified; the rest estimated).

**Rejected.** Firebase/Firestore (no relational or geo queries), Appwrite and PocketBase (no pgvector
or PostGIS at the needed level), full FastAPI owning Auth and Realtime (more code to write, 60–150
USD per month estimated).

**Consequence.** Two API surfaces (PostgREST and FastAPI). RLS policies must be written carefully.
Supabase Edge Functions are TypeScript, so we do not use them for logic.

## D4. Canonical product model with three flexibility levels

**Decision.** Every chain item maps to a canonical product with a confidence score. The user picks
per item: exact (barcode), any brand (critical attributes fixed), close substitute (soft attributes
open). Smart defaults per category: staples default to "any brand", cosmetics to "exact".

**Why.** Barcode comparison cannot see private label or chain-internal codes, which is where the
biggest savings are. The flexibility control is what makes substitutions acceptable to users: they
chose the rule.

## D5. Precision over recall in matching

**Decision.** Target 98% or higher precision at the "any brand" level. Recall is secondary. Hard rules
on critical attributes are applied after embedding similarity, never replaced by it. Medium-confidence
matches go to human review. User feedback ("not a good substitute") is a labeling signal.

**Why.** Rocha et al. (2024) and the market research both conclude that in price comparison a false
match hurts trust more than a missed one. Embeddings are a recall engine; they barely separate 3%
from 1% milk or fresh from frozen.

## D6. Unit price is the comparison basis

**Decision.** Normalize every item to price per 100 g, per 100 ml, or per unit. Weighed produce per kg,
labeled estimated. Multipacks parsed to total quantity. Comparisons within a flexibility level rank by
unit price. Store choice ranks by basket total of effective prices.

**Why.** Matches Israeli shelf-labeling rules, so the app agrees with what the shopper sees. Makes
"any brand" fair across pack sizes.

## D7. Net saving versus the user's own store

**Decision.** The headline number is always basket saving minus travel cost minus the user's stated
value of an extra stop, compared to the store the user said they normally use.

**Why.** "Versus the most expensive chain" is the inflated number competitors use and the authority
warns against. Users abandon when the promised saving does not appear at checkout.

## D8. Separate static SEO pages, same domain

**Decision.** 50–200 category and leading-product pages generated from the catalog at build time, on
the main domain. Grow the set over time.

**Why.** Indexing takes months, so it must start with the MVP. The two fastest-moving competitors are
built on SEO pages. This is also where the methodology page and the monthly basket index live.

## D9. Heuristic optimizer first, MILP second

**Decision.** Phase 1: take the N nearest stores, enumerate every subset of size up to K (N=10, K=2
gives 55 combinations), pick the cheapest item per subset, apply promos greedily. Phase 2: MILP with
OR-Tools CP-SAT or HiGHS to handle cross-item promos and quantity rounding exactly.

**Why.** Without cross-item promos the heuristic is exact and trivial to explain. The MILP is small
(40 items, 10 stores) and solves in tens of milliseconds, but it is extra complexity the MVP does not
need.

## D10. Trust and neutrality as product rules

**Decision.** Update timestamp on every price. "Price at checkout governs" footnote. Every substitute
labeled and reversible with a visible "why". Confidence shown on promos and extracted attributes
("unverified"). Report-a-gap button feeding quality checks. No sale of user data. No sponsored ranking.
Public methodology page and a public matching-quality metric.

**Why.** Every churn driver the research found is a trust failure. Pricez's data-selling model is the
neutrality gap we fill.

## D11. Privacy by design

**Decision.** Location rounded to neighborhood. Receipts (future) processed and deleted. No third-party
ad SDKs in the MVP. Explicit consent for location and receipts.

**Why.** Israeli privacy law amendment 13 treats location and purchase data as sensitive.

## D12. Monetization: freemium plus transparent partnerships, never chain commissions alone

**Decision.** Free core. Paid tier at 10–15 ILS per month for 3-store splits, unlimited alerts, full
history, family sharing. Later: clearly labeled referral partnerships with online stores, labeled
brand offers separate from ranking, anonymized aggregate market reports (not to chains), grants.

**Why.** MySupermarket closed when it depended on chain cooperation. Operating cost under 150 USD per
month means freemium can carry the product.
