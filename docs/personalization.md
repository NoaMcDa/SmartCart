# Personalization (phase 3): useful, private, explainable

Built on synthetic data. Nothing here has run against real shoppers or real files; every threshold
below is a proposal (an estimate, not a measurement) to be tuned in the beta.

Five things, all from the person's **own** lists and finished trips, all on the device first:

1. **My usual** ("הרגילים שלי"): the items bought most often, one tap to add them, and on every list
   row "you usually take N of these".
2. **Buy again** ("לקנות שוב?"): items whose usual interval has passed, dismissible, with the reason
   in one line ("לרוב את קונה כל ~10 ימים").
3. **Brand preferences**: after the person keeps an exact brand or turns a substitute down several
   times in a category, an *offer* to make that category's flexibility default "exact", with an undo.
4. **Large-family value packs**: a profile preference, off by default, that makes the list builder
   point out a larger pack with a lower unit price.
5. **Privacy**: it is in the export, in "delete my data", on the privacy page, and its analytics go
   only through the consent-gated events allowlist.

The design rule behind all of it: a suggestion says why it is shown, applies nothing by itself, and
can be undone. Precision over recall (D5): a wrong "buy again" costs more trust than a missed one, so
every rule below leans to saying nothing.

## What is stored

One document, `localStorage["sc-personal-v1"]`, in the shape of the API's `PersonalData`
(`PUT /me/personal`), so the device copy and the account copy are the same thing:

| Field | Holds |
|---|---|
| `prefs` | `learn` (default on), `value_packs` (default off), `updated_at` (so the newer side wins a sync) |
| `refs` | the product references the trips name: canonical id, Hebrew and Arabic name, taxonomy id, base unit, category path. Only so a device that did not see the product can still draw "my usual" |
| `trips` | `{id, at, kind: "finished" \| "list", lines: [{canonical_id, quantity}]}` |
| `signals` | `{id, at, taxonomy_id, kind: "kept_brand" \| "rejected_substitute"}`: one per time, a category and nothing else |
| `dismissals` | `{kind: "buy_again" \| "brand_default" \| "value_pack", key, at}`, the latest per (kind, key) |

Never in it: a price, a store, a location, a list name, free text. Bounds, enforced on the device
(`personalDoc.ts` `normalizeDoc`) and again by the API: 40 trips of at most 60 lines, 200 references,
100 signals, 200 dismissals, nothing older than 400 days, 200 KB (the API refuses a body over 256 KB).

Where records come from (`features/personal/record.ts`), each a no-op while learning is off:

| Source | Records |
|---|---|
| "סיימתי" in store mode | the lines the person **ticked** as a `finished` trip. With nothing ticked, the plan's lines as a `list` (weaker: finishing without a tick is not proof of what was bought) |
| "נקי הכול" in the list builder | the recognized rows as a `list`, only for a list of at least 3 rows |
| keeping the original over a substitute, an undone swap, "exact" chosen by hand in the flexibility sheet | one `kept_brand` in the product's category |
| "not a good substitute", a dismissed swap | one `rejected_substitute` |

A `list` trip loses, in every calculation, the products a `finished` trip within 3 days already holds
(the person finished that list, then cleared it: one shop, not two); what is left of it, the products
that were not ticked, stays as the weaker evidence it is. Trips on one Israel calendar day count as one
shopping day.

## The rules (`habits.ts`, pure functions, unit tested with fixed dates)

