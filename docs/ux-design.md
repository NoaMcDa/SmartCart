# UX and design

The interactive design canvas is at https://claude.ai/artifact/VRNDChNKiHym9nG5r5dGML (private;
share from the page's Share menu). Artboard sources are mirrored in `design/artboards/`. Six
artboards: four phone screens at 390 px and two desktop pages at 1280 px.

## Principles

1. **Net saving is the headline number**, after travel and delivery, versus the store the user said they use. Never versus the most expensive chain.
2. **Transparency over magic.** Every substitution shows why (matching and differing attributes) and has an undo.
3. **Visible reliability.** Update date, "club promo" tag, "estimated price (weighed)" tag, "report a gap".
4. **Less typing.** Paste, voice, history, recurring lists.
5. **Real RTL, not mirrored LTR.** Numbers and prices LTR inside Hebrew text, next/back chevrons point the RTL way, logical start/end instead of left/right, a readable Hebrew font (Heebo), tested with Arabic text for the future.
6. **Accessibility.** AA contrast, dynamic text sizes, labels for screen readers, meaning never by color alone (icon plus text next to every green).

## Navigation

Bottom bar with five tabs, right to left: Lists, Compare, Scan (raised center button), Alerts,
Profile. The map is a view inside Compare, not a tab. Desktop uses a top bar with the same sections.

## Screens

**Onboarding (3 steps, each skippable, each with "why we ask").** Location permission or city and
neighborhood, with a radius slider 1–15 km. Chain logo cards to pick "my store" and club memberships.
"How do you shop?" with car, walking or transit, delivery, and a slider "what is an extra stop worth
to you?" (0–50 ILS).

**List builder.** Large top input with placeholder "חלב, 2 רסק עגבניות, סלמון…" and mic and
clipboard buttons. Items grouped by department. Each row: canonical name, quantity stepper, a colored
flexibility chip. Low-confidence parses show an inline amber confirmation ("you wrote olive oil, did
you mean extra virgin 750 ml?"). Weighed produce carries an "estimated price" tag. Sticky bottom bar:
"basket estimate ₪412–₪468" and the Compare button.

**Flexibility sheet (bottom sheet).** Title with the product. Three radio options with one-line
explanations and examples ("any brand: Tnuva, Tara, Yotvata, private label; kept: 3% fat, fresh,
1 liter"). Checkboxes for soft attributes to allow ("different pack size", "carton or bag", "different
fat percentage"). Switch "remember this for all milk".

**Comparison results.** Header with item count, radius and update time. List/map toggle. Recommended
card with accent border: store and branch, distance, basket total, net saving in a green block with
the baseline named, "X items substituted" link, "Y items missing" in red, promos included. Split card:
two stores, total, net saving after fuel, extra minutes. Minimum-effort card: the user's own store as
the baseline. Footnote: price at checkout governs.

**Cart split view.** Two columns or tabs, one per store, with subtotals. Drag an item between stores
and watch the saving update. A waterfall at the top: base price, chain switch, brand swaps, promos,
travel cost, net.

**Substitution card (trust element).** "We replaced X with Y". Original and substitute side by side
with shelf price and price per 100 g. Saving times quantity. Tags: green check for matched attributes
(same type, same size, kosher level), amber for an extracted attribute marked unverified, neutral for
differences (private label instead of brand). Source line with confidence. Buttons: continue, keep the
original, not a good substitute.

**Product detail.** Canonical name, variants ranked by unit price, 90-day history with promo markers,
price per nearby store, "alert me below ₪__".

**Map.** Pins per store with the basket price on the pin, bottom sheet for the selected store.

**Scan.** Full camera. On recognition: "here ₪14.90, cheapest nearby ₪11.50 at Rami Levy, cheaper
substitute ₪8.90 (private label)", with add to list.

**Profile.** Location and radius, chains and clubs, diet and kosher preferences, flexibility defaults,
"my savings" (cumulative, real), privacy and data deletion.

## Key flows

1. "Where is cheapest this week?": paste list, confirm only the flagged rows, compare, pick an alternative, in-store mode (list sorted by department with checkmarks).
2. In store: scan, see substitute, add.
3. Alert: "any soy drink on promo 2 for ₪15 at Yochananof, 1.8 km", add to list.

## Design tokens

Font: Heebo (400, 500, 600, 700) from Google Fonts, packaged as an asset in production so it works
offline.

| Token | Light | Dark | Use |
|---|---|---|---|
| bg | #F6F5F2 | #141413 | Page background |
| surface | #FFFFFF | #1F1F1D | Cards, inputs, sheets |
| subtle | #F1EFEA | #2A2927 | Steppers, secondary buttons, group headers |
| border | #E3E0DA | #33322F | Card and input borders |
| divider | #EEECE7 | #2A2927 | Row dividers |
| text | #1A1A1A | #F2F1EC | Primary text |
| muted | #5C5952 | #A8A49B | Secondary text (≥ 4.5:1 on surface) |
| faint | #8A867E | #7D7971 | Placeholders, tertiary icons |
| accent (fill) | #1F5F8B | #1F5F8B | Primary buttons, scan button, badges; white text on it |
| accentFg | #1F5F8B | #7FB3E3 | Links, active nav, recommended border |
| accentSoft | #EEF4F9 | #1C2F3D | Selected option background |
| brandBg / brandFg | #D9F0EA / #0E5842 | #143D30 / #7FD4B4 | "Any brand" chip |
| exactBg / exactFg | #E6EBF2 / #263D5C | #22314A / #A9C1E6 | "Exact product" chip |
| warnBg / warnFg | #FBEFD6 / #7A4E00 | #3E2E0E / #F0C068 | "Close substitute" chip, estimated, unverified, confirmations |
| goodBg / goodFg | #E3F3EA / #1B6B45 | #16352A / #7FD4A6 | Savings |
| badFg | #A32D2D | #F08C8C | Missing items, "not a good substitute" |

Color rules: green only for savings, amber for estimated or unverified, red only for missing. The
three flexibility levels differ in hue and lightness and always carry an icon (lock, tag, refresh), so
they read without color. Icons are inline stroke SVG, never emoji.

Layout: 16–20 px side gutters on phone, 1200 px max content width on desktop, 44 px minimum touch
targets, 12–16 px card radius, pill chips.

## Dark mode

Every artboard carries a `dark` tweak and a visible switch in its header (moon in light mode, sun in
dark mode). The switch toggles the theme in Play mode. All colors in the artboards are theme holes
resolved from the token table above, so the two themes stay in sync. In production, follow the OS
preference by default and expose the same switch in the profile and the header.

## RTL implementation notes

- Root element `dir="rtl"`, `lang="he"`.
- Prices wrapped in `<span dir="ltr">₪389</span>` so the currency symbol and digits do not reorder inside Hebrew sentences.
- Use `padding-inline`, `margin-inline`, `text-align: start`, `justify-self: start`. Never left/right.
- Back chevron points right; "next" chevrons point left.
- Known Flutter bug on Hebrew punctuation placement is irrelevant to the web stack, but test punctuation next to numbers in mixed strings anyway.
