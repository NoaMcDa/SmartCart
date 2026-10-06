# SmartCart

Semantic supermarket price comparison for Israel. The user pastes a shopping list in Hebrew, sets a
flexibility level per item, and gets the cheapest nearby store plus a two-store split that accounts for
travel cost. The differentiator is matching depth and trust, not being another barcode comparer.

The code base is at the pre-code stage. What exists is research, decisions, a roadmap, and a UI design.
Read this file first, then `docs/README.md` for the index.

## Key decisions (do not re-litigate without reading `docs/decisions.md`)

- **Web-first PWA, not a native app.** Next.js (or SvelteKit) on a DOM renderer, mobile-first layout,
  installable. A native app is a phase 2 decision driven by retention data. Flutter was evaluated and
  rejected for the MVP; React Native stays the fallback for native because it shares the language.
- **No Flutter Web for anything.** Canvas rendering kills SEO and adds 1.1–1.5 MB before app code.
- **Python owns data, ML and optimization.** Ingestion, canonical catalog, embeddings, cross-encoder
  judge, and the cart optimizer are all Python. No Dart or Node on the backend.
- **Postgres is the one database.** Supabase-hosted Postgres with PostGIS (store radius queries) and
  pgvector (semantic matching). Supabase provides Auth, Realtime and row-level security. A thin FastAPI
  service handles `/parse-list`, `/search`, `/compare` and `/optimize`.
- **Precision over recall in product matching.** Target 98% precision at the "any brand" level. One
  wrong match (3% milk shown as 1%) costs more trust than ten missed matches.
- **Net saving versus the user's own store is the hero number.** Never "versus the most expensive chain".
- **Trust signals are mandatory UI**, not polish: update timestamp on every price, "price at checkout
  governs" disclaimer, every substitute labeled, confidence on promos, report-a-gap button.
- **No selling user data. No sponsored ranking.** This is a stated differentiator against Pricez.
- **Hebrew RTL is the primary locale.** Prices and numbers render LTR inside Hebrew text. Use
  logical properties (start/end), never left/right. Font: Heebo.

## Stack summary

| Layer | Choice |
|---|---|
| Web app | Next.js PWA (SvelteKit acceptable), Tailwind or CSS variables, Heebo font |
| SEO pages | Static pages generated from the catalog (Python/Jinja or Next.js static), same domain |
| API | FastAPI (Python 3.12+), OpenAPI 3.1 |
| Managed backend | Supabase: Postgres 16, PostGIS, pgvector, Auth, Realtime, RLS |
| Ingestion | Python workers on an Israeli-IP VPS, wrapping `israeli-supermarket-scarpers` and `il-supermarket-parser` |
| Catalog ML | Rule normalization, LLM attribute extraction (batch, once per new item), BGE-M3 embeddings, cross-encoder or LLM judge, Streamlit/Label Studio review UI |
| Optimizer | Phase 1 heuristic (subsets of nearest stores), phase 2 MILP with OR-Tools CP-SAT or HiGHS |
| Cache | Nightly precomputed effective price per (canonical product, store); Redis optional |
| Storage | Object storage (R2/S3) for raw transparency files |

## Repository layout (target)

```
/apps/web            # Next.js PWA + static SEO pages
/services/api        # FastAPI: parse-list, search, compare, optimize
/services/ingest     # Python: scrapers/parsers -> Postgres, quality gates
/services/catalog    # Python: normalization, LLM extraction, embeddings, judge, review UI
/supabase            # migrations, RLS policies, RPC functions (SQL)
/docs                # everything below
```

## Conventions

- Hebrew UI copy lives in the code as literal text for the MVP. Prices use `₪` with a non-breaking
  space and are wrapped in an LTR span.
- Unit prices are stored per 100 g, per 100 ml, or per unit. Weighed produce is per kg and flagged
  "estimated".
- Price history stores change events only, partitioned by month. Base price per chain plus per-store
  exceptions.
- Every ingestion file passes quality gates (zero price, >3x jump, item-count drop, stale date) or is
  quarantined. Never load a failed file.
- Adapters per chain isolate the source schema from the internal model. The consumer authority is
  changing the reporting schema through 2026; both schemas must coexist.
- Never scrape chain online stores. Only the legally mandated transparency files.
- Location is stored rounded to neighborhood level. Receipts (future) are processed and deleted.

## Design

The UI design lives in a Claude Design canvas:
https://claude.ai/artifact/VRNDChNKiHym9nG5r5dGML (private; share from the page's Share menu).
Source artboards are mirrored in `docs/design/artboards/`. Tokens, screens and rules are in
`docs/ux-design.md`. Light and dark themes are both specified.

## Research

Two Hebrew research documents from October 2026 are the primary sources, kept verbatim in
`docs/research/`. English summaries with conclusions are in `docs/product-and-market.md` and
`docs/decisions.md`. When a number is cited, the research marks which are verified facts and which are
the author's estimates. Keep that distinction when quoting.

## Working with this repo

- Phase 0 (data foundation) comes before any UI code. See `docs/roadmap.md`.
- When adding a chain adapter, add a regression fixture from a real file and a quality-gate test.
- When touching matching logic, run the gold-set evaluation and report precision per flexibility level.
- Keep the research distinction between "verified" and "estimate" in any doc you write.