| Feature | Rule (proposal) |
|---|---|
| Usual | on at least **3 shopping days**; ranked by days, then recency; at most 12; the quantity is the median taken (whole packs, halves of a kilo for a weight) |
| "You usually take N" | the same usual quantity, under the row; a one-tap "קבעי N" appears only when the row differs; it never changes the quantity by itself |
| Buy again | at least 3 shopping days; the **median gap** of the last 6 gaps is 3 to 90 days; **steady**: the median deviation of the gaps is at most 40% of the gap (at least 2 days) and no gap is over 3x the usual one; due when a gap has passed since the last purchase; given up after 3 more gaps; not suggested if already on the list; at most 5, most overdue first |
| Dismissing a buy again | hidden until the person buys it again, or one more gap from the dismissal; the status line offers an undo |
| Brand offer | **3 signals** in a category within 90 days; not offered when the category's default is already exact (the person's, or the smart default for toiletries, health, baby); after "no thanks" or an undo, needs 3 *new* signals; one offer at a time |
| Applying the offer | `setFlexDefault(category, "exact")`, the same call the flexibility sheet's "remember for all milk" makes; it does not touch rows already on the list; the undo restores exactly what the category had (a saved level, or none) |
| Value pack | see below; a dismissed pack is hidden for 30 days |

Everything above also needs learning on (Profile, "ללמוד מהקניות שלי"). Turning it off stops new
records and hides every suggestion; what was kept stays until "נקי את מה שנלמד".

## Large-family value packs

Pricing is untouched: this reads `/compare`. The API already chooses, per store and product, the
cheapest line **for the quantity asked** (`optimizer.md`, "Offers for the quantity asked"), so a pack
that is cheaper per unit but dearer in total (a tray of 30 eggs next to a 12-pack) appears only at a
bigger quantity. `valuePacks.ts` asks twice, for the list's quantities and for five times them (a
family stocking up), only for the rows that can have a larger pack (a resolved product counted in
units, not exact, not weighed), and reports a pack at the cheapest store for the current quantity when:

- both lines are exact or any-brand matches (never a substitute: nothing is swapped silently);
- the larger line is a different shelf item holding at least 25% more units (`pack_units`);
- its unit price (`effective_unit_price`, same unit) is at least 5% lower.

The card shows both unit prices, the pack sizes, the store, the time each price was updated and "המחיר
הקובע הוא בקופה". One tap raises the row's quantity to what covers one larger pack (1 to 2.5 for 30
eggs against 12), so the next `/compare` picks that pack by its own rule; the card says plainly that this
is more than was listed, and the change can be undone.

Limits, stated: it covers products counted in units (eggs, pitas, toilet paper), where one canonical
has several shelf packs at a comparable level. A larger bottle of milk is a different canonical and is
not offered here. It works on the offers of the cheapest store only. The 5x probe is a heuristic that
can miss a pack that wins only at another quantity. The mock (`mocks/packs.ts`) models eggs only.

## Where the data goes

- **Anonymous**: nowhere. `PersonalSync` makes no request without a session (a unit test and an e2e
  test assert zero `/me/` calls).
- **Signed in**: `PersonalSync` mirrors the document to `/me/personal` (`routes/personal.py`). On sign-in the
  two copies are merged (trips and signals by id, a dismissal at its latest time, the newer preferences
  win), the device keeps the union, and later changes are sent after an 800 ms pause. An empty document
  with default preferences is never created on the account. It is stored in `preferences.data ->
  'personal'`, a table that was already owner-only under forced row-level security and already removed
  by `DELETE /me`; there is no migration. The API never reads it for anything but its owner: not for
  ranking, not joined to another table, not exported, not sold.
- **Another device that still holds old data** merges it back on its next sign-in (a union cannot know
  something was cleared elsewhere). "Clear what was learned" removes it from this device and the
  account; another device clears its own copy from its own Profile.

## Controls and privacy

- Profile, "התאמה אישית": the two switches, what is kept (counts), where it is kept, and "נקי את מה
  שנלמד" (device, and account when signed in; a failed account clear says so).
- Export ("ייצוא הנתונים שלי"): `personalization` holds the whole document.
- "מחקי את הנתונים שלי": the account copy (`DELETE /me/personal`) first, then the device key
  (`sc-personal-v1` is in `CORE_DATA_KEYS`); if the server fails the device keeps its data so the person can
  retry. `DELETE /me` also removes it.
