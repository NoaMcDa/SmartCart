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
- Signed in, `ProfileSync` (W5) saves the choice to `PUT /me/profile` and restores it on sign-in.

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

## Secondary screens (W5)

Issues #18 (onboarding), #50 (product detail), #55 (profile), #41 (split), #59 (map), #66 (in-store
mode), the UI half of #30 (privacy) and of #16 (report-a-gap), plus Supabase email sign-in.

| Route | Client screen | Notes |
|---|---|---|
| `/onboarding` | `features/onboarding/OnboardingFlow.tsx` | Three skippable steps, each with a visible "למה אנחנו שואלים"; reuses the controls of Profile |
| `/profile` | `features/profile/ProfileScreen.tsx` | Account, my savings, location and radius, chains and clubs, travel, diet and kosher, flexibility defaults, theme ("ערכת צבעים" with `ThemePreferenceControl`), privacy and deletion |
| `/product/[id]?name=` | `features/product/ProductDetail.tsx` | `[id]` is the canonical id; `name` is the Hebrew canonical name (the price lines only carry chain item names) |
| `/split` | `features/split/SplitView.tsx` | Two stores, drag or move buttons, client-side saving and waterfall |
| `/map` | `features/map/MapScreen.tsx` | MapLibre GL, OSM raster tiles, loaded with `next/dynamic` (`ssr: false`) |
| `/store-mode?store=<id>[&plan=split]` | `features/store/StoreMode.tsx` | Checklist by department, offline |
| `/privacy` | `app/(secondary)/privacy/page.tsx` | Hebrew privacy policy, linked from onboarding and Profile |

`features/feedback` exports `GapReportSheet` and `ReportGapButton` for any screen that shows a price.
`features/auth` holds the Supabase client, `AuthProvider`/`useAuth`, the email OTP sheet and the API
token wrapper. The `(secondary)` layout mounts `AuthProvider` and `ProfileSync`.

### State and storage

| Key | Owner | What |
|---|---|---|
| `sc-profile` | W5 `features/profile/profileState.ts` | Everything onboarding and Profile collect: consent, location (rounded to 3 decimals before it is stored), radius, home chain and store, clubs, travel, extra stop value, diet, kosher, allergens. Read with `useProfile()` |
| `sc-profile-v1` | W4b `state/shopper.ts` | What the comparison reads. Every change to `sc-profile` is mirrored here (`mirrorToShopper`), so a change in Profile affects the next comparison. An unset home chain is an explicit `home_store_id: null` (no baseline, no saving, D7) |
| `sc-list-v1` | W4b `state/list.ts` | The list and the flexibility defaults. Profile edits the defaults through `useFlexDefaults()` and `listActions.setFlexDefault` (smart defaults from `state/flex.ts`) |
| `sc-shopping` | W5 `features/store/session.ts` | The in-store session: items, labels, prices, update times, check marks. Written when shopping starts, deleted by "סיימתי", expires after 12 hours |
| `sc-savings-history` | W5 `features/profile/savingsHistory.ts` | "החיסכון שלי": one entry per finished trip, only the lines the user checked, against their own store, after travel and the extra stop |

There is no stored comparison. `useComparison()` (`features/split/lastResult.ts`) assembles one from
the list, the shopper context, the `/optimize` response through W4b's cache (`useOptimize`, no
second request) and a `/compare` response with the real quantities. After a reload it is fetched
again; only the in-store checklist keeps a copy, so it works offline.

Home store: onboarding asks for a chain, the API takes a store. With the mock on a chain maps to its
fixture store; against the real API `adoptHomeStore(stores)` (called by `useComparison` on every
compare result) takes the nearest store of that chain. Request to `services/api`: a "nearest store of
chain X" lookup, so the first comparison can carry a home store.

### Split view arithmetic

Mirrors `docs/api.md` (D7), all in integer agorot (`features/split/savings.ts`):
`basket_saving` = home total minus plan total over the lines both supply; travel = plan travel minus
the home store's, split across stores by distance; extra stop = value per stop times visited stores
minus one; `net = basket_saving - travel - extra_stop`. Each line's saving is split into shelf
difference (chain switch, or brand swap when the plan line is a substitute) and promo difference, so
the waterfall steps sum exactly to the net. Moving an item re-prices it from the other store's
cached line total; an item the store does not stock (`missing`) cannot move and says why.

### Map

