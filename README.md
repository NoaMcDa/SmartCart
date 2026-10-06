# SmartCart

Semantic supermarket price comparison for Israel.

Paste a shopping list in Hebrew, choose how flexible you are on each item (exact product, any brand,
or close substitute), and SmartCart finds the cheapest store nearby and a two-store split that still
makes sense after travel cost. Every substitution is explained and reversible.

**Status:** pre-code. Research, decisions, roadmap and UI design are done. Phase 0 (data foundation)
is next.

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
| [docs/research/](docs/research/) | The two original research documents (Hebrew) |

## Design

Interactive design canvas: https://claude.ai/artifact/VRNDChNKiHym9nG5r5dGML (private link).
Artboard sources are mirrored in `docs/design/artboards/`.
