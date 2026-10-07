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
| `npm run gen:api` | Regenerate `src/api/types.ts` from `src/api/openapi.json` (commit the output; CI fails if it is stale) |
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