OpenStreetMap raster tiles through MapLibre GL, no API key; attribution is the MapLibre control plus a
text link under the map. Tiles come from `tile.openstreetmap.org`, which sees the viewer's IP and
the area shown (stated in the privacy policy). OSM's tile usage policy is for light use; before real
traffic move to a hosted tile provider or a self-hosted server (out of scope in #59). Dark theme
inverts the tile canvas with a CSS filter. Without WebGL the screen shows a schematic plan with the
same pins; the store list under the map is the accessible alternative in both cases.

`StoreResult` has no coordinates. Pins are placed at the store's real distance from the user on a
deterministic bearing and the screen says the direction is approximate. Request to `services/api`:
add `lat` and `lon` to `StoreResult`; `storePosition` uses them as soon as they exist.

### Privacy and deletion (#30)

- Location is rounded by `setLocation` before it is written and again by `sanitizeProfile` on every
  read and write; a test scans the stored JSON for anything finer than 3 decimals. It is stored only
  with explicit consent, and the device is asked only after the user clicks, below the explanation.
- `tests/unit/privacy-audit.test.ts` fails on any analytics, advertising or tracking package, tracking
  call, external script, or a host outside the allow-list (localhost, tile.openstreetmap.org,
  www.openstreetmap.org).
- "מחקי את הנתונים שלי": signed in, `DELETE /me/lists/{id}` for every list and `PUT /me/profile` with
  the defaults, no location and consent off; then the device keys above plus `sc-list-v1` and
  `sc-profile-v1` are removed and the user is signed out. If the server fails the device keeps its
  data so the user can retry. The theme choice is a display setting and stays.
  Blocked, request to `services/api`: `DELETE /me`, which must remove the `profiles` row and the
  Supabase auth user. Until then the account row (and email) remain, and the UI says full account
  deletion is coming.
- The privacy text has not had a legal review (tracked separately in #30).

### Auth

`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (build time). Without them the app is
signed out and the sheet says so; mock mode needs nothing. Email one-time code, session kept by
supabase-js. `features/auth/apiAuth.ts` registers an `openapi-fetch` middleware on the shared `api`
client (no change to `client.ts`) that adds `Authorization: Bearer <access token>`. It is installed
by `AuthProvider` and by `GapReportSheet`; request to W4a: mount `AuthProvider` in the root layout so
`/feedback/*` records the user id on every screen. `ProfileSync` mirrors the profile, theme and
flexibility defaults to `PUT /me/profile` while signed in. Diet flags travel as `vegan`,
`gluten_free` and `allergen:<key>`; city and neighborhood text stay on the device.

### Gap report

`GapReportSheet` takes `context` (store, canonical and item ids, item name, shown price, price time).
One tap plus "שליחה" is enough; reason, shelf price and note are optional. The API has no reason or
price-time field, so they travel as `#reason=...` and `#shown_at=...` at the end of `note` (cut to
500 characters). Used by product detail, split, map sheet and store mode; W4b's `ReportGapSheet` is
its own component, switching to this one is optional.

### Product detail

Variants (distinct chain items) ranked by unit price, a per-store table with distance, shelf and final
price, promo and club tags and an update time on every price, "הוספה לרשימה" with a flexibility chip
(through `listActions.add`), and a disabled "בקרוב · שלב 2" alert placeholder. No history chart. The
promo "confidence" is shown as "לא נבדק": the API has no promo confidence field yet.

### Links other screens should use

- Results: "מפה" to `/map`; the split card to `/split`; "התחילי קנייה" to `/store-mode?store=<id>`
  (`&plan=split` for a split part); a product name to `/product/<canonical_id>?name=<name>`;
  store anchors on `/compare` should be `id="store-<store_id>"` (the map sheet links there).

### Tests

Unit: `profileState`, `savings` (waterfall sums, moves, blocked items), `session`, `deleteData`
(MSW, lists and profile erased), `gapReport`, `geo`, `auth`, component tests for onboarding,
profile, split, map, store mode and product detail, and the privacy audit. E2E (`secondary-*.spec.ts`):
onboarding with a granted and a denied location, profile persistence and deletion, split by keyboard
and by pointer (columns on desktop, tabs on a phone), map pins and sheet in light and dark, the map
chunk loaded only on `/map`, store mode including a reload with the network cut at the proxy, and
the gap report. Not tested here: the Wake Lock API and real Supabase.

## Phase 2 screens (P2-E)

Issues #39 (barcode scanning), #28 (price history), #23 (alerts and web push), #34 (shared lists) and
#45 (smart cart): the UI halves. Built against `src/mocks/handlers.phase2.ts`; the API halves are
workstream P2-A. `/scan` and `/alerts` moved out of `(shell)` into the new `(phase2)` group (P2-D:
the shell layout comment that lists them as placeholders is now stale; nothing else of the shell was
touched).

| Route | Page | Client screen |
|---|---|---|
| `/scan` | `app/(phase2)/scan/page.tsx`, "סריקת ברקוד" | `features/scan/ScanScreen.tsx` (+ `ResultCard`, `barcode`, `camera`, `detector`, `stores`, `scanLog`) |
| `/alerts` | `app/(phase2)/alerts/page.tsx`, "התראות" | `features/alerts/AlertsScreen.tsx` (+ `PushPanel`, `push`, `alertNames`) |
| `/lists/[id]/share` | `app/(phase2)/lists/[id]/share/page.tsx`, "שיתוף הרשימה" | `features/share/SharedListScreen.tsx` (+ `ShareSheet`, `useSharedList`, `listSync`) |
| `/lists/accept/[token]` | `app/(phase2)/lists/accept/[token]/page.tsx`, "הצטרפות לרשימה משותפת" | `features/share/AcceptInvite.tsx` |
| product detail | (existing `/product/[id]`) | `features/history/PriceHistory.tsx` and `features/alerts/AlertMe.tsx`, mounted by `ProductDetail` |
| results | (existing `/compare`) | `features/compare/SmartCartCard.tsx`, mounted by `ResultsContent` (one import and one JSX line) |

The `(phase2)` layout is just `AppShell`; `AuthProvider` comes from the root layout. Typed helpers for the new
routes are in `src/api/client.ts` (`priceHistory`, `listAlerts`, `createAlert`, `deleteAlert`,
`addPushSubscription`, `createList`, `getList`, `updateList`, `shareList`, `listMembers`,
`acceptShare`, `lookupBarcode`, `swapSuggestions`, `nearestStore`).

### Barcode scanning (#39)

- The camera is never asked for on load. The card explains ("לא נשמרות תמונות והן לא עוזבות את
  המכשיר") and the permission prompt follows the tap on "הפעלת המצלמה". Denied, no camera, busy and
  unsupported each have their own Hebrew message, and the manual field is always on the page.
- `detector.ts`: native `BarcodeDetector` when it lists `ean_13` (Android Chrome), otherwise
  `@zxing/browser`, loaded with a dynamic `import()` so only `/scan` pays for it (iOS Safari has no
  native detector, so installed iOS PWAs take this path). Both report only codes that pass the EAN-13
  or EAN-8 check digit, so a misread never becomes a product (D5). Manual entry runs the same check
  before any request ("הספרות לא מרכיבות ברקוד תקין").
- Store picker: `/stores/nearest` for the chains in `SCAN_CHAIN_IDS` (GS1 ids; the first three are
  the mock's), pre-selecting the remembered store, then the shopper's home store, then the nearest. A
  home store that is not among them is offered as "הסופר שלי".
- Result card: "כאן" (the price at the picked store, or the shelf price the shopper typed), "הכי זול
  באזור" and "תחליף זול" with `Tag variant="substitute"` and the reason, each price with its update
  time, unit prices (D6) and the checkout disclaimer. A typed shelf price that differs from ours shows
  a warning and `ReportGapButton`. Add to list uses `listActions.add` with a `Stepper` quantity; the
  flexibility level is whatever the list resolves for the category (D4). Not found: "לא ננחש מוצר",
  report-a-gap, manual entry.
- Scan success rate and time to result are kept on the device (`sc-scan-log-v1`: counters and a sum of
  milliseconds, no image, barcode or location). The API's `EventIn.name` has no scan event, so nothing
  is sent until it does (`trackEvent` cannot carry it).

### Price history (#28)

`PriceHistoryChart` is an SVG with no chart library. Unit price is the default axis (D6), shelf price
is a toggle; 30 or 90 days; the store is "my store", "cheapest nearby" or the chain base price.

- Time runs in reading direction (oldest on the right in Hebrew) and the price axis is on the right;
  every number is an LTR island. Colors are tokens (line `--sc-accent-fg`, promo `--sc-warn-*`).
- Promo windows are shaded bands; promo days carry a marker with a Hebrew tooltip (`<title>` on hover,
  and a status line below the chart that follows the pointer). A legend names each mark in words.
  Each promo window is listed under the chart with its dates, `Tag variant="club"` ("מבצע מועדון · <name>")
  when `club_only`, and the confidence ("ביטחון במבצע: 87%", or "לא נבדק" when the API has none, D10);
  the tooltip repeats audience and confidence.
- Days without data are gaps, never interpolated: the line is cut where two points are more than 3
  days apart (`MAX_JOIN_DAYS`; the mock samples every 3 days) and the hole is hatched. Leading and
  trailing holes count too. The chart says so in a sentence under it.
- The drawing is `aria-hidden`. A summary sentence (min, max, latest, promo periods, gap days) and a
  visually hidden `<table>` with every point carry the same data for screen readers.
- Shows the time of the last price and "המחיר הקובע הוא בקופה.".

### Alerts and web push (#23)

- `AlertMe` on product detail: "התריעי לי מתחת ל-₪__" is a target unit price at one of the three
  levels, within the shopper's radius. Existing alerts for the product are listed with delete.
  `/alerts` lists all of them with the product, price, level, radius and last fired time, and lets the
  shopper pause or resume (`PUT /me/alerts/{id}` with `active`), edit price and level in a sheet
  (`EditAlertSheet`, the API re-arms an edited alert) and delete.
- The API returns only the canonical id, so the device remembers the product name when the alert is
  created (`sc-alert-names-v1`); an unknown one reads "מוצר מס' <id>".
- Signed out with Supabase configured, both screens ask for sign-in instead of failing; without
  Supabase (mock, local) they call the API directly. 402/403/429 read as the free-tier limit.
- `push.ts`: feature-detected (service worker, Push API, Notification, the key). Needs
  `NEXT_PUBLIC_VAPID_PUBLIC_KEY` at build time. States: unsupported, iOS before "add to home screen",
  no key, denied (with how to allow it), on (with an off switch), off. Permission is requested only
  after a tap, then the subscription goes to `POST /me/push-subscriptions`; turning it off also calls
  `DELETE /me/push-subscriptions?endpoint=`. None of these states
  breaks alerts; they stay listed on `/alerts`.
- `public/sw.js`: `push` shows a notification from `{title, body, url, tag, product, store, price,
  updated_at}` (composed body: product, store, price, the price's time in Israel time, "המחיר הקובע
  הוא בקופה."; Hebrew, RTL, `tag` collapses repeats) and `notificationclick` focuses an open window
  or opens the product. Only same-origin paths are ever opened. `sw.test.ts` runs the handlers in a vm.

### Shared lists (#34)

- Entry: `/lists/mine/share` creates the shared copy of the device's list once (`POST /me/lists`,
  names and quantities and levels only, no location or preferences), remembers its id and redirects
  to `/lists/<id>/share`. `ShareSheet` (role "עריכה" or "צפייה בלבד", invite link, copy with a
  select-and-copy fallback, `navigator.share` when present) opens from "הזמנת בני משפחה".
- `/lists/accept/<token>`: joining is a tap, never automatic; an expired or revoked link says so.
- The owner can cancel the link just created ("ביטול הקישור", `DELETE /me/lists/{id}/share/{token}`) and
  remove a joined member ("הסרה מהרשימה", `DELETE /me/lists/{id}/members/{user_id}`; shown only on the
  list this device shared). `/lists/mine/share` also lists the lists others shared with me
  (`GET /me/shared-lists`). A pending invite cannot be revoked later because the API does not return
  its token and the app never stores tokens.
- `useSharedList`: signed in with Supabase, items come from `GET /me/lists/{id}` once and then from a
  Realtime subscription on `list_items` filtered to `list_id=eq.<id>`; edits go to `list_items`
  directly (RLS decides) and are applied optimistically, rolled back with a message on failure; the
  list is read again whenever the channel (re)subscribes, which merges what happened offline. Not
  signed in (mock, local), the list is read every 4 seconds and edits are sent as `PUT /me/lists/{id}`.
- Conflict rule (`listSync.ts`): per item, never per list. A change replaces what we know of the item
  unless its `updated_at` is older than the one we hold (without a timestamp, the last change received
  wins). Different items never interact; a delete removes only that item; an insert whose id is known
  is an update, so a replay cannot duplicate.
- Members: owner, pending invites ("הזמנה ממתינה") and joined members, with a line that members see
  only the list. Member names and emails are never shown.

### Smart cart (#45)

`SmartCartCard` takes the recommended plan, asks `POST /optimize/swaps?store_id=<its store>` with the
list, and shows "N החלפות יחסכו לך ₪X" (the sum of the visible swaps in whole agorot; the API's swaps
do not overlap), then the top one: name, saving, confidence, a "למה" line by level and `Tag`s for the
attributes. Nothing is applied by itself.

- "החלפה" sets the list rows of that product to the swap's level (the substitution flow's inverse of
  "keep the original") and sends `accepted` to `/feedback/substitution`; "ביטול ההחלפה" restores the
  previous level, soft attributes and exact item.
- "לא עכשיו" sends `not_good` and hides the swap until its saving changes by at least ₪1 and 25%.
- Renders nothing while loading, on an error or with nothing to suggest.

### Storage and configuration

| Key | Owner | What |
|---|---|---|
| `sc-scan-store-v1` | `features/scan/stores.ts` | Store id picked on `/scan` |
| `sc-scan-log-v1` | `features/scan/scanLog.ts` | Counters: attempts, found, not found, failed, summed ms, by input. No images, codes or location |
| `sc-alert-names-v1` | `features/alerts/alertNames.ts` | Canonical id to product name and unit label, for `/alerts` |
| `sc-shared-lists-v1` | `features/share/sharedLists.ts` | Server id of the list shared from this device, lists joined by invite (id, name) |
| `sc-swaps-v1` | `features/swaps/swapState.ts` | Dismissed swaps (key to saving at dismissal), applied swaps with the rows' previous state |

Existing keys used: `sc-list-v1` (add to list, apply and undo), `sc-profile-v1` (location, radius, home
store). New build variable: `NEXT_PUBLIC_VAPID_PUBLIC_KEY` (web push; optional).

Dependencies added: `@zxing/browser` 0.2.1 and its peer `@zxing/library` 0.23.0, both pinned, loaded
only by `/scan`.

### Tests

Unit: `barcode`, `detector` (native stub and the zxing fallback), `ScanScreen` (manual, camera denied,
stubbed camera and detector, not found, gap, logging), `series` and `PriceHistory` (gaps, promo
bands, tooltips, table, controls), `push`, `AlertsScreen`, `sw` (push and click handlers),
`listSync`, `share` (sheet, accept, polling, a fake Supabase Realtime channel, optimistic rollback,
share my list), `swaps` and `SmartCartCard`, `client.phase2`. E2E (`phase2-*.spec.ts`): scan with a
stubbed `getUserMedia` and `BarcodeDetector` at 390 and 1280 px; history in both themes; alerts
create, list, delete; share, copy, accept on a second context and see edits in both directions;
smart cart dismiss, apply and undo at 390 and 1280 px.

### Manual checks (not automatable here)

1. Real camera: scan a known EAN-13 on Android Chrome (native detector) and on an installed iOS PWA
   16.4 or later (zxing); note the devices in the PR.
2. Real push: set `NEXT_PUBLIC_VAPID_PUBLIC_KEY`, build, install the PWA, create an alert and send a
   push from the API; the notification shows product, store, price and time, and a tap opens the
   product. On iOS the app must be added to the home screen first.
3. Two real signed-in accounts on a Supabase project with the phase 2 migration: edits appear on both
   within a couple of seconds, and a non-member gets nothing.

### Requests to other workstreams

- API: `updated_at` on `list_items` and `ShoppingList.items`; a "checked" flag per item; scan events
  in `EventIn.name`; the paid-tier limits as a documented error code; the invite token (or an id) on
  pending `ListMember` rows so an owner can revoke them from the members list. The shared mock has no
  handlers for `PUT /me/alerts/{id}`, the two share DELETEs, `DELETE /me/push-subscriptions` and
  `GET /me/shared-lists` (the e2e stubs the alert PUT itself).
- P2-D (list builder): a "שיתוף" link to `/lists/mine/share` next to the list's name.
- Mock numbers: `/optimize/swaps` returns 5.00, 4.80 and 1.20, so `total_saving` is 11.00, not 10.90;
  `cheapest_nearby` is אושר עד and the substitute is at רמי לוי.

## Phase 2 web follow-ups (P2-D, issue #91)

Loose ends reported by W4b, W5 and W6, plus the UI halves of #12 (promo confidence), #30 and #55
(account deletion) and #59 (real map pins). Where this section differs from an earlier one, this
section is current: the "request to W4a", "request to `services/api`" and "not done" notes above
are closed by the table below.

| Earlier note | Now |
|---|---|
| "Mount `AuthProvider` in the root layout" (Auth) | Done: `app/layout.tsx` wraps the app in `AuthProvider`; the `(secondary)` layout keeps only `ProfileSync`. `tests/unit/layout-auth.test.ts` fails if a second provider appears. |
| "`/design-system` does not show `UpdatedAt`, `TrustedPrice`, `CheckChip`, the new tags" | Done: section "אמון ועדכניות", both themes. |
| "`StoreResult` has no coordinates" (Map) | `lat` and `lon` are optional on `StoreResult`; `storePosition` uses them when both are finite, otherwise the bearing approximation and the existing note. |
| "Blocked: `DELETE /me`" (Privacy and deletion) | `deleteMe()` in `src/api/client.ts`; see Account deletion below. |
| "Not done: a confidence indicator on promos" (Trust signals) and "לא נבדק" (Product detail) | `PromoConfidence`, see below. |
| Request for "nearest store of chain X" (Home store) | `nearestStore(chainId, lat, lon)` helper added to `client.ts`; **not wired** to `adoptHomeStore` yet (that stays W5's profile logic). |

### Auth in the root layout

`AuthProvider` registers the bearer-token middleware (`ensureApiAuth`) and, new here,
`setAuthTokenProvider(getApiToken)` so `POST /events` carries the user's token like `/feedback/*`.
Mock mode and builds without Supabase variables stay signed out.

`supabase-js` is now loaded with a dynamic `import()` (`loadSupabase()` in `supabaseClient.ts`) and
only when `NEXT_PUBLIC_SUPABASE_URL` and `_ANON_KEY` are set. Without that, the provider in the root
layout would have put a roughly 250 KB (before gzip) chunk on every SEO page; with it, SEO pages,
mock builds and local builds download nothing extra. `getSupabase()` is now the synchronous "already
loaded or null" accessor.

### Beta instrumentation and consent (issue #40, `docs/beta-plan.md` sections 3 and 5)

- **Opt-in, a behavior change.** `isTrackingEnabled()` is true only when the build has
  `NEXT_PUBLIC_BETA_EVENTS=1`, the API is not the mock, the browser does not send Do Not Track **and
  the person accepted the consent sheet**. Before this change an unanswered question meant "on";
  now unset means nothing is queued or sent, so no event can precede the person seeing what is
  collected. This also applies to the SEO `page_viewed` event: a visitor who never opened the app
  is not counted.
- **Storage key:** `localStorage["sc-events-consent"]`, `"1"` accepted, `"0"` declined, absent not
  asked. Reading and writing are in try/catch; with blocked storage the answer lives in memory for
  the page and the sheet asks again next visit. The session id key `sc-session` is unchanged.
- **Where the sheet is.** `features/consent/ConsentSheet.tsx` (`ConsentGate`) is mounted by
  `AppShell`, so it appears on the app screens (not on the SEO pages) and only in a build that
  collects events and for a browser without Do Not Track. Accept or decline closes it for good;
  Escape counts as decline. The wording follows the proposed text in `beta-plan.md` section 3 and
  **has not had a legal review**; the six-month retention in it is a proposal. In a default build
  (no flag, as in CI) there is no sheet and no switch.
- **Opt-out in Profile.** `UsageEventsControl` ("אירועי שימוש לבדיקת הבטא", a `Switch`) in the privacy
  section: off calls `setTrackingConsent(false)`, which drops the queue at once. With Do Not Track it
  shows a note instead.
- **Call sites** (`features/consent/betaEvents.ts` forwards to `trackEvent`; the API allowlist is
  the contract, so props are integers or fixed strings and never text):

| Event | Fired from | Props |
|---|---|---|
| `app_opened` | `ConsentGate`, once per page load after consent | `surface` web or pwa |
| `list_pasted` | `ListBuilder`, after a successful parse of text that came from a paste into the box or the clipboard button (typing does not count) | `item_count` = parsed rows, at most 200 |
| `results_shown` | `ResultsView`, once per response, only if a paste happened in this page session | `duration_ms` from the paste (dropped over 10 minutes), `item_count`, `store_count` = stores in the three plans |
| `substitutions_shown` | `ResultsView`, per flexibility level that lists substitutes in the recommended plan | `flex_level`, `count` |
| `substitution_verdict` | `features/substitution/actions.ts` (`acceptSubstitute`, `keepOriginal`, `rejectSubstitute`), before the row changes | `flex_level`, `verdict` |
| `flex_changed` | `FlexibilitySheet` save, only when the level changed | `flex_level` |
| `split_viewed` | `SplitBoard` on mount (a split is on screen) | none |
| `gap_reported` | both gap sheets (`compare/ReportGapSheet`, `feedback/GapReportSheet`), after the API accepted the report | none |

  The API does not return a flexibility level on a priced line, so the level of a substitute is the
  level of the list row with the same canonical id (`compare/substitutionLevels.ts`); a substitute
  with no matching row is not counted and its verdict is not sent, rather than guessing a level.
  `results_shown` measures from the paste, as the plan defines it, so it includes the time the
  person spends reviewing the list before pressing compare: read it with that in mind. The three
  edits outside the listed directories (`features/split/SplitView.tsx`, `features/feedback/
  GapReportSheet.tsx`, `features/product/ProductDetail.tsx`) are one-line additions.

### Methodology links

`MethodologyLink` is in the results footer, in the same paragraph as the checkout disclaimer
("איך אנחנו משווים מחירים"), and on the substitution card under the source line ("איך אנחנו מחליטים
מה תחליף מתאים"). Both go to `/methodology`.

### Design system page

`/design-system` has a section "אמון ועדכניות" with `UpdatedAt` (today, yesterday, days ago, unknown;
a fixed "now" so the page reads the same on any day), `TrustedPrice` (stacked and inline),
`CheckChip` (checked, unchecked, disabled), the `substitute` and `club` tags, `PromoConfidence`
(96%, 72%, not checked) and a row of `Price` sizes and tones, in both themes. Tests:
`tests/e2e/followups.spec.ts`.

### Top bar at 195 px

200% zoom on a 390 px phone is 195 CSS px. The 32 px logo, the wordmark, a 16 px gap and the 44 px
theme switch did not fit in the 163 px left by the 16 px gutters, so the bar overflowed by 7 px.
Under 260 px the bar now uses an 8 px gap, a 28 px logo and a 15 px wordmark; the switch keeps its 44
px target. `tests/a11y/top-bar-zoom.spec.ts` checks 195, 240 and 320 px, both themes, four routes
(no control outside the viewport, no scrolling inside the bar); it failed at 195 px before the fix
(-6.98 px). Not part of #91, found while testing: at 195 px the list builder (`/`) is 13 px wider
than the viewport and Profile 69 px wider. Follow-up.

### Promo confidence (UI half of #12)

`PromoConfidence` (in `@/components/ui`) renders a `Tag`: `ביטחון 96%` from `PricedItem.promo_confidence`
(green at 90% and above, amber below), or `לא נבדק` when it is null or missing. Never a made-up
number, never nothing. Used next to the promo on the line details (`BasketDetails`) and in the
product detail table. The mock fixtures carry no `promo_confidence`, so `dev:mock` shows `לא נבדק`
everywhere; the e2e test overrides one line to prove the score path. The API returns null until the chain adapters record a confidence, so "לא נבדק" is the normal state for now.

### Real map pins (UI half of #59)

`storePosition` uses `StoreResult.lat` and `.lon` when both are finite and in range. A null pair, one
null coordinate or an invalid one falls back to the distance-and-bearing approximation and the
existing note ("הכיוון … בקירוב") shows only while at least one pin is approximate. The mock stores
have no coordinates yet, so the mock still shows the note.

### Account deletion (UI halves of #30 and #55)

"מחקי את הנתונים שלי", signed in: lists and profile are erased on the server (unchanged), then the
device is cleared, then `DELETE /me` runs (while the token is still set), then the person is signed
out. The hosted-account notice (`account-remains`: the data is gone but the stored account and email
could not be deleted, sign in and try again) shows **only** when `DELETE /me` fails; on success the
status says the account, including the email address, was deleted. If the earlier list or profile
step fails nothing is cleared and `DELETE /me` is not called, as before. Signed out, no `/me` call is
made. The server side of the events table (rows with the user's id or session id) belongs to the
`DELETE /me` implementation; `sc-session` and `sc-events-consent` stay on the device because they are
not personal data and the consent answer is a choice.

### Tests (this section)

Unit: `features/consent` (`betaEvents.test.ts`: allowlisted props only, nothing sent when declined
or unset or without the flag, paste-to-results rules; `consent.test.tsx`: sheet shown once, accept,
decline, Escape, Do Not Track, Profile switch; `wiring.test.tsx`: each call site), `seo/track.test.ts`
(opt-in), `auth.test.tsx` (token provider), `deleteData.test.ts` and `deleteAccount.test.tsx`
(`DELETE /me` order and notice), `geo.test.ts` and `MapScreen.test.tsx` (real coordinates),
`PromoConfidence.test.tsx`, `ResultsView.test.tsx` and `SubstitutionView.test.tsx` (methodology links,
promo confidence), `api/client.test.ts` (`deleteMe`, `nearestStore`), `tests/unit/layout-auth.test.ts`.
E2E: `tests/e2e/followups.spec.ts`. A11y: `tests/a11y/top-bar-zoom.spec.ts`. Not testable in CI:
the consent sheet in a real beta build (needs `NEXT_PUBLIC_BETA_EVENTS=1` at build time) and a real
Supabase sign-in followed by `DELETE /me`.

## MVP completion (workstream M-C, issue #101)

What this round changed in `apps/web`, by deliverable. Nothing here reads real data; every number in
the tests is a mock value.

| # | Change | Where |
|---|---|---|
| 1 | **Share entry point.** A visible "שיתוף" link (44 px, share icon) in the list builder's header row opens `/lists/mine/share`, which opens this device's shared list when one exists and otherwise offers to create it. `list_shared` is sent when an invite is created, `share_accepted` when the accept page's join succeeds. The share sheet is mounted only while open, so a link from an earlier visit (possibly revoked from the members list) is never shown again | `features/list/ListBuilder.tsx`, `features/share/ShareSheet.tsx`, `AcceptInvite.tsx` |
| 2 | **Smart cart undo and dismiss.** Apply stores what undo needs (`origin`: canonical, from and to item, level, confidence) next to the row snapshots. Undo restores the rows, sends `/feedback/substitution` with `verdict: "kept_original"`, `source: "swap"` and the swap's `flex_level` and `match_confidence`, and reports `swap_undone`. Dismiss hides the suggestion until its saving moves by at least ₪1 and 25% (`isMaterialChange`), is stored in `sc-swaps-v1`, sends `not_good` and `swap_dismissed`. Apply sends `accepted` and `swap_applied` with `saving_agorot`. Applying clears an earlier dismissal; re-dismissing replaces the baseline saving; both lists are capped (200 dismissals, 20 applied). An undo is offered only while one of its rows is still on the list. The "ההחלפה בוטלה" note lives in memory (`useUndoneName`), because undoing reloads the results and rebuilds the card | `features/swaps/*`, `features/compare/SmartCartCard.tsx` |
| 3 | **195 px (200% zoom).** The list builder's input row wraps (textarea, then the buttons, the add button filling the last row) and its item rows put the name on a row of its own; `SegmentedControl` options wrap their text instead of overflowing (this was the Profile and product-page overflow); the results plan header, the substitution card (original and substitute stack) and its action buttons wrap; the `/design-system` card rows wrap. Logical properties only. `tests/a11y/zoom-195.spec.ts` asserts every route in `routes.ts` and the states behind a tap | CSS modules above, `tests/a11y/zoom-195.spec.ts` |
| 4 | **Home store from the chain.** Picking "הסופר שלי" calls `GET /stores/nearest` (`nearestStore`) with the chain's API id (`Chain.apiId`, the GS1 prefix) and the profile's neighborhood-level location (the default city without one), and stores the id as `homeStoreId` (`adoptNearestHomeStore`), which `mirrorToShopper` sends as `home_store_id`. The results page also runs `useResolveHomeStore`: a chain with no store is looked up once per chain, and the stores of the result on screen fill it in as a fallback (`adoptHomeStore`), so the first results page already shows the net saving "לעומת <your store>". The mock `/stores/nearest` has one store per chain with a compare fixture (101 to 105) and answers 404 for any other chain, like the API | `features/profile/profileState.ts`, `chains.ts`, `controls/ChainControls.tsx`, `mocks/handlers.phase2.ts` |
| 5 | **Revoke a pending invite, remove a member.** Pending invites (a `share_id` and no user) show "ביטול ההזמנה" and call `DELETE /me/lists/{list_id}/shares/{share_id}` (`revokeShareById`); joined members show "הסרה מהרשימה" (through the same route when the member has a `share_id`, else `DELETE .../members/{user_id}`). Both are optimistic: the row leaves at once, comes back in the same place with a message when the call fails, and the member poll is paused while a call is in flight. The MSW handlers return `share_id`, delete by it, and turn an accepted invite into a member | `features/share/useSharedList.ts`, `SharedListScreen.tsx`, `api/client.ts` |
| 6 | **Checked items and offline edits on shared lists.** A checkbox per item (a native input in a 44 px label, the name struck through when checked), saved through the list item's `checked` field (the PUT body in polling mode, `update({checked})` on `list_items` in realtime mode) and shown to other members by the poll or the Realtime payload. An edit that fails for lack of a connection stays on screen and is queued in `sc-shared-queue-v1` (quantity, checked, remove, add; coalesced per item); "ממתין לסנכרון (N)" is shown until the queue is empty. The queue is sent when the browser fires `online`, when a poll tick or a Realtime reconnect succeeds, and on the next visit; polling mode reads the fresh list, lays the edits on it and PUTs it whole, realtime mode writes each edit. A refusal from the server (not a lost connection) still rolls the edit back | `features/share/offlineQueue.ts`, `useSharedList.ts` |
| 7 | **Scan and alert events.** `/scan` sends `scan_started` (engine: `native`, `zxing` or `manual`) and `scan_completed` (outcome `found`, `not_found`, `no_price`, `cancelled` or `error`, `duration_ms`, engine). A started event is always sent before a completed one; leaving the screen or stopping the camera mid-scan is `cancelled`. `alert_created` (`source: "product"`, the level) is sent when an alert is created on product detail. Payloads never carry a barcode, an item id or a price | `features/scan/ScanScreen.tsx`, `features/alerts/AlertMe.tsx`, `features/consent/betaEvents.ts` |
| 8 | **Coordinator follow-ups.** The results page links the split card to `/split` and every line of the basket details to `/product/<canonical_id>?name=`; the substitution card carries "המחיר הקובע הוא בקופה."; tags and units are written in Hebrew (`src/lib/attributes.ts`: `unit`, `pack_size`, `base` with soy, almond, oat, rice and coconut, `fat_pct`, `state`, `flavor`; `g`, `ml`, `unit`, `kg` become ג׳, מ״ל, יח׳, ק״ג; `100g` becomes "ל-100 ג׳"), and a `unit` tag that accompanies `pack_size` is folded into it ("1000 ג׳"). `BottomSheet` closes on Escape from anywhere: focus moves into the dialog one animation frame after it opens, and an Escape pressed before that went to the opener and was lost (the cause of the CI failure of "flexibility sheet › preselects, cancels, saves and remembers") | see the files named |

### New localStorage keys

| Key | Holds |
|---|---|
| `sc-swaps-v1` (existing, extended) | dismissed swaps with the saving at dismissal, applied swaps with row snapshots and `origin` |
| `sc-shared-queue-v1` | per shared list, the edits waiting for a connection (item id, quantity, checked, and the name of an item added offline). No location, profile or price |

### Events fired (all through `trackEvent`, so none without the beta flag, consent and a real API)

| Event | When | Properties |
|---|---|---|
| `scan_started` | camera decoder is up, or a manual search starts (also before an early `error` or `cancelled`) | `engine` when known |
| `scan_completed` | the attempt ended | `outcome`, `duration_ms`, `engine` |
| `alert_created` | an alert was created | `source: "product"`, `flex_level` |
| `swap_applied` | a swap was applied | `flex_level`, `saving_agorot` |
| `swap_undone` | an applied swap was undone | `flex_level` |
| `swap_dismissed` | a suggestion was dismissed | `flex_level` |
| `list_shared` | an invite link was created | `role` |
| `share_accepted` | a join from an invite link worked | none (the joiner is not told the role) |

### Contract notes for the merge

- `revokeShareById` types `DELETE /me/lists/{list_id}/shares/{share_id}` locally (`RevokeSharePaths` in
  `api/client.ts`) because the route is not in the generated `types.ts` of this branch. Once it is,
  the local type can go; behaviour does not change.
- Realtime mode writes `list_items.checked`; the column and its Realtime publication are `supabase/`'s.
- `/stores/nearest` is called with the GS1 chain ids in `chains.ts`; the real API answers 404 for a
  chain with no physical store, and the profile then keeps the chain without a store.

### Tests (this section)

Unit: `swaps/swaps.test.ts` (apply, undo with `kept_original`, dismiss persistence, caps, old
entries), `share/offlineQueue.test.ts` (coalescing, replay, storage, network-failure detection),
`share/sharedChecklist.test.tsx` (checkbox, offline, reload, realtime), `share/shareManage.test.tsx`
(revoke, remove, rollback, stale link), `scan/scanEvents.test.tsx` and `consent/phase2Events.test.tsx`
(payloads), `profile/homeStore.test.tsx`, `lib/attributes.test.ts`, `ui/BottomSheet.test.tsx` (early
Escape), `SubstitutionView.test.tsx` and `ResultsView.test.tsx` (disclaimer, Hebrew tags, links).
E2E: `phase2-share-swaps.spec.ts` (share entry, revoke, checkbox across two devices, offline queue,
swap undo after a reload), `secondary-onboarding-profile.spec.ts` (home store to results),
`core-compare.spec.ts` and `core-substitution.spec.ts`. A11y: `tests/a11y/zoom-195.spec.ts`.

## Phase 3 (unblock round)

Web features that need no real data: voice list input (#65), monthly budget and spend (#70), the
scan page reading its code from the URL, and the UI half of recipe to list (#71). They were built
against `src/mocks/handlers.phase3.ts` and then reconciled with the real routes of `services/api`
(`routes/spend.py`, `routes/recipe.py`) and the regenerated `types.ts`. Nothing here reads real
prices; every number in the tests is a mock value.

### Voice list (#65)

`features/voice/`: `speech.ts` (the typed seam over `SpeechRecognition` / `webkitSpeechRecognition`,
error mapping, transcript assembly), `useVoiceInput.ts` (the state machine, `useVoiceSupported`),
`VoiceSheet.tsx` (the sheet), mounted by `ListBuilder`.

- **Detection at run time.** `getRecognizerCtor()` looks for the constructor; the answer is `null`
  until hydration, so the server and the first client render agree. Supported: the microphone
  button (`voice-open`) sits in the input row. Not supported: the button is not rendered and a hint
  ("הכתבה קולית לא זמינה בדפדפן הזה. אפשר להקליד או להדביק את הרשימה.", `voice-unsupported`) takes
  its place. Whether `he-IL` actually works per browser and OS is **not verified here**; the
  per-browser results the issue asks for (iOS Safari installed PWA, Android Chrome) are a manual
  check that is still open.
- **Permission flow, like `/scan`.** The sheet explains first (what to say, that SmartCart records and
  stores no audio, that the recognition itself runs in the browser's speech service, in Chrome on
  Google's servers) and the recognizer is created only on "התחלת הקלטה", so the browser's microphone
  prompt follows the tap. Denied, no microphone, no speech, network, language not supported and
  failure each have their own Hebrew message that points back to typing; the typed input is never
  disabled.
- **Recognition.** `lang = "he-IL"`, `continuous`, `interimResults`. The sheet shows the phrases
  while listening; one phrase per pause becomes one line.
- **Confirm step.** After "סיימתי לדבר" (or the recognizer ending) an editable textarea shows what was
  heard. Nothing is parsed until "הוסיפי לרשימה": the text then goes through the same `parseList`
  call as a pasted list (`ListBuilder.parseInto`), so quantities, flexibility and the amber
  confirmations behave identically. A failed request keeps the text.
- **Events** (`features/consent/betaEvents.ts`, `track.ts`): `voice_started {engine: "web_speech"}`
  on the tap, `voice_completed {outcome, duration_ms, item_count}` once per attempt, always after a
  start. `outcome`: `parsed` (rows added, `item_count` = rows), `empty` (nothing heard), `cancelled`
  (sheet closed, re-record, leaving the page), `error` (denied, no microphone, network, failure). No
  transcript, no text. Same consent gate as every event.
- Not built: the server speech-to-text fallback, its cost per minute and monthly cap, and the audit
  that audio is deleted (the app never holds audio, so there is nothing to delete). Those are the
  open acceptance criteria of #65.

### Monthly budget and spend (#70)

`features/budget/`: `month.ts` (Israel calendar), `budgetState.ts`, `spendState.ts`, `sync.ts`,
`BudgetRemaining.tsx`, `MonthlyBudgetSection.tsx`, `SpendChart.tsx`.

| Key | Holds |
|---|---|
| `sc-budget-v1` | `{ "monthly": 2500 }`, whole ILS from 1 to 1,000,000 (invalid or damaged reads as no budget) |
| `sc-spend-v1` | `{ version: 1, entries: SpendRow[], pending: string[] }` |

Both are in `LOCAL_DATA_KEYS`, so "מחקי את הנתונים שלי" removes them.

- **Budget.** Profile ("תקציב חודשי", anchor `#budget`) sets, changes and clears it. It travels with
  the profile: `ProfileSync` reads `monthly_budget` on sign-in (the account's value replaces the
  device's; a device budget the account lacks is offered once) and then sends `monthly_budget` in
  `PUT /me/profile` **only when the person changed it** (omitted keeps the stored value, an explicit
  `null` clears it). Other profile saves never carry it.
- **Spend entry.** "סיימתי לקנות" (the finish button of store mode) opens the summary sheet, which has
  a switch "לרשום בתקציב החודשי" (on by default). On "סיום וניקוי" one entry is written: Israel
  date, `store_id`, `store_name`, `total`, `item_count`, `plan` (`single`, or `split` for a store's
  part of a split; `ShoppingSession.plan`). `total` is the sum of the lines the person ticked, or,
  when nothing was ticked, of the whole store basket; the sheet says which. Never item names, a list
  name or a location.
- **Trust.** Totals are "לפי המחירים שהוצגו", not receipts: said in the finish sheet, under "נותר
  החודש", in the Profile section and in the chart caption. Net saving stays versus the person's own
  store and is shown with the same number as "החיסכון שלי".
- **Screens.** `BudgetRemaining` ("נותר החודש" against the budget, "אחרי הקנייה הזו" for the plan on
  screen, with that plan's price time) renders under the plans on `/compare` and under the summary on
  `/split`. Without a budget it renders nothing. Over budget it is amber with the overage, never a
  clamp and never red. The Profile section adds spent and remaining this month, this month's shops, and a
  six-month bar chart (`SpendChart`, plain SVG, oldest month on the right as in the price history, a
  dashed budget line, the drawing `aria-hidden` and a table of every month under it; month names under
  the bars are hidden at 195 px).
- **Account sync** (signed in only; `sync.ts`). Entries recorded while signed in are `pending` and
  sent with `POST /me/spend` (body `SpendEntryIn`, 201 with the numeric `id`, kept as `server_id`);
  Profile pulls the last six months with `GET /me/spend?month=` and adds entries the device lacks
  (local id `srv<id>`). Failures are swallowed and the entry stays pending. Entries recorded signed
  out stay on the device. A shop whose `POST` succeeded but whose response was lost would be added
  again by the next pull; that edge is accepted.
- Not built: correcting a total (`PUT /me/spend/{id}`), deleting one entry, the export
  (`GET /me/spend/export`) and per-category spend are API-only for now. Server rows are removed by the
  account deletion on the API side.

### Scan by URL

`/scan?code=<ean>` runs the lookup as if the code were typed into the manual field, without the
camera (`getUserMedia` is not called). It waits for the shopper and the nearby stores, so the lookup
names the store the person is in; the code is also put in the manual field. A code that fails the
EAN check digit shows the manual-entry error and makes no request. Reported as a manual scan
(`scan_started {engine: "manual"}`). `docs/fullstack.md` gap 5 can be closed; `tests/fullstack` was not
touched and can now use the URL.

### Recipe to list (#71)

`features/recipe/`: `RecipeSheet.tsx`, `scale.ts`. "ממתכון" under the input opens a sheet with two
sources, pasted text or a link, and `POST /parse-recipe {text} | {url}` (exactly one; the sheet
checks that a link is http(s) before any request). The answer is a preview: the title, a servings
stepper (when `servings` is not null), the items with scaled quantities, and the lines left
unresolved. Quantities scale **in the browser** from the recipe's servings: weighed goods smoothly
in 50 g steps, anything bought by the piece or pack rounded up to whole ones. "הוסיפי N פריטים"
adds the rows to the list, where uncertain matches (`needs_confirmation`) show the list's normal amber
confirmation; unresolved lines are added as rows in the "לא זוהו" group, where they can be edited or
removed. With `servings: null` nothing can be scaled and the sheet says so. The link goes to the
server, which fetches the page; the sheet says so.

### Mocked routes and shapes

`src/mocks/handlers.phase3.ts`, answered by `mockApi` in e2e and by `NEXT_PUBLIC_API_MOCK=1`. They
follow `services/api`; `GET /me/spend` returns `budget: null` in the mock (the budget is on the
profile) and `PUT`/`DELETE /me/spend/{id}` and `GET /me/spend/export` are not mocked.

| Route | Request | Response |
|---|---|---|
| `POST /me/spend` | `SpendEntryIn` `{date: "YYYY-MM-DD", store_id, store_name, total, item_count, plan: "single"\|"split"}` | 201 `SpendEntry` (the same fields, `id: number`, `total: "371.40"`) |
| `GET /me/spend?month=YYYY-MM` | month optional (default the current one) | `SpendMonth` `{month, entries (oldest first), total: "300.30", budget: string\|null}` |
| `POST /parse-recipe` | `{text?, url?, servings?}`, exactly one of text and url | `{title: string\|null, servings: number\|null, items: ParsedRow[], unresolved: string[]}` |
| `PUT /me/profile` | `monthly_budget` optional (omit keeps, null clears) | `Profile.monthly_budget: "2500.00"\|null` (already in `handlers.ts`) |

Also in this round: `src/mocks/parseRow.ts` (the mock list parser, moved out of `handlers.ts`
which still exports it) and `IconBook`.

### Storage keys and events added

| Key | Owner |
|---|---|
| `sc-budget-v1`, `sc-spend-v1` | `features/budget` |

Events: `voice_started`, `voice_completed` (above).

### Tests (this section)

Unit: `voice/speech.test.ts`, `voice/voice.test.tsx` (the sheet against a fake recognizer, the events,
the list builder path), `consent/voiceEvents.test.ts`, `budget/budget.test.ts` (calendar, budget,
spend state, arithmetic, sync), `budget/budgetUi.test.tsx` (the card on results and split, the Profile
section and chart, the finish sheet), `profile/budgetSync.test.tsx` (`monthly_budget` omitted, set,
cleared), `recipe/recipe.test.tsx`, `mocks/handlers.phase3.test.ts`, `scan/scanUrl.test.tsx`. The fake
recognizer is `tests/unit/fakeSpeech.ts`. E2E: `phase3.spec.ts` injects a fake `SpeechRecognition`
(`phase3-helpers.ts`); `secondary-onboarding-profile.spec.ts` now also asserts the net saving on the
first results page after onboarding and that `/split` was never needed. A11y: `tests/a11y/phase3.spec.ts`.
One unrelated finding fixed on the way: checked rows in store mode were dimmed with `opacity: 0.6`,
which put the tags and the update time below 4.5:1; they now keep their color and the name and price
turn muted.

## Photo to list (#61, #68)

The web half of receipt scanning and handwritten list photos. "מצילום" in the list builder (next to
"ממתכון") opens `features/photo/PhotoSheet.tsx`; the server half (`POST /parse-image`, the OCR
providers, the monthly cap) is a separate workstream, so everything here runs against the mock in
`src/mocks/handlers.phase3.ts`.

**Flow.** choose, then consent (once), then reading, then preview, then the list.

1. **Choose.** Two cards, "קבלה" and "רשימה בכתב יד", each with "צילום" (a file input with
   `accept="image/*" capture="environment"`, which opens the back camera on a phone) and "בחירת קובץ"
   (the same input without `capture`). The inputs are hidden and sit outside the dialog, so the sheet's
   focus trap never counts them.
2. **Checks on the device** (`imageFile.ts`). A file that is not an image, or is over 8 MB (the
   server's limit), is refused with a message and no request. Anything whose longest side is over
   2400 px is redrawn on a canvas as a JPEG (quality 0.85, white background) before the upload, which
   keeps phone photos small; a format the server does not take (HEIC, GIF) goes
   through the same redraw when the browser can decode it, and a JPEG, PNG or WebP the browser cannot
   decode is sent as it is. The size logic (`checkImageFile`, `fitWithin`, `prepareImage`) is tested
   without a canvas behind an `ImageIO` seam, and an e2e test checks that a 4000 x 3000 photo reaches
   the server as 2400 x 1800.
3. **Consent** (`features/consent/imageConsent.ts`). The first upload asks: the image is read on our
   server and deleted right away, the text is not kept, nothing is shared; "מסכים/ה" stores the
   answer, "לא עכשיו" closes the sheet. **No consent, no request**: the sheet checks it before
   `parseImage`, and `parseImage` refuses to send without it (`X-Image-Consent: 1` is sent only
   then). A 403 from the server (it disagrees) sends the person back to the consent step.
   Withdrawable in Profile, "פרטיות ונתונים" (`ImageConsentToggle`, a switch); turning it off removes
   the key at once and the next photo asks again. Delete-my-data removes it too.
4. **Reading.** A progress state with "ביטול"; cancelling aborts the request and drops a late answer.
5. **Preview** (`PhotoPreview.tsx`, the recipe preview's pattern). Matches the server is sure about
   are listed and ticked; matches with `needs_confirmation` are in an amber group "לאישור" (the list's
   amber), unticked, each with "נקרא: <the line as read>"; the lines in `unresolved` are in "לא זוהו",
   each an editable field with a checkbox (typing ticks it). A receipt adds a summary: chain (named
   from the chain id, with the store hint), the printed total and the number of lines. The photo is
   shown small, from an object URL on this device only, so what was read can be checked against what
   was written. "התמונה נמחקה מהשרת" is shown when `deleted`. **Nothing joins the list until
   "הוסיפי N פריטים לרשימה"**; then the ticked matches are added as they came (an uncertain match
   keeps its normal amber confirmation in the list), an unresolved line the person rewrote goes through
   `/parse-list` once more (and joins as typed if that fails), and one left as read joins as a
   not-found row in the list's "לא זוהו" group.
6. **Failures** (`photoErrors.ts`), each with its own message and "להקליד במקום" (closes the sheet and
   puts the cursor in the list input): 403 consent (back to the consent step), 413 and 415 (another
   photo), 429 ("הגענו למכסה החודשית, נסו שוב בחודש הבא", no retry), 501 and 503 (no OCR provider,
   retry), a dropped connection (retry), anything else (retry). An image with nothing readable has its
   own state.

**Events.** `image_parsed {kind, outcome, item_count?, duration_ms?}` once per attempt that reached a
decision: `parsed`, `empty`, `refused` (not an image, over 8 MB, 403, 413, 415, 429) or `error`. Counts
and fixed strings only; never the text, the file name or the image. Declining the consent step is not
an event.

**API helper.** `parseImage(kind, file, consent, { signal })` in `src/api/client.ts` sends
`multipart/form-data` through `api.POST` with a `bodySerializer` that builds the `FormData`, so the
bearer-token middleware (`ensureApiAuth`) and the mock transport apply like for every other helper;
openapi-fetch drops its JSON content type for a `FormData` body, so the browser sets the boundary. The
generated body type says `image: string`, so the file is cast once, in that function.

**Mock** (`POST /parse-image`). Without `X-Image-Consent: 1` it answers 403. File names pick the case:
`x-413.png` too large, `x-415.png` type, `x-429.png` monthly cap, `x-503.png` no OCR provider,
`x-500.png` failure, `empty.png` nothing read, `slow.png` waits 1.5 s. The real limits apply as well
(not JPEG, PNG or WebP is 415, over 8 MB is 413, no image part is 422). A `list` upload returns three
matches (one uncertain) and two unresolved lines; a `receipt` returns four matches (one uncertain), two
unresolved lines and a summary (Shufersal, "שופרסל דיל מודיעין", total 187.40, six lines).

| Key | Owner |
|---|---|
| `sc-image-consent-v1` | `features/consent/imageConsent.ts`; `"1"` means agreed. In `CORE_DATA_KEYS`, so "מחקי את הנתונים שלי" removes it and `useImageConsent` hears the `storage` event |

Copy is in `src/i18n/messages/photo.ts` (`ar` is a copy of the Hebrew under a `// TODO ar`, #73).

Not built: the on-screen crop that #68 mentions (the preview shows the photo beside what was read, but
there is no crop step), and the accuracy and cost evaluations the issues ask for (they need the server
half and real photos). Receipts are never stored: the file lives in memory in the sheet until it closes.

Tests: `features/photo/imageFile.test.ts` (checks, `fitWithin`, `prepareImage`),
`features/photo/photo.test.tsx` (entry, consent gate, preview, errors, events, token, Profile switch),
`features/consent/imageConsent.test.ts`, `mocks/handlers.photo.test.ts` (node environment, the magic
names), `i18n/messages/photo.test.ts`; `tests/e2e/photo.spec.ts` (with `photo-helpers.ts`, which answers
`/parse-image` with the real multipart body because `mockApi` rewrites bodies as JSON) and
`tests/a11y/photo.spec.ts`.
