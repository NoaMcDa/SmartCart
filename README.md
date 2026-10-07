# SmartCart

Semantic supermarket price comparison for Israel.

Paste a shopping list in Hebrew, choose how flexible you are on each item (exact product, any brand,
or close substitute), and SmartCart finds the cheapest store nearby and a two-store split that still
makes sense after travel cost. Every substitution is explained and reversible.

**Status:** phases 0 (data foundation), 1 (MVP) and 2 (advanced savings) are built and tested, on
synthetic data only: the chain transparency files, the gold set and every price shown are synthetic
until the infrastructure exists. The infrastructure (Supabase project, Israeli VPS, object storage)
is not provisioned yet; see [docs/phase-2-status.md](docs/phase-2-status.md) for what is done, what
is blocked and the owner's runbook.

## Run it locally

One command brings up the whole stack on synthetic data: a throwaway Postgres (PostGIS and
pgvector), the migrations, the catalog seed, every chain's synthetic transparency files through the
real loader and quality gates, the matching pipeline, the nightly precompute and the API. Details,
expected counts and known gaps: [docs/fullstack.md](docs/fullstack.md).

```bash
uv sync                                    # Python 3.12+, uv
scripts/demo/up.sh                         # Postgres, pipeline, API on http://127.0.0.1:8000
uv run python scripts/demo/smoke.py        # HTTP smoke test of the MVP path

cd apps/web && npm ci                      # Node 22.12+
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 NEXT_PUBLIC_API_MOCK=0 npm run dev
# http://localhost:3000/onboarding: city רמת גן (the demo stores are there, not where you are),
# my store שופרסל; then paste a list (the one in scripts/demo/smoke.py) and compare

npm run e2e:fullstack                      # Playwright against the real API (builds the app)
cd ../.. && scripts/demo/down.sh           # stop the API and delete the throwaway database
```

Without Postgres binaries, start the database with `docker compose -f infra/docker-compose.yml up -d`
and export `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres` before `up.sh`.
Every number the demo shows is synthetic. CI runs the same steps in
`.github/workflows/fullstack.yml`.

## Documentation

Start at [`docs/README.md`](docs/README.md). For an AI assistant working in this repo, read
[`CLAUDE.md`](CLAUDE.md) first.

| Document | What it covers |
|---|---|
| [docs/product-and-market.md](docs/product-and-market.md) | Competitors, realistic savings, regulation, legal, positioning |
| [docs/decisions.md](docs/decisions.md) | Architecture decisions and why (web-first, no Flutter, Postgres stack) |
| [docs/architecture.md](docs/architecture.md) | Data pipeline, canonical catalog, matching, price comparison, optimizer |
| [docs/roadmap.md](docs/roadmap.md) | Phase 0 to phase 3, with exit criteria |
| [docs/features.md](docs/features.md) | Prioritized feature list and monetization |
| [docs/ux-design.md](docs/ux-design.md) | UX principles, screens, design tokens, light and dark themes |
| [docs/dev-setup.md](docs/dev-setup.md) | Tooling, tests, the local database and CI |
| [docs/fullstack.md](docs/fullstack.md) | The one-command full-stack demo, its smoke test and end-to-end suite |
| [docs/phase-2-status.md](docs/phase-2-status.md) | Status of every issue and the owner's runbook |
| [docs/research/](docs/research/) | The two original research documents (Hebrew) |

## Design

Interactive design canvas: https://claude.ai/artifact/VRNDChNKiHym9nG5r5dGML (private link).
Artboard sources are mirrored in `docs/design/artboards/`.
