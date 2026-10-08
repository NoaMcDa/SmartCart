# Accessibility audit report

Issue #26. Israeli standard 5568 is equivalent to WCAG 2.0 level AA and applies to apps and sites
(verified: `product-and-market.md`, "Legal rules we follow"). Audit date 2026-10-07, on phase-1-base after
W4a (shell, tokens), W4b (list, results, substitution card) and this workstream. Screens W5 owns
(`/onboarding`, `/product/[id]`, `/profile`, `/split`, `/map`, `/store-mode`) were still placeholders: they
are covered by the automated suite and must be re-audited when built.

This is an automated audit plus a documented list of what only a person can check. **It is not a
conformance claim.** The public statement (`/accessibility`) says the same.

## What is checked automatically (CI job `a11y`, `npm run a11y`)

| Check | Where | Result |
|---|---|---|
| axe-core, tags `wcag2a` and `wcag2aa`, every route in `tests/e2e/routes.ts` (22 routes) at 390 px and 1280 px, light and dark: **serious or critical violation fails** | `tests/a11y/axe.spec.ts` (88 tests) | no violation |
| The harness itself fails on a real violation (low-contrast text) | `tests/a11y/keyboard.spec.ts` | proven |
| Core flow states, not only first paint: list with nine items, flexibility sheet open, results, basket details open, substitution card; both widths, both themes | `tests/a11y/core-flow.spec.ts` | no violation |
| Core flow by keyboard only: paste, open and dismiss the flexibility sheet (focus goes in, stays in, returns to the opener), compare, open a substitution | `tests/a11y/core-flow.spec.ts` | completes |
| Skip link is the first stop and works; every Tab stop has a visible focus indicator (SEO pages) | `tests/a11y/keyboard.spec.ts` | pass |
| Controls on SEO pages (list rows, breadcrumbs, buttons, footer and nav links) are at least 44 px tall at 390 px | `tests/a11y/keyboard.spec.ts` | pass |
| Reflow: no horizontal scroll at 320 px on every route (WCAG 1.4.10, a 2.1 criterion, stricter than 2.0) | `tests/a11y/keyboard.spec.ts` | pass |
| 200% zoom on a phone (195 CSS px): SEO page content and footer stay inside the viewport (data tables scroll inside their own wrapper) | `tests/a11y/keyboard.spec.ts` | pass |
| 200% zoom on a phone (195 CSS px), **every route** in `routes.ts` (22) and the states behind a tap: no element outside the viewport, `scrollWidth` of the document and the body at most 195 | `tests/a11y/zoom-195.spec.ts` (27 tests) | pass, results below |
| Text-only 200%: every route plus store mode and the budget section, 390 px and 1280 px, two ways of scaling; no horizontal scroll, nothing outside the viewport, no clipped text in headings, buttons, labels, table and price cells, chips and tags; plus the open budget correction form, the delete confirmation and the flexibility sheet | `tests/a11y/text-scaling.spec.ts` (102 tests) | pass, results below |
| Contrast of every token pair in `ux-design.md` is at least 4.5:1 for text in both themes | `src/styles/tokens.test.ts` (unit) | pass |
| Structural axe rules on the SEO components (jsdom, contrast excluded) | `src/features/seo/*.test.tsx` | no violation |
| Lighthouse accessibility, best practices and SEO on the six SEO page types | `lighthouserc.seo.json`, CI | 100 each (local run) |
| Icon-only buttons have a name: axe `button-name`, `link-name`, `aria-*` rules run on every route | `tests/a11y/axe.spec.ts` | no violation |
| Meaning not by color alone: the design system gives every chip and tag an icon and text; axe `link-in-text-block` and `color-contrast` run on every route | `src/components/ui`, axe | no violation |
| `lang="he"` and `dir="rtl"` on every route | `tests/e2e/shell.spec.ts` | pass |

Moderate and minor axe findings are attached to the Playwright report as `non-blocking-violations.json` and
do not fail the run.

## Open findings

1. ~~Shell top bar overflows at 195 px~~ Fixed in #91 (`top-bar-zoom.spec.ts`). The 195 px check now covers
   every route and the main states, see "200% zoom at 195 px" below.
2. ~~Split view has no keyboard or non-drag path~~ Fixed: the earlier line was stale. `/split` is built and
   there is no drag at all: every item row in `features/split/SplitView.tsx` has a native button
   "העברה ל{chain}" (accessible name "העברת {item} ל{chain}"), so it is reachable by Tab and works with
   Enter and Space. Where the move is not allowed (it would drop a promo or break the split) the button
   stays focusable, is `aria-disabled` and points at the reason with `aria-describedby`. Verified in the
   code and by `SplitView.test.tsx` (moves an item, blocked case) and
   `secondary-split-map-store.spec.ts` (moves by button in the browser).
3. ~~Text-only scaling is not automated~~ Now automated, see "Text-only scaling at 200%" below. What stays
   manual: a real phone with the system font at 200%, because Chromium has no text-only zoom to drive.
4. **Reduced motion** and **forced colors / high contrast** modes are not tested.

## Text-only scaling at 200% (issue #26, finish round)

