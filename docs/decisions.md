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

**Confirmation, 2026-10-06 (phase 0, issue #14).** Supabase-hosted Postgres is confirmed for phase 0;
no override. Reasons: (1) PostGIS and pgvector are available as managed extensions, so the store
radius query and the semantic matching join live in one database, which is the property the
architecture relies on; (2) the phase 0 workload is small (batched nightly and hourly writes from one
VPS, no user traffic), so a managed instance removes operations work from a solo developer, and
Supabase Pro at 25 USD per month is a verified price while the 40-100 USD per month MVP total stays an
estimate; (3) nothing in phase 0 depends on Supabase-only features (Auth, Realtime and RLS arrive in
phase 1, Track B), so moving to self-hosted Postgres later is a dump-and-restore, not a rewrite. The
trigger to revisit is a measured one: sustained write latency from the Israeli VPS to the chosen
region, or a compute bill that exceeds a self-hosted VPS by a wide margin. **The project is not yet
provisioned.** The owner follows `infra-provisioning.md`; the acceptance items of #14 that need a
live database stay open until that is done.

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

## D13. Phase 0 chain list: ten chains, six of them with hourly deltas

**Date.** 2026-10-06 (phase 0, issue #9).

**How to read the evidence labels.** The research keeps verified facts apart from the author's
estimates, and this decision keeps the same split with three labels.
- **verified (research)**: stated as fact in `research/2026-10-market-research-and-product-plan.he.md` or in `product-and-market.md`; the source named in the research is given.
- **verified (upstream source)**: read directly from the source of `il-supermarket-scraper` 1.0.15 and `il-supermarket-parser` 1.0.12 (the OpenIsraeliSupermarkets packages, installed and read on 2026-10-06). This is a primary source about what the tools do today, not a statement from the research, and it says nothing about portal uptime.
- **estimate**: anything else, including general knowledge of chain size. Estimates must be replaced with measured values (see "Consequences").

**Context.** Phase 0 ingests the largest chains first, not all of the 30 to 35 portals the open source
tools cover (verified, research section 2.1). Every other ingestion issue depends on the list. Two
facts about the inputs limit how rigorous the ranking can be.
- **The research contains no per-chain market share figure.** The only chain-level numbers it gives are enforcement fines (2021: Rami Levy 607k ILS, Shufersal 405k, King Store 337k, Machsanei Hashuk 324k; verified, Consumer Protection Authority sanctions, research section 2.1) and basket prices from press surveys (Rami Levy 908.49 ILS versus Tiv Taam 1,147.45 ILS on 67 items, Maariv; verified, research section 3.1). The fines and the baskets show that those chains publish files and fall under the law, which is a coverage fact, not a share fact. The ranking below therefore uses a size tier from general knowledge of the market, and every tier is an **estimate**. The tier must be replaced by a sourced figure (for example a Competition Authority concentration report) before D13 is used in any public claim about coverage.
- **Portal reliability has not been measured.** The research verifies one reliability fact: laibcatalog blocks cloud IP ranges (Segalil, cited in research section 2.3). Everything else about uptime is unmeasured until the Phase 0 nightly loads produce data, so the reliability notes below are about portal type and known quirks, not uptime.

**Selection criteria**, in order: (1) size tier, estimate; (2) the chain is named in the research as a
chain that publishes (fined, surveyed or listed by a competitor), which makes it verified to be in
scope of the law; (3) coverage in the upstream scraper and parser, so adapters wrap existing code
rather than write scrapers; (4) portal diversity, so that the adapter framework is exercised against
every engine type (own portal, Cerberus, laibcatalog, Bina, the Carrefour-style portal) before
phase 1; (5) no chain whose portal needs special handling beyond what phase 0 can absorb.

**Decision.** Ingest these ten chains in phase 0. Chain ids are the identifiers in the upstream scraper
(verified, upstream source).

| # | Chain | Chain id | Portal type | Size tier | Evidence and reliability note |
|---|---|---|---|---|---|
| 1 | Shufersal (upstream says it includes the BE brand) | 7290027600007 | Own portal, `prices.shufersal.co.il`, paginated HTML listing (verified, upstream source; the research confirms Shufersal has an independent portal) | Large (estimate) | Fined 2021 (verified, research). On the supported list of the competitor Oshek (verified, research section 1.1). The listing is paginated, so the adapter must page through all of it. No cloud-IP block is documented for this portal (neither verified nor refuted). |
| 2 | Rami Levy | 7290058140886 | Cerberus on `publishedprices.co.il`, public username `RamiLevi` (verified, upstream source) | Large (estimate) | Fined 2021 and used in the 908 versus 1,147 ILS basket (verified, research). Upstream notes the former Cofix scraper is folded into Rami Levy (verified, upstream source). Cerberus is one portal shared by several of our chains, so one outage can hit several chains at once (estimate). |
| 3 | Victory | 7290696200003, 7290058103393 | laibcatalog JSON API (`/webapi/api/getfiles`). The older Matrix ASPX scraper is marked deprecated upstream in favor of this source (verified, upstream source) | Mid to large (estimate) | **Needs an Israeli IP**: laibcatalog blocks cloud IP ranges (verified, research citing Segalil). On Oshek's list (verified, research). The research also reports, from user comments, that Victory blocked MySupermarket shortly before it closed (reported, not verified). Upstream tests note the laibcatalog listing is empty between midnight and about 08:00 Israel time until the morning republish (verified, upstream source), so the daily full job must not assume files exist at 05:00. |
| 4 | Yeinot Bitan and Carrefour (includes the former Mega) | 7290055700007 | Own chain portal `prices.carrefour.co.il`, served by the upstream engine named "PublishPrice" (not Cerberus) (verified, upstream source) | Large (estimate) | The upstream Mega scraper is marked deprecated and merged (verified, upstream source), so Mega is not a separate entry. Yeinot Bitan is on Oshek's list (verified, research). The chain is in transition between brands (estimate), so store naming in the Stores file needs a regression fixture. |
| 5 | Hazi Hinam | 7290700100008 | Own portal `shop.hazi-hinam.co.il/Prices`, paginated HTML (verified, upstream source). An earlier Cerberus scraper is commented out upstream, which indicates the chain moved off Cerberus (inference) | Mid (estimate) | On Oshek's list (verified, research). The portal sits on the chain's online shop domain, so the adapter must fetch only the transparency files (rule: never scrape online stores). Date format and pagination differ from Shufersal. |
| 6 | Tiv Taam | 7290873255550 | Cerberus, public username `TivTaam` (verified, upstream source) | Mid (estimate) | The high-price end of the 67-item basket (verified, research), so it matters for the "net saving versus the user's own store" number. On Oshek's list (verified, research). |
| 7 | Osher Ad | 7290103152017 | Cerberus, public username `osherad` (verified, upstream source) | Mid (estimate) | Discount format (estimate). Appears in the research's wireframe split example, which is a design example and not data. Shares the Cerberus dependency with chains 2, 6 and 8. |
| 8 | Yohananof | 7290803800003 | Cerberus, public username `yohananof` (verified, upstream source) | Mid (estimate) | Appears in the research's alert example (a design example, not data). Shares the Cerberus dependency. |
| 9 | Machsanei Hashuk | 7290661400001, 7290633800006 | laibcatalog JSON API; the older Matrix scraper is deprecated upstream (verified, upstream source) | Mid (estimate) | Fined 2021 (verified, research). **Needs an Israeli IP** (laibcatalog, verified, research). Same midnight-to-08:00 empty listing caveat as Victory. Discount-oriented (estimate), so among the chains the exemption bill could remove (see risk below). |
| 10 | King Store | 7290058108879 | Bina (`kingstore.binaprojects.com`, plain HTTP, ASPX) (verified, upstream source) | Smaller (estimate) | Fined 2021 (verified, research). The only Bina chain in the list; it is included to exercise the fourth engine type. Also among the chains the exemption bill could remove. |

Tie-break rule if the schedule slips: drop King Store first, then Machsanei Hashuk. The roadmap's exit
criterion (two consecutive weeks of more than 95 percent nightly load success across the chosen chains)
is then measured over eight chains.

**Main chains for hourly deltas.** Issue #49 asks D13 to define "main". The main chains are 1 to 6
(Shufersal, Rami Levy, Victory, Yeinot Bitan and Carrefour, Hazi Hinam, Tiv Taam). Chains 7 to 10 get
the daily full sync only until the nightly pipeline is stable. This split rests on the size tier
(estimate) and can be changed in configuration. Notes for the delta schedule: Victory has the laibcatalog
overnight gap, and the Cerberus chains (2, 6, 7, 8) share one portal, so their deltas should be spread
within the hour, not fired together.

**Upstream coverage.** All ten chains have an active scraper (chains 3 and 9 through their "new source"
entries) and a parser in the upstream packages (verified, upstream source). The upstream project is
beta (stated in the research and the architecture doc), so each chain still gets a regression fixture
from a real file and a quality-gate test (rule in CLAUDE.md). Which upstream version is pinned is for
the adapter issues, not for this decision.

**Deferred to phase 1 or later**, so phase 1 can see the gap. The upstream scraper lists 33 active
entries (verified, upstream source); the other 23 are deferred. Reasons are grouped.
- **Super-Pharm** (own portal `prices.super-pharm.co.il`, plain HTTP) and **Good Pharm**: pharmacy chains fall under the law (verified, research), but their catalogs are mostly non-food, which belongs to the matching work of phase 1 (taxonomy and attributes for cosmetics and drugstore items), not to the food-first data foundation. Revisit when the taxonomy covers pharmacy categories.
- **Convenience and fuel-station operators** (Dor Alon, Yellow, Stop Market and similar): little weight in a weekly shopping list (estimate).
- **Smaller regional and specialty chains** (for example Keshet Teamim, Super Yuda, Zol Vebegadol, Super Sapir, Shuk Ahir, Polizer, Salach Dabach, Meshnat Yosef, Maayan 2000, Het Cohen, Bareket, City Market, Shefa Birkat Hashem, Fresh Market and Super Dosh): each adds a portal dialect for a small share of baskets (estimate). They matter for the periphery audience named in the roadmap, so they are the first additions in phase 1 once the adapter framework is proven.
- **Netiv Hesed** (kosher-conscious audience): upstream records that its portal lists zero files on Saturday and that Cloudflare blocks requests without a browser User-Agent (verified, upstream source). Deferred because of the extra handling, although the audience is one of the roadmap's first target groups.
- **Wolt** (delivery platform, an online channel): excluded until the online-store identification issue (#53) is done; online prices differ from store prices (verified, research).
- **Deprecated upstream entries** (the old Victory and Machsanei Hashuk Matrix scrapers, Mega, Quik, Cofix, two City Market branches): not ingested; upstream marks them as replaced, merged, closed or folded.

**Risk: the exemption bill.** A bill proposed by MKs Yinon Azulai and Moshe Passal would exempt more
retailers from transparency by raising the turnover threshold. That the proposal exists is verified
(research section 2.2); the current threshold of 250M ILS per year is verified (research section 2.1).
The research gives no figures on the bill's effect and no passage status, so how many chains would be
removed is unknown. If it passes, the smaller and cheaper chains would stop publishing first, which is
the coverage the product most needs for the "cheapest nearby store" claim. Chains 9 and 10 are the most
exposed of the ten (estimate; no turnover figures are in the research). Mitigations:
- Adapters are per chain behind one contract, so losing a chain is a configuration change, not a rewrite (`architecture.md` section 1).
- Coverage per chain is shown on the internal dashboard (issue #46), so a chain that stops publishing is visible within a day.
- The product must never claim "all stores in Israel"; coverage is stated by chain on the methodology page.
- **How it is tracked:** (1) watch the bill's status on the Knesset site (bill search and the agendas of the committee that handles it) and the Consumer Protection Authority's announcements; (2) a quarterly check, the first on 2027-01-05, recording the bill's stage (not tabled, preliminary reading, committee, passed) and the effect on the chain list; (3) the result is noted in `roadmap.md` under the Phase 0 and Phase 1 decisions. The roadmap edit itself is not part of this change and is flagged for the maintainer.

**Alternatives rejected.**
- All 30 to 35 portals in phase 0: each portal has its own dialect and failure mode, the upstream project is beta, and the exit criterion (95 percent success over two weeks) becomes unreachable for a solo developer. Rejected for the schedule.
- The five largest chains only: covers most baskets (estimate) but leaves the laibcatalog, Bina and Carrefour-style engines untested until phase 1, and drops the cheap chains that carry the "cheapest nearby store" value. Rejected for diversity and for the savings claim.
- Choosing by portal reliability alone: unmeasured today, and it would pick the most convenient portals instead of the chains users shop at.

**Consequences.**
- Size tiers are estimates and must be replaced with a sourced figure before launch; owner: whoever writes the methodology page.
- Reliability becomes a measurement: after the first two weeks of loads, update this table with the observed per-chain success rate and mark it verified (measured). A chain below the 95 percent bar moves to the deferred list.
- Chains 3 and 9 pin the ingestion VPS to an Israeli IP (see `infra-provisioning.md`); acceptance of #22 uses them as the "known to block cloud IPs" test.
- The daily full job must tolerate the laibcatalog empty window; the infra timers run the full sync twice (06:00 and 08:30 Israel time), which is safe because loads are idempotent by file hash.
- Cerberus usernames and portal hosts come from upstream and may change; adapters should read them from configuration, not hard-coded constants (for the adapter issue).

## D14. Attribute extraction model: Claude Sonnet 5.5 in batch mode, rules as the baseline

**Date.** 2026-10-07 (phase 1, issue #25). **Status:** provisional. The comparison on a labeled
sample that issue #25 asks for has not been run; it needs an API key and loaded items. Revisit this
decision with its results.

**Context.** Matching step B extracts structured attributes once per new chain item
(`architecture.md` section 3). The research proposes "a cheap commercial LLM in batch mode, or an open
Hebrew LLM (Dicta-LM) run locally", and estimates the full extraction at "tens of dollars" (estimate,
research section 4.3). GPT-4-class models led every product entity-matching benchmark in Peeters, Der
and Bizer (arXiv 2310.11244; verified, published result), which supports a strong commercial model
over a small local one for the judgement-heavy part. Chain files do not carry kosher or allergens
structurally (verified, research), so those values are unverified whatever extracts them.

**Decision.**
- Default extractor in code: the deterministic **rule extractor** (`EXTRACTOR=rule`). It needs no key,
  costs nothing, and is the baseline any model must beat.
- Model extractor: **`claude-sonnet-5-5` through the Message Batches API** (`EXTRACTOR=claude`), one
  request per item, structured output with a strict JSON schema whose product types and taxonomy ids
  are closed vocabularies, adaptive thinking with no budget at low effort, `max_tokens` 1024, the
  system prompt cached. Invalid output goes to the retry queue, never to the table as a trusted value.
- Kosher and diet flags are always unverified unless a human confirmed them, whichever extractor runs.

**Why Sonnet 5.5 in batch.** It is the current Sonnet: cheaper than the Opus tier and capable on
Hebrew text and structured output (general knowledge, not measured here). Batches bill at 50% of list
price and suit a job that runs once per new item with no latency need. Structured outputs guarantee
parseable JSON against the schema, which removes most of the failure handling a free-text answer
needs. Dicta-LM locally avoids per-token cost but needs a GPU host and our own constrained decoding,
and has no published entity-matching result in the research.

**Cost (estimate).** Rates: $1 per million input tokens and $5 per million output tokens with the
batch discount (Sonnet 5.5 list price $2 / $10; pricing page as cached in the SDK documentation,
2026-09-25), cache reads 0.1x input. Per item, assuming a system prompt of about 6,000 to 7,000 tokens
(the product type and taxonomy vocabularies; Hebrew tokenization not measured), about 150 tokens of
item input, and 150 to 450 output tokens including low-effort thinking: about $0.002 to $0.003 with the
prompt cached, about $0.008 to $0.009 without. That gives roughly $40 to $120 for an MVP slice of
20,000 to 40,000 items (the items whose rule-extracted type is one of the 222 MVP types; slice size is
an estimate), and $300 to $500 for 170,000 items with caching, more without. This is about ten times
the research's "tens of dollars", mostly because of the vocabulary prompt and thinking tokens. Levers
before a full run: extract once per barcode across chains, send only items the rule extractor places
in an MVP block or cannot place, trim the vocabularies per department, and measure a 1,000-item pilot
with `smartcart-catalog cost-report`.

**Pending, needs a human and a key.**
1. A labeled sample (at least 300 items across departments, drawn from the gold set of issue #29),
   scored per attribute for the rule extractor, Sonnet 5.5 batch, and Dicta-LM if a GPU host is
   available. Record precision of `product_type`, `fat_pct` and `state` (the critical keys) here.
2. The cost of the first run on the MVP catalog from the cost report, against the estimate above.

**Alternatives considered.**
- Opus tier: stronger, about twice the per-token price of Sonnet 5.5; kept as the fallback if the
  sample shows Sonnet errors on critical keys.
- Haiku 4.5: cheaper; rejected for now because critical-key errors cost more than tokens (D5).
- Dicta-LM locally: see above; stays in the comparison.
- Rules only: free and deterministic, but keyword tables miss unseen phrasing and brands; kept as the
  baseline and the no-key default.

**Consequences.** `ANTHROPIC_API_KEY` becomes a secret of the catalog worker when `EXTRACTOR=claude`.
Items are sent to an external API: they are public price-file data with no user data, so D11 is not
affected. The model name, effort and batch size are configuration, so the comparison can switch them
without code changes. Details: `catalog.md` section 4.
