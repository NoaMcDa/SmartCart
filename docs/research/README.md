# Research

Two Hebrew research documents from October 2026, kept verbatim. They are the primary sources for
everything in `docs/`. Both separate verified facts from the author's estimates; preserve that
distinction when citing them.

## 2026-10-market-research-and-product-plan.he.md

Market research and product plan for a semantic supermarket price comparison app in Israel.

Sections: competitors in Israel and abroad with a comparison table; regulation (Food Competition Law,
transparency regulations, file formats, update frequency, enforcement, 2023–2026 developments
including the authority's improved reporting model and the AWS project); data limitations and
handling; legal aspects (misleading presentation, privacy amendment 13, accessibility standard 5568);
how much a user can really save, facts versus estimates; savings levers; full system architecture
(ingestion, canonical catalog with a five-step matching method, MILP optimizer formulation, backend
and cost); roadmap in four phases; prioritized features and monetization; UX principles, navigation,
wireframe descriptions for every screen, key flows; risks and mitigations.

Conclusions drawn from it: see `../product-and-market.md`, `../architecture.md`, `../features.md`,
`../ux-design.md`.

## 2026-10-flutter-feasibility.he.md

Evaluation of Flutter for the client, Dart for the backend, and a recommended hybrid architecture.

Findings: Flutter 3.47 is mature for iOS and Android with good RTL and accessibility. Flutter Web is
unsuitable for SEO pages (canvas rendering, 1.1–1.5 MB bundle, accessibility opt-in). ML Kit does not
recognize Hebrew, so receipt OCR must run server-side. OR-Tools has no Dart bindings. Serverpod 4 is
the most mature Dart backend but adds a third layer with frequent breaking changes. Recommended:
Flutter mobile, Supabase, a thin FastAPI, Python workers, static SEO pages in Python/Jinja, about
40–100 USD per month at MVP.

What we took from it: the Supabase plus thin FastAPI architecture, the static SEO pages, the
server-side OCR decision, the RTL and accessibility practices, and the cost model. What we did not
take: Flutter itself. The MVP feature set needs nothing native, so the client is a web PWA; see
`../decisions.md` D1.