`tests/a11y/text-scaling.spec.ts` on the production build, Chromium, at 390 px and 1280 px wide. The
viewport stays put and only text grows, which is WCAG 1.4.4 as a user with a larger system font sees it.
Chromium has no text-only zoom, so the spec scales in two ways:

- **root**: `html { font-size: 200% }`, what the default font size of a desktop browser changes. The app
  sizes text in px (289 `font-size` declarations, none in rem), so this mode moves almost nothing. It is
  kept because it proves the root size is not used anywhere in a way that breaks.
- **all**: every element's computed `font-size` and `line-height` doubled in place, which is what an
  Android system font scale does to px-sized text. This is the mode that stresses the layout. The spec
  asserts the body font size really doubled, so it cannot pass by scaling nothing.

Per route and mode it asserts: `documentElement` and `body` `scrollWidth` at most the viewport width; no
visible element outside the viewport; and for headings, buttons, tabs, switches, checkboxes, labels,
table cells, price cells, chips and tags that contain text and clip or cannot scroll,
`scrollWidth <= clientWidth` and `scrollHeight <= clientHeight`. Tables that scroll inside their own
wrapper and the map canvas are skipped, as in `zoom-195.spec.ts`. Routes: the 22 in `routes.ts`,
`/store-mode?store=101` and `/profile#budget`, with a comparison, a budget and two recorded shops seeded.
States behind a tap: the budget correction form, the delete confirmation and the flexibility sheet.

Result: **102 of 102 pass**. The first run of the "all" mode found two real problems, both fixed with logical
properties and wrapping only:

| Where | Found | Cause | Fix |
|---|---|---|---|
| `/product/[id]` per-store table, below 640 px | store cell 125 px and shelf-price cell 133 px in a 103 px column | the shelf cell was `nowrap` and the cells could not shrink below their longest word | `.shelfCell` wraps; `.storeCell`, `.shelfCell`, `.finalCell` get `min-inline-size: 0` and `overflow-wrap: anywhere` (`Product.module.css`) |
| `/store-mode` row tags | a promo tag ("מבצע: 3 ב-₪14.70") 147 px in a 135 px row | the tag is an inline-flex pill with an unbreakable price | `.tags > *` gets `max-inline-size: 100%` and `overflow-wrap: anywhere` (`StoreMode.module.css`) |

The "root" mode found nothing. A switch track (a button with no text) reported 50 px in 48 px because of
its thumb; that is not text, so the check only looks at elements that contain text.

