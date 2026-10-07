# SmartCart documentation index

Everything here was produced in October 2026 from two research documents and a series of design
discussions. Phases 0, 1 and 2 are built (see phase-2-status.md). Read in this order if you are new:

1. [product-and-market.md](product-and-market.md): what the market looks like, what the product is, and why it can win.
2. [decisions.md](decisions.md): the architecture decisions, each with the reasoning and the alternatives rejected.
3. [architecture.md](architecture.md): how the system works end to end, from transparency files to a ranked cart split.
4. [roadmap.md](roadmap.md): phases 0 to 3 with deliverables and exit criteria.
5. [features.md](features.md): the prioritized feature list and monetization plan.
6. [ux-design.md](ux-design.md): UX principles, navigation, screen specs, design tokens, dark mode.
7. [research/](research/): the two original Hebrew research documents, kept verbatim.
8. [design/artboards/](design/artboards/): source of the UI design canvas.
9. [adapters.md](adapters.md), [ingestion.md](ingestion.md), [dashboard.md](dashboard.md), [dev-setup.md](dev-setup.md), [infra-provisioning.md](infra-provisioning.md): phase 0 engineering docs.
10. [catalog.md](catalog.md), [matching.md](matching.md), [api.md](api.md), [web.md](web.md), [seo.md](seo.md), [methodology.md](methodology.md), [beta-plan.md](beta-plan.md), [a11y-report.md](a11y-report.md), [phase-0-exit-report.md](phase-0-exit-report.md): phase 1 engineering docs.
11. [optimizer.md](optimizer.md): the phase 2 cart optimizer (MILP and the heuristic it is compared with).
12. [phase-2-status.md](phase-2-status.md): status of every phase 0, 1 and 2 issue, what is blocked, and the owner's runbook, in order.
13. [fullstack.md](fullstack.md): the one-command local run on synthetic data (`scripts/demo`), the real-API smoke test, the Playwright suite against the real API, and the gaps that run found.

## Facts versus estimates

The research documents are careful to separate verified facts (cited sources, pricing pages, laws,
academic papers) from the author's estimates (costs, timelines, savings ranges). The English documents
here keep that distinction. When you see "estimate", it is not a measured number.

## Glossary

| Term | Meaning |
|---|---|
| Canonical product | A product concept independent of brand and chain, e.g. "fresh milk 3%, 1 liter". Chain-specific items map to it. |
| Flexibility level | Per-item user setting: exact (barcode), any brand (same critical attributes), close substitute (soft attributes may differ). |
| Critical attribute | An attribute that must match at "any brand" level: fat percentage, fresh/frozen/chilled, size class. Kosher is never critical because it cannot be verified from chain data. |
| Soft attribute | An attribute that may differ at "close substitute" level: pack size, packaging type, nearby fat percentage. |
| Effective price | Shelf price after applying promos the user is eligible for, precomputed nightly per (canonical, store). |
| Unit price | Price per 100 g, 100 ml, or unit. The basis for all "cheaper" decisions. |
| Net saving | Basket saving minus travel cost minus the user's own value of an extra stop, versus the user's usual store. |
| Transparency files | The XML price, promo and store files Israeli chains must publish by law. |
| PriceFull / PromoFull | Daily complete files per store. Price / Promo are hourly deltas. |