- `/privacy`: a short section (`PersonalPrivacySection`, copy in `i18n/messages/personal.ts`), marked
  "ממתין לבדיקה משפטית" like the rest of the page.
- Analytics: one event, `personalization {kind: usual | buy_again | brand_default | value_pack, action:
  shown | accepted | dismissed | undone}`, through `trackEvent` (so: beta build, real API, consent, no Do
  Not Track). No product, no category, no count, no date. `shown` is sent once per kind per page
  session. The API allowlist takes exactly those two keys (`test_api_personal.py`).
- No selling, no sponsored ranking: nothing here touches ranking, and the suggestions are computed
  from the person's own history on their own device.

## Accessibility and layout

Every card is a labelled region with an `h2`; every button has a name that includes the product
("הוסיפי קוטג' ... לקנות שוב", "לא עכשיו: ..."); one persistent `role="status"` line per area announces
what changed and carries the undo; focus moves to a neighbour or the list input when the focused button
leaves (`rescueFocus`); touch targets are 44 px; logical CSS properties only; the cards wrap at 195 px;
prices are `Price` (an LTR span with a non-breaking space) next to their `UpdatedAt`. Hebrew and Arabic
copy: `i18n/messages/personal.ts` (the Arabic is machine drafted and awaits a native-speaker review,
like the rest, #73).

## Code map

| Area | Files |
|---|---|
| Document, bounds, merge | `features/personal/personalDoc.ts`, `personalState.ts` (the store) |
| Rules | `habits.ts` (usual, buy again, brand offers), `valuePacks.ts` |
| Call sites | `record.ts`, hooks in `StoreMode.tsx`, `ListBuilder.tsx`, `substitution/actions.ts`, `swaps/actions.ts`, `FlexibilitySheet.tsx` |
| UI | `PersonalSuggestions.tsx`, `ValuePackSuggestions.tsx`, `UsualQuantityHint.tsx`, `PersonalSection.tsx` (Profile), `PersonalPrivacySection.tsx`, `StatusNote.tsx` |
| Account copy | `PersonalSync.tsx` (mounted in the core and secondary layouts), `api/client.ts` (`getPersonal`, `putPersonal`, `deletePersonal`) |
| API | `services/api/smartcart_api/routes/personal.py`, `schemas.py` (`PersonalData`), `routes/events.py` |
| Mocks | `mocks/handlers.personal.ts`, `mocks/packs.ts` |

## Tests

Unit (vitest): `personalDoc.test.ts`, `habits.test.ts`, `personalState.test.ts`, `valuePacks.test.ts`,
`PersonalSuggestions.test.tsx`, `ValuePackSuggestions.test.tsx`, `PersonalSync.test.tsx`,
`PersonalSection.test.tsx` (Profile, export, delete, privacy page), `brandSignals.test.tsx`,
`finishTrip.test.tsx`, `consent/personalizationEvents.test.ts`, `mocks/handlers.personal.test.ts`.
API: `services/api/tests/test_api_personal.py`. E2E: `tests/e2e/personal.spec.ts` (390, 1280 and 195 px).
A11y: `tests/a11y/personal.spec.ts` (axe in both themes at two widths, keyboard, four accessibility-tree
snapshots: `personal-suggestions`, `personal-value-pack`, `personal-usual-quantity`,
`personal-profile-section`).

## Open

- The thresholds (3 days, 90 days, 40%, 25%, 5%, 5x) are proposals; the beta's `personalization`
  events (accepted over shown, dismissed, undone) are what should tune them.
- Value packs beyond counted products, and across several stores, need the API to expose the offers it
  already keeps (`effective_offers`); this round did not change the API's pricing or its responses.
- A person who clears the account copy on one device and still has old data on another gets it back on
  the next sign-in there.
- The privacy paragraph and the Arabic copy have had no legal or native-speaker review.