Not covered: text-only scaling at 200% on a real phone (Android font scale, iOS Dynamic Type "larger
accessibility sizes"), which is a manual check. iOS Safari ignores px-based text scaling unless the page
opts in, so Dynamic Type does not change this app at all today; moving sizes to rem would be the way to
honor it and is not done.

## 200% zoom at 195 px (issue #101)

Measured by `tests/a11y/zoom-195.spec.ts` on the production build (Chromium, viewport 195 x 844). Before the
fixes, four routes overflowed; after them none does, and none of the states behind a tap does either.

| Route or state | Before | Cause | Fix | After |
|---|---|---|---|---|
| `/` list builder | 208 px wide | the input row (textarea, mic, clipboard, add button) did not fit in one row | below 260 px the row wraps: textarea first, buttons below, the add button filling the last row | fits |
| `/` with nine items | an item row overflowed | name, stepper and remove button in one row | below 260 px the name takes its own row | fits |
| `/profile` | 264 px wide | `SegmentedControl` options were `nowrap` (travel mode, kosher level, theme) | options wrap their text (`white-space: normal`, `flex: 1 1 auto`) | fits |
| `/product/1001` | 280 px wide | the same `SegmentedControl` (flexibility levels in the alert form) | same fix | fits |
| `/design-system` | 216 px wide | the card's price row did not wrap | `.spread` wraps | fits |
| results with the smart cart | the plan's distance label overflowed | `planTop` did not wrap | wraps | fits |
| substitution card | the "התחליף" tag and the two action buttons overflowed | two columns of about 70 px, and a row of two buttons | below 260 px the columns stack, the buttons wrap | fits |
| every other route (18 of 22) | fits | | | fits |
| shared list with a pending invite and a checked item, the share sheet, onboarding steps, flexibility sheet, scan result card | not measured before | | | fits |

All fixes use logical properties and media queries on width only; at 390 px nothing moved.

## Phase 3 screens (unblock round)

`tests/a11y/phase3.spec.ts` (23 tests): axe (`wcag2a`, `wcag2aa`, serious or critical fails) in the
states behind a tap, at 390 and 1280 px in both themes; 195 px overflow; keyboard-only use. No
violation. Not a conformance claim; the manual items below still apply.

| Screen or state | axe, 390 and 1280 px, light and dark | 195 px (200% zoom) | Keyboard |
|---|---|---|---|
| List builder with the microphone | no violation | fits | the mic is a 44 px button reached by Tab |
| Voice sheet: intro, listening, review, microphone denied | no violation | fits, also with a long transcript | opens with Enter, focus moves in and stays in (Tab x8), start, stop and add by Enter, Escape closes and focus returns to the mic |
| Recipe sheet: input and preview | no violation | fits | field, read, the servings stepper buttons and add all by keyboard |
| Results with the "נותר החודש" card (over budget) | no violation | fits | a link to the budget |
| Profile budget section with the six-month chart | no violation | fits; month names under the bars are hidden at 195 px and the table carries them | the budget field submits with Enter, the status is announced (`role="status"`) |
| Store mode finish sheet with the budget switch | no violation | fits | the switch is a `role="switch"` with a visible label |

Notes: the chart's drawing is `aria-hidden` and a real `<table>` (caption, column and row headers)
carries every number; the over-budget state is amber text with an icon and words, not color alone;
the voice live transcript is not a live region (interim text would be read out on every change), the
status line "מקשיבה…" is. Found and fixed while testing the finish sheet: checked rows in store mode
were dimmed with `opacity: 0.6`, so the tags and the update time fell below 4.5:1 (axe
`color-contrast`); they keep their color now and only the name and price turn muted, with the
strikethrough unchanged.

Manual and still open for these screens: the screen reader pass (VoiceOver, TalkBack) on the voice
sheet and the chart table, and whether `he-IL` speech recognition works on iOS Safari (installed
PWA) and Android Chrome.

## What remains manual

1. **Screen reader pass in Hebrew RTL**, not done. Do it with VoiceOver (iOS Safari) and TalkBack
   (Android Chrome) on: paste and list rows, the flexibility sheet, the results cards, the substitution
   card, the SEO pages, tables. Check specifically: prices and numbers read correctly inside Hebrew (the
   `Price` component is an LTR island, and the comma stays outside it); the order of the bottom tabs; the
   chevron directions; the announcement when results load (there is no live region today, so it may be
   silent). Record findings and fixes in this file under "Screen reader pass". The beta recruits at least
   some assistive-technology users (`beta-plan.md`).
2. **Keyboard on a real browser per platform**: Safari does not Tab to links by default (a system setting).
3. **Standard 5568 mapping.** 5568 follows WCAG 2.0 AA, and adds Israeli requirements on top (the
   accessibility statement and a contact for requests are the main ones: a statement page exists, the
   contact detail is not set yet). Map every WCAG 2.0 A and AA criterion to a check before launch. The
   table below is the starting point, with the automated coverage; "manual" rows need a person.
4. **A legal read** of the accessibility statement. Not done.

### WCAG 2.0 criteria and how they are covered

| Principle | Criteria | Coverage |
|---|---|---|
| Perceivable | 1.1.1 non-text content | axe `image-alt`, `svg-img-alt`; icons are inline SVG with accessible names or hidden; no images on SEO pages |
| | 1.3.1 info and relationships | axe `table`, `th-has-data-cells`, `list`, `label`; tables have captions and header scopes; manual for reading order in a screen reader |
| | 1.3.2 meaningful sequence | DOM order equals visual order in RTL (logical properties, RTL guard in lint); manual |
| | 1.3.3 sensory characteristics, 1.4.1 use of color | icon plus text on every chip and tag; manual review of new components |
| | 1.4.2 audio control | no audio |
| | 1.4.3 contrast (minimum) | token test (unit) and axe `color-contrast` on every route in both themes |
| | 1.4.4 resize text | zoom checks above; text-only scaling manual (finding 3) |
| | 1.4.5 images of text | none |
| Operable | 2.1.1 keyboard, 2.1.2 no keyboard trap | core flow by keyboard; sheet traps focus on purpose and Escape releases it; split view open (finding 2) |
| | 2.2.1 timing adjustable, 2.2.2 pause stop hide | no time limits, no auto-updating content |
| | 2.3.1 three flashes | none |
| | 2.4.1 bypass blocks | skip link, tested |
| | 2.4.2 page titled | each route has a title; axe `document-title` |
| | 2.4.3 focus order, 2.4.7 focus visible | keyboard tests on SEO pages and the core flow |
| | 2.4.4 link purpose, 2.4.5 multiple ways, 2.4.6 headings and labels | axe `link-name`, `heading-order` (moderate); one h1 per page checked by the route test |
| Understandable | 3.1.1 language of page | `lang="he"` tested; 3.1.2 language of parts: English fragments carry `lang="en"` |
| | 3.2.1 on focus, 3.2.2 on input | no context changes on focus or input (manual) |
| | 3.3.1 to 3.3.4 input errors, labels, suggestions, error prevention | axe `label`; the list input has a visible-or-programmatic label; manual for error messages |
| Robust | 4.1.1 parsing, 4.1.2 name, role, value | axe `aria-*`, `duplicate-id`, `button-name`; the switch, radiogroup and dialog roles are unit-tested |

## Fixes made during the audit

The audit itself needed no fix on the SEO pages: they were built against the checks. Decisions that came
from them: breadcrumb links, list rows and footer links get 44 px targets; tables have captions and
column and row header scopes and scroll inside their own wrapper; the basket-index disclosures use native
`details` and `summary` (keyboard and screen-reader operable without scripting); prices are LTR islands;
estimated values carry a text tag, not only color; the accessibility statement says what was not checked.
