# Web app (`apps/web`)

The SmartCart PWA: Next.js App Router, Hebrew-first and right-to-left, light and dark themes from
the token table in `ux-design.md`, installable, with the app shell available offline. Decision
background: D1 (web-first PWA), D7 (net saving versus the user's own store), D10 (trust signals).

Phase 1 workstream W4a built the scaffold: tokens, theme, design-system components, shell, routes,
API client and mocks, PWA, guards and CI. Screens are filled in by W4b, W5 and W6 (see
[Ownership](#directory-ownership)).

## Run it

Node 22.12 or newer and npm.

```bash
cd apps/web
npm ci
npm run dev:mock          # same as NEXT_PUBLIC_API_MOCK=1 npm run dev; no backend needed
# open http://localhost:3000 and http://localhost:3000/design-system
```

Against a running `services/api`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_MOCK` | unset | `1` answers every API call from the MSW handlers in `src/mocks`, in process, on the server and in the browser |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI origin |
| `NEXT_PUBLIC_DISABLE_SW` | unset | `1` skips service worker registration in a production build |

`NEXT_PUBLIC_*` values are inlined at build time: set them before `npm run build`, not only before
`npm start`.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` / `npm run dev:mock` | Dev server (Turbopack); `dev:mock` turns the API mock on |
| `npm run build` / `npm start` | Production build / serve it (the service worker only registers in production) |
| `npm run lint` | ESLint (Next core-web-vitals + TypeScript + RTL guard for inline styles) and stylelint (RTL guard for CSS) |
| `npm run typecheck` | `next typegen` (route types) then `tsc --noEmit`, strict with `noUncheckedIndexedAccess` |
| `npm test` | Vitest unit tests (jsdom): components, theme, tokens versus the doc table, AA contrast, mock API, RTL guard |
| `npm run e2e` | Playwright against `next start` on port 3100. Run `npm run build` first |
| `npm run gen:api` | Regenerate `src/api/types.ts` from `src/api/openapi.json` (commit the output; CI fails if it is stale). Not run through Prettier (`.prettierignore`), so it matches `services/api/scripts/gen_ts_client.sh`, which the Python CI checks too |
| `npm run lhci` | Lighthouse CI on `/`, `/compare`, `/design-system` (accessibility, best practices, SEO). Needs a build and `CHROME_PATH` |
| `npm run fetch:fonts` | Re-download Heebo into `public/fonts` (one-time setup, output committed) |

Playwright is pinned to 1.56.1 because that matches the Chromium revision preinstalled in the
Claude Code containers (`/opt/pw-browsers/chromium-1194`). Elsewhere run
`npx playwright install chromium` once, or set `PW_CHROMIUM_PATH` to a Chromium binary.

## Stack and why

| Piece | Choice | Note |
|---|---|---|
| Framework | Next.js 16.4 App Router, React 19.3 | Turbopack for dev and build |
| Language | TypeScript 5.9, strict | TS 7 (the native port) is out, but `typescript-eslint` and `openapi-typescript` peer ranges stop below it |
| Styling | CSS Modules plus CSS variables | Tokens are the source of truth; no Tailwind |
| Lint | ESLint 9 flat config, stylelint 17 | ESLint 10 is out; staying on 9 until the React plugins in `eslint-config-next` declare support |
| Unit tests | Vitest 5, Testing Library, jsdom 29 | jsdom 30 needs Node 22.22.2+ |
| E2E | Playwright 1.56.1, Chromium | See above |
| API types | `openapi-typescript` 7 + `openapi-fetch` | Generated from the committed contract |
| Mocks | MSW 3 handlers, resolved in process with `getResponse` | No mock service worker, so it never fights the PWA worker |
| PWA | Hand-written `public/sw.js`, `app/manifest.ts` | See [PWA and offline](#pwa-and-offline) |

## Directory ownership

Only W4a and W4b edit `src/components/ui`, `src/components/shell`, `src/components/theme`,
`src/styles` and the root layout. Everyone else composes them; if a component is missing or wrong,
ask W4a/W4b rather than forking a local copy.

| Path | Owner | Contents |
|---|---|---|
| `src/app/layout.tsx`, `src/app/globals.css`, `src/app/fonts.ts`, `src/app/manifest.ts`, `src/app/not-found.tsx` | W4a | Root document (`<html lang="he" dir="rtl">`), fonts, theme bootstrap, manifest |
| `src/app/(shell)/` | W4a | `/alerts`, `/scan` (phase 2 placeholders), `/offline` (service worker fallback), `/design-system` |
| `src/app/(core)/` | W4b | `/` list builder, `/compare` results, `/compare/substitution/[id]` |
| `src/features/{list,compare,substitution}` | W4b | Screen logic and screen-specific components |
| `src/app/(secondary)/` | W5 | `/onboarding`, `/product/[id]`, `/profile`, `/split`, `/map`, `/store-mode` |
| `src/features/{onboarding,product,profile,split,map,store}` | W5 | Screen logic and screen-specific components |
| `src/app/(seo)/` | W6 | `/methodology`, `/c/[slug]`, `/p/[slug]`, `/basket-index` (D8, same domain). W6 may give this group its own layout |
| `tests/a11y` | W6 | Accessibility tests |
| `src/components/ui`, `src/components/shell`, `src/components/theme`, `src/components/pwa`, `src/styles` | W4a, W4b | Design system and shell |
| `src/api` | W4a (contract owned by `services/api`) | `openapi.json` (copied from the API), generated `types.ts`, `client.ts` |
| `src/mocks` | W4a; W4b and W5 may add fixtures | MSW handlers and fixtures |
| `public/sw.js`, `public/icons`, `public/fonts` | W4a | PWA worker, icons, Heebo |

`/profile` must keep the "ערכת צבעים" section with `ThemePreferenceControl` (issue #63).

Every route currently renders `PlaceholderPage` (a server component with the Hebrew h1). Replace
the page body; keep the h1 text or update `tests/e2e/routes.ts` in the same change.

## Design tokens

`src/styles/tokens.css` holds every row of the `ux-design.md` token table as a CSS variable.
Naming: the table name in kebab case with an `sc` prefix.

| Table | CSS variable |
|---|---|
| bg, surface, subtle, border, divider | `--sc-bg`, `--sc-surface`, `--sc-subtle`, `--sc-border`, `--sc-divider` |
| text, muted, faint | `--sc-text`, `--sc-muted`, `--sc-faint` |
| accent (fill), accentFg, accentSoft | `--sc-accent`, `--sc-accent-fg`, `--sc-accent-soft` |
| brandBg / brandFg, exactBg / exactFg | `--sc-brand-bg`, `--sc-brand-fg`, `--sc-exact-bg`, `--sc-exact-fg` |
| warnBg / warnFg, goodBg / goodFg, badFg | `--sc-warn-bg`, `--sc-warn-fg`, `--sc-good-bg`, `--sc-good-fg`, `--sc-bad-fg` |

Extra colors the artboards use outside the table: `--sc-on-accent` (white text on accent),
`--sc-on-warn`, `--sc-handle` (sheet handle), `--sc-map-bg|grid|road`, `--sc-scrim`, and shadows.
Layout tokens: `--sc-touch` (44 px), `--sc-gutter` (20 px, 16 px under 380 px),
`--sc-content-max` (1200 px), radii `--sc-radius-card` (16), `-input` (14), `-control` (12),
`-small` (10), `-sheet` (22), `-pill`.

Theme selection, in this order: light on `:root`; dark under `prefers-color-scheme: dark` guarded
by `:root:not([data-theme="light"])`; dark under `:root[data-theme="dark"]`. `[data-theme]` on any
element also scopes a theme to a subtree (the `/design-system` panels use this).
`src/styles/tokens.test.ts` parses the doc table and fails when a value drifts, when the two dark
blocks differ, or when a text pair drops below 4.5:1 in either theme.

Rules (`ux-design.md`): green (`good`) only for savings and matched attributes, amber (`warn`) for
estimated, unverified and confirmations, red (`bad-fg`) only for missing items and "not a good
substitute". Meaning never by color alone: every chip and tag carries an icon and text. Never
hard-code a color in a component; use a token.

## Dark mode (#63)

- `THEME_INIT_SCRIPT` (inline in `<head>`) reads `localStorage["sc-theme"]` and the OS preference
  and sets `data-theme` before first paint, so there is no flash. Storage access is wrapped in
  try/catch.
- `ThemeProvider` keeps the choice (`system` / `light` / `dark`) in localStorage, follows OS
  changes live while on `system`, sets `data-theme` on `<html>`, and points both
  `<meta name="theme-color">` tags at the chosen theme's surface color (`#FFFFFF` / `#1F1F1D`)
  when the user overrides the OS.
- `ThemeToggle` is the two-state header switch from the artboards (`role="switch"`,
  `aria-label="מצב כהה"`, moon in light, sun in dark; the icon is picked by CSS so it is right
  before hydration). `ThemePreferenceControl` is the three-state choice in Profile. Both read the
  same context and stay in sync.
- Not done yet: saving the choice to the signed-in profile (needs Auth; W5).

## Components (`src/components/ui`)

Import from `@/components/ui`. Every component is on `/design-system`, light and dark side by side.

| Component | Notes |
|---|---|
| `Button` | `variant` primary / secondary / outline / ghost, `size` md (48 px) / sm (44 px), `tone="bad"`, `href` renders a Next link |
| `Chip`, `FlexChip` | Pill chips. `FlexChip level="exact" \| "any_brand" \| "close"` (lock / tag / refresh icon, the three color pairs); interactive chips get a 44 px hit area and `aria-label="רמת גמישות: …"`; toggle chips set `aria-pressed` |
| `Tag` | `matched` (check, green), `unverified` (info, amber), `differs` (neutral), `missing` (x, red), `estimated` (warning, amber) |
| `Card`, `CardRow` | 16 px radius surface; `variant="recommended"` = 2 px accent border; `padding="none"` plus `CardRow` for divided lists |
| `BottomSheet` | Modal dialog: `aria-modal`, labelled by the title, focus moves in and is trapped, Escape and the scrim close, focus returns to the opener, page scroll locked; centered at 768 px and up |
| `Stepper` | 44 px buttons, Hebrew labels ("הוסיפי כמות של …"), value is an LTR island, `step` and `unit` for weighed goods |
| `Switch` (alias `Toggle`) | `role="switch"` with a visible label, 44 px hit area |
| `SegmentedControl` | Radiogroup with roving tabindex; arrow keys follow the visual direction (ArrowLeft = next in RTL) |
| `Price`, `PriceRange` | `<span dir="ltr">₪ 389</span>` with a non-breaking space; drops agorot on whole amounts like the artboards; `tone="good"` for savings only |
| `Skeleton`, `SkeletonText` | Decorative loading placeholders |
| `icons.tsx` | Inline stroke SVGs from the artboards. `IconChevronBack` points right and `IconChevronNext` points left (RTL) |

Shell: `AppShell` (skip link, `TopBar`, `<main>` capped at 1200 px, `BottomNav`). The bottom nav
shows below 768 px with the five tabs right to left (Lists, Compare, Scan raised, Alerts, Profile);
from 768 px the top bar carries the same sections. The map is a view inside Compare, so `/map` and
`/split` highlight Compare.

## RTL rules and the guard

- `<html lang="he" dir="rtl">`. Logical properties only: `margin-inline`, `padding-inline`,
  `inset-inline-start/end`, `border-inline-*`, `border-start-start-radius`, `text-align: start`.
- Prices and numbers inside Hebrew text go through `Price` (or a `dir="ltr"` span).
- `npm run lint` fails on physical `left`, `right`, `margin-left/right`, `padding-left/right`,
  `border-left/right*`, `float`, `text-align: left|right` in CSS (stylelint,
  `.stylelintrc.json`) and in JSX `style` objects (ESLint `no-restricted-syntax`,
  `eslint.config.mjs`). `tests/unit/rtl-guard.test.ts` proves both catch violations.
- Copy uses the artboards' feminine imperative ("השווי", "שמרי", "הוסיפי").

## API layer and mocks

`src/api/openapi.json` is the contract from `services/api`. `npm run gen:api` writes
`src/api/types.ts`; never edit it. `src/api/client.ts` exports the raw `api` client plus typed
helpers: `parseList`, `compare`, `optimize`, `search`, `reportGap`, `substitutionFeedback`,
`health`. They throw `ApiError` (status, detail) on non-2xx. Request inputs make server-defaulted
fields optional (`CompareInput`, `OptimizeInput`, `BasketItemInput`); responses use the generated
types as they are.

With `NEXT_PUBLIC_API_MOCK=1` the client resolves requests against `src/mocks/handlers.ts` in
process. Unit tests can use `src/mocks/node.ts` (`setupServer`). The fixtures follow the
artboards ("הקנייה השבועית", 9 items, Modi'in, prices updated 06:40). They are design values for
building screens, not real prices:

| Plan | Fixture |
|---|---|
| Recommended single store | רמי לוי · מודיעין, ₪389, 4.2 km, 3 substituted, 1 missing (cottage), net saving ₪57 |
| Split | רמי לוי (6 items) + אושר עד (3 items), ₪371, +12 min, ₪9 travel. Net saving follows the API arithmetic, so with the default ₪25 stop value it is ₪41 (basket saving ₪75) |
| Minimum effort / baseline | שופרסל דיל · מודיעין, ₪446, 1.1 km, the home store (`home_store_id` 103) |

`/compare` also returns יוחננוף ₪402 and ויקטורי ₪418 (complete) and אושר עד ₪100.20 (missing
salmon), sorted complete baskets first. Every store total equals the sum of its line totals.
`/parse-list` splits on commas and newlines, reads leading quantities ("2 רסק עגבניות"), flags
"שמן זית" for confirmation with candidates, marks produce as weighed, and returns `not_found` for
unknown text. `/optimize` drops the split when its net saving is below `min_split_saving`.

## PWA and offline

- Manifest: `src/app/manifest.ts` (`/manifest.webmanifest`): name SmartCart, short name
  סמארטקארט, `lang: he`, `dir: rtl`, standalone, icons 192, 512, maskable 512 and SVG. iOS gets
  `apple-touch-icon.png` (180) and `apple-mobile-web-app-capable`. Icons are generated from
  `public/icons/*.svg` by `node scripts/gen-icons.mjs`.
- `theme-color`: two media-specific metas (light `#FFFFFF`, dark `#1F1F1D`), retargeted by
  `ThemeProvider` on a manual choice.
- Service worker: `public/sw.js`, hand-written, registered by `ServiceWorkerRegistrar` in
  production only. On install it precaches `/` and `/offline`, parses their HTML and CSS for
  `/_next/static` assets (JS, CSS, the Heebo woff2 files) and precaches those. Navigations are
  network first, falling back to the cached page, then `/offline`. Hashed static assets are cache
  first. API calls (cross origin) and RSC payloads are never cached here.
- Why hand-written: Next 16 builds with Turbopack. `next-pwa` is unmaintained and webpack only;
  `@serwist/next` needs a webpack build or an extra esbuild-based CLI step. The worker above has no
  build coupling, about 130 lines, and the e2e test proves it by killing the server.
- Offline data (lists, prices) is out of scope here (store-mode issue).

### Manual checks (not automatable in CI)

Lighthouse 12 removed the PWA category, so installability is checked in the browser:

1. `npm run build && npm start`, open Chrome DevTools > Application > Manifest: no installability
   errors, icons render, `dir` rtl.
2. Android Chrome on a real device (HTTPS or `chrome://inspect` port forwarding): the install
   prompt appears; the installed app opens standalone; airplane mode, reopen: the shell loads.
3. iOS Safari: Share > Add to Home Screen; the icon and Hebrew title appear; launches standalone.

`npm run lhci` (and CI) runs Lighthouse for accessibility (min 0.95), best practices (0.9) and SEO
(warning) on `/`, `/compare` and `/design-system`.

## Fonts

Heebo 400, 500, 600 and 700 are self-hosted: `public/fonts/Heebo-*.woff2` (full static files from
Google Fonts, Hebrew and Latin) with `public/fonts/OFL.txt` (SIL Open Font License 1.1).
`src/app/fonts.ts` loads them with `next/font/local`, which serves them from `/_next/static/media`
and preloads them. The e2e test "Heebo is served locally" blocks every non-localhost request and
asserts all four weights load and no Google Fonts request is made. Never add a Google Fonts
`<link>`.

## Tests

- Unit (`npm test`): `src/**/*.test.ts(x)` and `tests/unit`. Highlights: `Price.test.tsx` (Hebrew
  sentence, the number is an LTR island and the comma stays outside it), `tokens.test.ts` (doc
  parity and contrast), `ThemeProvider.test.tsx` (OS following, persistence, private mode, the
  pre-paint script), `BottomSheet.test.tsx` (focus trap, Escape), `handlers.test.ts` (mock API
  through the typed client).
- E2E (`npm run e2e`, after `npm run build`): every route renders its Hebrew h1 in an RTL document;
  no horizontal scroll at 390 px; content at most 1200 px wide at 1280 px; bottom-nav order and
  44 px targets; theme toggle, persistence, no flash, Profile sync, `theme-color`; manifest and
  icons; fonts with the network blocked; service worker offline; `/design-system` in both themes at
  390 and 1280 px with screenshots attached to the report.

## Adding a screen

1. Work in your group: `src/app/(core)/compare/page.tsx`, for example. Keep it a server component
   and put interactive parts in `src/features/<area>/` as client components.
2. Compose `@/components/ui` and tokens. No hard-coded colors, no physical left/right, prices via
   `Price`, 44 px targets. Need a new shared component? Add it to `src/components/ui` (W4a/W4b),
   show it on `/design-system`, and test it.
3. Fetch with the helpers in `@/api/client`; develop with `npm run dev:mock`. Add fixtures to
   `src/mocks/fixtures.ts` when a screen needs a case the mock does not cover.
4. Trust signals are mandatory (D10): update time on prices, "המחיר הקובע הוא בקופה", labeled
   substitutes, report-a-gap. Net saving is always versus the user's store (D7).
5. Keep the page h1 in sync with `tests/e2e/routes.ts`, add e2e coverage for the flow, and check the
   screen on `/` at 390 px and 1280 px in both themes.

## CI

`.github/workflows/web.yml` runs on pull requests and pushes that touch `apps/web/**`,
`docs/ux-design.md` (the token test reads it) or the workflow: `npm ci`, lint, typecheck, a
check that `src/api/types.ts` matches `openapi.json`, unit tests, build, Playwright e2e (Chromium
installed by `npx playwright install --with-deps chromium`, cached), Lighthouse CI. Time limit 10
minutes. The Playwright HTML report and Lighthouse reports are uploaded as an artifact.

## Core screens (W4b)

Issues #24 (list builder), #31 (flexibility sheet), #36 (comparison results), #48 (substitution
card) and the UI half of #12 (trust signals). Artboards: `Main`, `Flexibility`, `Results`,
`Substitution`, `DesktopList`, `DesktopResults`.

| Route | Page (server, owns the h1) | Client screen |
|---|---|---|
| `/` | `src/app/(core)/page.tsx`, "הקנייה השבועית" | `features/list/ListBuilder.tsx` (+ `ListRow`, `EstimatePanel`, `FlexibilitySheet`) |
| `/compare` | `src/app/(core)/compare/page.tsx`, "איפה הכי זול השבוע?" | `features/compare/ResultsView.tsx` (+ `PlanCard`, `SubstitutionsSection`, `BasketDetails`, `ReportGapSheet`) |
| `/compare/substitution/[id]?plan=single\|split` | `.../substitution/[id]/page.tsx`, "פרטי החלפה" | `features/substitution/SubstitutionView.tsx`; `[id]` is the substitute's `item_id` |

### State (`src/state`)

| Module | What | Storage |
|---|---|---|
| `list.ts` | The list: rows (canonical, candidates, quantity, unit, weighed, flex level, allowed soft attributes, `exactItemId`, confirmation and not-found flags) and `flexDefaults` (taxonomy id to level). Pure `listReducer`, `useList()`, `listActions`, `basketItems()` (API items, duplicates merged), `useFlexDefaults()` | `localStorage["sc-list-v1"]`, versioned and sanitized on read, every access in try/catch; works in memory in private mode; syncs across tabs |
| `flex.ts` | Level resolution for a new row: the user's remembered default for the node or an ancestor, then the smart default (`toiletries`, `health`, `baby` = exact, D4), then the level `/parse-list` returned (any brand for staples). Per-category copy and soft attributes for the sheet | none |
| `shopper.ts` | Location, radius, home store, clubs, travel. `useShopper()`, `saveShopperProfile(patch)` | `localStorage["sc-profile-v1"]` with the API `Profile` field names plus `city_label` |
| `comparison.ts` | Builds `/optimize` and `/compare` requests; a shared cache (`useOptimize`, `useCompareEstimate`) so results and the substitution card read the same response; `estimateRange`, `findSubstitution`, `substitutionSaving`, plan helpers | memory |
| `flash.ts` | One-shot status message across a navigation ("we kept the original") | memory |

Defaults when `sc-profile-v1` is missing: Modi'in (31.898, 35.010, neighborhood precision), 5 km,
car, ₪1.2/km, ₪25 per extra stop, up to 2 stores. The home store defaults to the mock's
(103, שופרסל דיל) only when `NEXT_PUBLIC_API_MOCK=1` and the field is absent; an explicit
`home_store_id: null`, or any real build without one, shows "מה הסופר שלך?" and no saving at all
(D7: never an invented baseline).

### Behaviour worth knowing

- **Parse.** Enter (or "הוסיפי") sends the text with the user's `flex_defaults` to `/parse-list`.
  The clipboard button reads the clipboard and parses it; without permission it says how to paste.
  The mic is `aria-disabled` with a "בקרוב" tooltip. The same confident product twice adds up.
  Rows group by `canonical.category_path_he[0]` (the mock fixtures carry the path now), in order
  of first appearance; `not_found` rows sit in their own "לא זוהו" group with edit and remove.
- **Confirmation.** `needs_confirmation` rows show the amber block with "כן" and "בחרי אחר"
  (the candidates); either resolves the flag. Unconfirmed rows still count for Compare.
- **Estimate.** `/compare` with the list's products and levels; the range is over stores that
  carry every product (a gap never makes a store look cheap), and quantities are applied locally
  (line total / line quantity x the row's quantity), so the steppers update it without a refetch
  and a level change refetches. Phone: fixed bar above the bottom nav. 1024 px and up: sticky side
  card with the home store total, the cheapest store and the flexibility counts (DesktopList).
- **Flexibility sheet.** Three radios (icon, label, one-line explanation, example), soft-attribute
  checkboxes for any brand and close, "זכרי בחירה זו לכל סוגי ה…" which writes
  `flexDefaults[taxonomy_id]` and applies it to that category's rows. Save/cancel; Escape and the
  scrim cancel. The soft attributes are stored with the row only: the API has no field for them.
- **Results.** Recommended plan first (the split only when the API marks it), then the other
  plan, then minimum effort (the home store). Saving block = `breakdown.net_saving`, always named
  "לעומת <home store>, הסופר שלך"; the split explains basket saving minus travel and the extra
  stop. Missing items are a red button (icon + text) that lists the names. "X פריטים הוחלפו" opens
  the first substitute's card. Below: every substitute of the recommended plan with "למה?" and
  "בטלי", line-by-line prices (collapsed), the disclaimer from the API (`disclaimer_he`) and
  report-a-gap (sheet: store, item, actual price, note, `POST /feedback/gap`). List/map toggle:
  "מפה" navigates to `/map` (W5).
- **Substitution card.** Original versus substitute with shelf and unit price and update time,
  saving x quantity, tags from `tags` (matched green check, unverified amber, differs neutral),
  source line with the match confidence and the price time. "בסדר" sends `accepted` and moves to
  the next substitute (or back); "השאירי את המקורי" sends `kept_original` and sets the row to
  exact with `exact_item_id = original_item_id`; "לא תחליף טוב" sends `not_good` and does the same.
  Both return to `/compare`, which recomputes because the request changed.
- **The original's price** is the home store's non-substitute line for the same canonical: the
  API gives only `original_item_id`, not its price at the substitute's store. Without a home
  store the card says there is no price to compare.

### Trust signals (#12)

- `UpdatedAt` (`<time datetime>`; "היום 06:40", "אתמול 18:20", "לפני 3 ימים", then the date, in
  Israel time) on every card, line, substitute and estimate; `TrustedPrice` = `Price` + its time,
  with `updatedAt` required by the type. A missing time renders "מועד העדכון לא ידוע", never
  nothing.
- `ResultsView.test.tsx` walks every rendered ₪ amount and fails if it is not inside a
  `[data-trust-scope]` that also contains a `time[datetime]`. It also fails if the results ever say
  "most expensive" (Hebrew or English).
- New `Tag` variants: `substitute` ("תחליף", refresh icon) and `club` ("מבצע מועדון", tag icon).
  Weighed rows and lines carry `estimated` ("מחיר משוער · שקיל").
- Not done: a confidence indicator on promos. The API returns `promo_description` but no promo
  confidence; the UI shows the promo text and the source note in the footnote.

### Tests

- Unit: `state/list.test.ts` (acceptance parse, merge, confirmation, remember, keep original,
  sanitize, persistence and private mode), `state/flex.test.ts`, `state/comparison.test.ts`
  (estimate, substitutions, saving x quantity, shopper defaults), `UpdatedAt.test.tsx`,
  `FlexibilitySheet.test.tsx`, `ResultsView.test.tsx`, `SubstitutionView.test.tsx`.
- E2E: `core-list.spec.ts`, `core-compare.spec.ts`, `core-substitution.spec.ts` at 390 and
  1280 px, the results also in dark. `core-helpers.ts` `mockApi(page)` answers the browser's API
  calls from the MSW handlers, so the specs pass on a build with or without
  `NEXT_PUBLIC_API_MOCK=1` (CI builds without it) and can assert request bodies; `seedProfile`
  writes `sc-profile-v1` the way onboarding will.

### For W5 and W6

- Profile "flexibility defaults": read `useFlexDefaults()` and edit with
  `listActions.setFlexDefault(taxonomyId, level | null)` (`@/state/list`).
- Onboarding and Profile: write location, radius, home store, clubs and travel with
  `saveShopperProfile({...})` (`@/state/shopper`); the comparison screens pick it up live.
- `/map` and `/split` can reuse `useOptimize(buildOptimizeInput(basketItems(state), shopper))`
  for the same cached response the results screen uses.
- `UpdatedAt`, `TrustedPrice`, `CheckChip` and the new `Tag` variants are in `@/components/ui`;
  they are not on `/design-system` yet because that page belongs to the shell group.
