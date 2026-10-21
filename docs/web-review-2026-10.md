# Web app review, October 2026

A correctness bug hunt in `apps/web`, looking for defects a beta user would hit, not style. Each
defect below was reproduced (a test that failed before the fix and passes after it), fixed in the
style of the surrounding code, and left with that test. Nothing here is an estimate: the counts are
test counts, and the "how to reproduce" lines are what the tests do.

Scope: state and persistence (`src/state`, `features/profile`, `features/budget`, `features/store`),
sync and offline (`ProfileSync`, spend sync, the shared list and its offline queue, auth), async
steps that outlive a cancel (voice, recipe, photo, scan, location, list builder), money and numbers,
i18n and RTL, and keyboard focus. Not touched, as agreed: the results-screen substitutions list,
`features/swaps`, `features/substitution`, `next.config.*`, the generated API types, Python.

## Defects found and fixed

### State and persistence

| # | Defect | How to reproduce | Fix | Test |
|---|---|---|---|---|
| 1 | A write that storage refuses (quota, some private windows) was kept "in memory" only in name: the next read went back to storage and found the old value. Onboarding answers, the shopper context behind every comparison, the in-store checklist, spend entries and realized savings all vanished at once. | Make `Storage.setItem` throw, save a location in onboarding, open Results: the default city is used. Same for "סיימתי" recording a shop. | `state/storage.ts` keeps a refused write in memory (`readRaw`/`writeRaw`) until another tab changes the key; `profileState`, `shopper`, `spendState`, `savingsHistory` and `store/session` read through it. | `state/storage.test.ts`, `store/session.storage.test.ts`, `profile/savingsHistory.test.ts`, `budget.test.ts` ("storage blocked" now says kept for this page view) |
| 2 | `sc-profile-v1` holding a string, an array, `NaN` or an out-of-range coordinate was spread into the next write or became the search centre; a negative `cost_per_km` made travel a saving. | Put `"abc"` or `{"cost_per_km":"-3"}` in the key and save anything. | `shopperFromStored` and `saveShopperProfile` accept only a plain object, finite in-range coordinates, non-negative costs, integer store ids. | `state/storage.test.ts` |
| 3 | A list row whose `canonical` was not a product (hand-edited or old data) reached `/optimize` with `canonical_id: undefined`; another tab's `localStorage.clear()` (a `storage` event with no key) was ignored. | Edit `sc-list-v1`; clear storage in a second tab. | `sanitizeItem` validates the canonical and the candidates; the list store follows a keyless event. | `state/list.storage.test.ts` |
| 4 | The keyed async cache let a slow older response overwrite a newer one after a retry, and let a response arrive after `clear()`. | Reload a key while the first request is slow. | A per-key request token. | `state/resource.test.ts` |
| 5 | A stored in-store session or savings history with one damaged entry crashed the checklist or the total (`null.net`, `null.checked`). | Put `[null]` in `sc-savings-history`. | `sanitizeSession` and the savings reader drop what they cannot draw. | `store/session.storage.test.ts`, `profile/savingsHistory.test.ts` |
| 6 | Switching language in one tab changed the copy in a second tab but not its `<html lang>` (screen reader voice, font stack). | Two tabs, switch in one. | `LocaleProvider` applies the stored locale to `<html>` when the locale changes, reading storage again so the Hebrew hydration pass never overwrites it. | `i18n/LocaleProvider.test.tsx` |
| 7 | "Delete my data" left the shared-list registry, the queued shared-list edits (they hold item names), remembered alert names, scan counters, the picked scan store, dismissed swaps and the analytics session id. The in-memory queue was also written back by the next edit. | Queue an edit offline, delete the data, edit again. | The keys are in `CORE_DATA_KEYS`; the queue listens for storage events. | `share/offlineQueue.tabs.test.ts` |
| 8 | The offline queue kept one in-memory copy per tab and never reread it: two tabs replayed the same edit, or one tab's write erased the other's. | Two tabs of one shared list. | The queue rereads on a `storage` event for its key. | `share/offlineQueue.tabs.test.ts` |

### Sync, offline, retries

| # | Defect | How to reproduce | Fix | Test |
|---|---|---|---|---|
| 9 | A shop deleted while its `POST /me/spend` was in flight reappeared after the next pull (the account kept it); a total corrected during the POST never reached the account. | Delete or correct a pending entry while the request is slow. | After the POST, `pushPendingSpend` deletes (and remembers not to merge back) or `PUT`s the corrected total. | `budget/sync.race.test.ts` |
| 10 | A shared-list poll that started before an edit and ended after it put the old list back on screen (the tick disappeared). | Poll in flight, tick an item, answer the poll last. | `useSharedList.load` ignores an answer older than the last edit. | `share/sharedList.race.test.tsx` |
| 11 | Signing out while the first profile upload was still in flight marked the next sign-in as loaded, so its first local change was pushed over the account's stored profile before that was read. | Hang the first `PUT /me/profile`, sign out and in. | `ProfileSync` ignores a finished attempt that was cancelled. | `profile/ProfileSync.race.test.tsx` |
| 12 | If the Supabase chunk failed to load (offline, flaky link), `AuthProvider` stayed `loading` for ever (shared list, alerts and profile sync all wait on it), the rejected promise was cached for the whole session, and the sign-in sheet stayed busy. | Make the dynamic import reject once. | The failure is forgotten, the provider falls back to signed out, the sheet catches and reports, ignores a second Enter, and reads Arabic-Indic digits in the code. | `auth/auth.loadfail.test.tsx`, `auth/supabaseClient.test.ts` |
| 13 | Events queued before the person withdrew consent in another tab were still sent. | Decline in tab B with events queued in tab A. | `flushEvents` rechecks consent and drops the queue. | `seo/track.test.ts` |
| 14 | If the server refused a new push subscription the browser subscription stayed, so the panel read "notifications on" for a device the server never heard of. | `POST /me/push-subscriptions` returns 500. | The subscription made in this call is dropped again; an older one is kept. | `alerts/push.test.ts` |
| 15 | No request timeout: on a connection that hangs, every spinner (list parsing, results, shared list) stayed for ever and a shared-list edit was neither queued nor rolled back. | A request that never answers. | `api` aborts after 60 s (combined with the caller's own signal); a `TimeoutError` counts as a lost connection for the offline queue. | `api/client.test.ts`, `share/offlineQueue.test.ts` |

### Async steps that keep running after cancel or unmount

The same pattern as the photo cancel race, found in six more places. Each used a request or an
answer token that the cancel, close, navigation or unmount invalidates.

| # | Where | What happened | Test |
|---|---|---|---|
| 16 | `RecipeSheet` | Cancel while the recipe is read: the answer filled the closed sheet, which then reopened with it and a stuck "קוראים...". | `recipe/recipe.cancel.test.tsx` |
| 17 | `VoiceSheet` + `ListBuilder` | Closing the dictation sheet while the list is parsed still added the rows. | `voice/voice.test.tsx`, `list/ListBuilder.race.test.tsx` |
| 18 | `PhotoSheet.add` | Closing while an edited line is re-parsed still added the rows. | `photo/photo.test.tsx` |
| 19 | `ScanScreen` | "עצירת המצלמה" or leaving the page while the permission prompt is open: the camera came on afterwards and was never released. A slow lookup replaced the result of a newer one. | `scan/ScanScreen.race.test.tsx` |
| 20 | `LocationControls` | A position that arrived after the step was skipped, or the location removed, was stored together with the location consent. | `profile/controls/LocationControls.race.test.tsx` |
| 21 | `ListBuilder` | Typing the next item while the first was parsed: the box was cleared and the new text lost. | `list/ListBuilder.race.test.tsx` |

### Double submits

| # | Where | What happened | Test |
|---|---|---|---|
| 22 | `StoreMode.finish` | A double tap on "סיימתי לקנות" recorded the shop twice (savings history and budget). | `budget/budgetUi.test.tsx` |
| 23 | `AlertsScreen` | A double tap on delete sent two requests and showed the second one's 404 as a server error; pause could toggle back. | `alerts/alertsManage.test.tsx` |

### Money and numbers

| # | Defect | Fix | Test |
|---|---|---|---|
| 24 | Amounts typed with an Arabic keyboard (٩٫٩٠) were "invalid" or silently dropped: alert threshold, corrected spend total, monthly budget, the price at the shelf in both report-a-gap forms and on the scan card. | `lib/numberInput.ts` (`normalizeNumberInput`) in every parser; the budget also takes `2,500`, and its field is a text input with a numeric keypad (a `type="number"` field drops Arabic digits and commas before the app sees them). | `lib/numberInput.test.ts` |
| 25 | The price in the history tooltip and in the history table was plain text in an RTL paragraph, so the shekel sign rendered after the digits. | `Price` (an LTR island). | `history/PriceHistory.test.tsx` |
| 26 | The price in a push notification had the same problem (no markup there). | LTR isolate marks around the price in `public/sw.js`. | `alerts/sw.test.ts` |
| 27 | Map pin and store-row labels, and the split move announcement, wrote `₪` without the no-break space, and the announcement printed a negative net as `₪-3.50`. | `formatPrice`. | `tests/a11y/aria-snapshots/split-view-moved.aria.yml` updated |
| 28 | The basket estimate summed floats per store. | Whole agorot per line, like the split. | no change in `state/comparison.test.ts` |

### i18n and RTL

| # | Defect | Fix | Test |
|---|---|---|---|
| 29 | A shared-list row without a name was given a Hebrew placeholder in the data (`מוצר מס' 12`, `פריט`), shown in Arabic and written back to the server as `input_text`. | The name stays as stored; `sharedItemName` translates the fallback (`itemNumbered`, `itemUnnamed`, he and ar). | `share/listSync.test.ts` |

### Keyboard focus and announcements

| # | Defect | Fix | Test |
|---|---|---|---|
| 30 | Removing a list row, answering the amber question, clearing the list, deleting an alert, a shared item or a spend entry, closing the correction form, and leaving the beta destroyed the focused button: focus fell to the top of the page. | `lib/focus.ts` (`rescueFocus`) moves focus to the next row, or to the page's `[data-focus-fallback]` element (the typing box, the empty-state heading). | `list/ListBuilder.focus.test.tsx`, `alerts/alertsManage.test.tsx`, `beta/beta.test.tsx` |
| 31 | Onboarding's next and back replaced the card under the pressed button and said nothing. | Focus goes to the step heading (not on first render). | `onboarding/OnboardingFlow.test.tsx` |
| 32 | The results skeleton and the cards replaced each other silently. | A visually hidden `role="status"` says "טוען תוצאות", then "התוצאות מוכנות" (he and ar). | `results.aria.yml` snapshot |

## Checked and found fine

- `readJson`/`writeJson` and every direct `localStorage` use survive a throwing accessor, garbage JSON
  and SSR (list, flex defaults, theme, locale, profile, budget, spend, scan, alerts, swaps, consent).
- The `sc-locale` cookie and localStorage agree: the cookie wins, both are written together, a bad
  value reads as Hebrew, and `LOCALE_INIT_SCRIPT` sets `lang` before first paint.
- Spend `client_id` idempotency: one id per entry, kept for every retry, adopted on a lost response,
  and a pull inside the undo window does not bring a deleted entry back.
- Shared list: Realtime and polling merge by item and arrival order, offline edits coalesce, a
  server refusal rolls back and a lost connection queues.
- `ProfileSync` budget handling (`monthly_budget` only when changed), theme and flexibility defaults.
- Handoff (HTTPS-only links, no fetch from the chain), voice recognizer lifecycle (late events are
  detached), photo cancel (already fixed), onboarding nearest-store (guarded by the chain it asked for),
  product detail (stale requests dropped by key), `BottomSheet` focus trap and return.
- No physical `left`/`right` in CSS, TSX inline styles or style props; no hard-coded Hebrew or Arabic
  in components outside the message modules except `listSync` (fixed, #29) and the deliberate Hebrew
  barcode label sent to the review team; he/ar key parity is enforced by `messages.catalog.test.ts`.
- Every visible price goes through `Price` (an LTR island); `formatPrice` uses Latin digits in both
  locales.

## Found, not fixed

- Adding a scanned product twice adds up (by design, "adding the same product again adds up"); the
  card says "נוסף" but stays tappable.
- `aria-label`s on map pins and store rows read the price without a currency word; not a visual issue.
- `adoptNearestHomeStore` (`features/profile/profileState.ts`) reads the shopper's location before
  `GET /stores/nearest` and did not compare it with the location after the answer, so a location
  changed in between could keep the home store of the old location. **Fixed** in the "Follow-up of
  the follow-ups" section below (#39).
- The polling fallback of the shared list is last-write-wins for the whole list. It needs an API
  change, so it is a proposal, not a fix: see "Proposal: per-item writes for the shared list in
  polling mode" below.

## Follow-up round: the first three "found, not fixed" items and the other async flows

### Fixed

| # | Where | What happened | Fix | Test |
|---|---|---|---|---|
| 33 | `features/swaps/swapState.ts` | "Delete my data" (this tab, or another tab, or `localStorage.clear()`) left the in-memory snapshot of `sc-swaps-v1`; the next dismissal wrote the deleted dismissals back. A screen showing the dismissals did not update either. | The store rereads on a `storage` event for its key or without a key (the delete path already sends one for every `CORE_DATA_KEYS` key, also in the tab that ran it) and tells its subscribers. | `swaps/swaps.tabs.test.ts` (6 tests; 5 fail without the fix) |
| 34 | `features/share/useSharedList.ts` `flush`, `offlineQueue.ts` | Realtime mode: an item added offline and ticked offline is two queued edits, the "add" under a negative placeholder id and a "checked" for that id. The real id was only kept in a local map of the running replay, so when the link dropped between the two writes the retry sent the tick for the placeholder id, matched no row and dropped it: the tick was lost. A tick made while the add was being sent had the same problem. | New `completeAdd(listId, placeholder, realId)` removes the sent "add" and renames the waiting edits of that item to the real id in one write (so it also survives a reload); the replay then puts the saved row in place of the draft on screen. | `share/sharedList.addedOffline.test.tsx` (fails without the fix), `share/offlineQueue.test.ts` ("an item added offline that reached the server", 2 tests) |
| 35 | `features/alerts/AlertMe.tsx` | The first read of the list could end after a create or a delete: it dropped the alert just created from the screen, or brought a deleted one back. A double tap on "delete" sent two requests and showed the second one's 404 as a server error (the same bug `AlertsScreen` had, #23). | The form remembers what it created and deleted and applies it to a late answer; one delete per alert at a time; one create at a time. `ProductDetail` gives the form `key={canonicalId}`, and the product route keys the page the same way, so nothing of one product carries into the next. | `alerts/alerts.race.test.tsx` (3 tests) |
| 36 | `features/alerts/AlertsScreen.tsx`, `EditAlertSheet.tsx` | A save in the edit sheet that ended after the person closed it and opened the sheet of another alert closed that second sheet. | `onSaved` closes only the sheet of the alert that was saved; the sheet ignores a second submit while one is on its way. | `alerts/alerts.race.test.tsx` ("a save that ends after the person opened another alert's sheet") |
| 37 | `features/beta/BetaJoin.tsx`, `betaState.ts` | Joining or leaving the beta while signing out: the answer of the old session was written into the shared membership after `resetBetaState`, so the next sign-in read "ready, member" (or "left") without asking the API. | `setBetaMembership` takes the generation the step started in (`betaGeneration()`); a reset in between makes the answer stale and it is dropped. | `beta/beta.race.test.tsx` (2 tests fail without the fix) |
| 38 | `features/handoff/HandoffAction.tsx` | Two taps on "copy" where the first (a permission prompt) ended last: "copied" turned into "failed". | The latest tap's result is the one shown. | `handoff/HandoffAction.test.tsx` ("shows the answer of the latest tap on copy when an earlier one ends last") |

For #33 to #38 the fix was reverted and the new tests were seen to fail. The ones that still pass
without the fix are the controls: "ignores the storage events of other keys" (swaps), "still
records the answer when nothing changed meanwhile" (beta), and the `completeAdd` unit tests (the
function is new).

### Checked and found fine

- Product detail: the `compare` and `search` request is cancelled when the product changes, and the
  answer is tagged with its request key, so a late answer for the previous product is ignored. Now
  pinned by a test (`product/ProductDetail.test.tsx`, "ignores the answer of the previous product's
  request ..."). There is no promo-cycle fetch in the web app: `/promo-cycles/{canonical_id}` is in
  the generated API types and nothing calls it.
- The map screen has no fetch of its own. Its data is `useComparison`, which reads the keyed
  resource cache (a request token per key, #4); the map library is a dynamic import whose
  animation-frame callback is cancelled on unmount. The nearest-store lookup is the profile one
  above (`adoptNearestHomeStore`).
- Handoff share: `navigator.share` rejections (cancel, a second share while one is open) are caught.
  Beta join: the button is disabled while joining and the consent sheet closes on the first answer,
  so there is no second request. Push panel: its buttons are disabled while a request runs, and the
  panel renders nothing until its first read has finished.

### Proposal: per-item writes for the shared list in polling mode

Status: **done** (see "Implemented" at the end of this section). The text below is the proposal as it was written, kept for the reasoning.

What the polling fallback does today (`useSharedList`, mode "polling": no Supabase client, that is
the mock and local development, never a signed-in production session): an edit sends the whole list
with `PUT /me/lists/{id}`, built from the items on screen at the last poll (every 4 s). Two people
who edit within one poll interval overwrite each other's change.

Why the existing API cannot fix it from the client:

1. `PUT /me/lists/{id}` replaces the item set (`services/api/smartcart_api/routes/me.py`,
   `_write_items`: `DELETE FROM list_items WHERE list_id = ...`, then one `INSERT` per item). Every
   PUT gives every item a new id, so after another person's PUT the ids this client holds name
   nothing, and "merge by item id" matches nothing. Matching by `canonical_id` and name would merge
   two rows of the same product wrongly.
2. `ListItem` has no `updated_at` (the `list_items` table has no such column either; only `lists`
   has one), so "newest edit wins per item" has nothing to compare.
3. There is no precondition on the PUT (no `If-Match`, no revision).
4. `PUT` is owner-only (`WHERE id = %s AND user_id = %s`). An editor gets 404, so in polling mode only
   the owner can save at all; editors work through PostgREST, which is the realtime path.
5. A client-side read, apply, write (`GET`, apply this person's edit, `PUT`) would shrink the window
   from 4 s to one round trip, but not close it, and it would have to match items by content.
   Rejected as a half fix that hides the bug.

Proposal, in two steps:

1. Per-item routes on the API, all editor-or-owner, one SQL statement each:
   `POST /me/lists/{id}/items` (body `ListItemIn`, answers the `ListItem`),
   `PATCH /me/lists/{id}/items/{item_id}` (any of `quantity`, `checked`, `flex_level`, `confirmed`;
   answers the `ListItem`; 404 if the item is gone) and `DELETE /me/lists/{id}/items/{item_id}`.
   Add `list_items.updated_at` (default `now()`, `set_updated_at` trigger like `lists`) and return it
   as `ListItem.updated_at`. Two people changing different items then never conflict, and on the same
   item the later write wins per field, which is what realtime mode does.
2. Keep `PUT` for "replace the list" (the owner's save, import), but make it keep ids: items that
   carry an `id` are updated, the others inserted, the missing ones deleted. Optionally accept
   `base_updated_at` and answer 409 with the current list when the list moved on.

Web follow-up once the routes exist (small, the pieces are there): polling-mode `edit` and `flush`
call the same per-edit write as `writeRealtime` does against the routes instead of `PUT`, with the
same optimistic update, queue and rollback; the poll merges with `applyChange` by id and
`updatedAt` (it already skips an older row); `completeAdd` (above) covers placeholder ids the same
way. Tests: two clients editing different items within one poll keep both; the same item keeps the
later; an edit queued offline replays per item.

#### Implemented

API (`docs/api.md`, "Per-item writes"): `POST /me/lists/{id}/items`, `PATCH` and `DELETE
/me/lists/{id}/items/{item_id}` for the owner and accepted editors (viewer 403, stranger 404, the
item must belong to the list in the path), `list_items.updated_at` kept by a trigger (migration
`20261022090000_list_items_updated_at.sql`), an `expected_updated_at` precondition (body field of
PATCH, query parameter of DELETE) that answers 409 with the current row, an id-stable `PUT`, and
`PATCH` in the CORS methods. Two departures from the proposal: the precondition is a field, not
`If-Unmodified-Since` (one-second resolution), and `PUT` has no `base_updated_at` (the web app no
longer uses it for edits, and a whole-list replace cannot merge anyway).

Web (`features/share`): in polling mode every edit is applied on screen, queued with what the
person saw (`base`, the item's version, and `from`, the value of the field), and written by the
flush as one per-item call (`itemWrites.ts`); online and offline edits take the same path, in
order, and an add that reached the server renames the waiting edits to the real id and the saved
row's version (`completeAdd`). Realtime mode is unchanged.

Merge rule on 409 (`mergeVerdict`), per item and per field, never for the list; the server row is
always what the screen shows afterwards:

| The person's edit | The item now | Result |
|---|---|---|
| tick / quantity | already has the value they wanted | nothing to do, no note |
| tick / quantity | the field is still what they saw; another field changed | sent again on the current version, both changes stay, no note |
| tick / quantity | the same field has another value | the other person's value stays; the edit is dropped with a quiet note (`msgSuperseded`, he and ar) |
| remove | changed by somebody since | the item stays, same note |
| remove | already gone (404) | done |
| tick / quantity | gone (404) | the row leaves the screen, same note |
| any | keeps changing for 3 rounds | dropped, same note |

Tests: `services/api/tests/test_api_list_items.py` (29: every route for owner, editor, viewer and
stranger, IDOR, 409 on PATCH and DELETE, millisecond matching, the trigger, size cap, id-stable
PUT), `test_api_security_data_api.py` (a version cannot be forged through PostgREST),
`itemWrites.test.ts`, `sharedList.concurrent.test.tsx` (two editors within one poll, 409 merge,
offline replay), `offlineQueue.test.ts`, `mocks/handlers.lists.test.ts`, and the e2e spec
`phase2-share-swaps` ("two devices editing within one poll interval").

Both gaps that stood here ("an add whose response is lost is sent again and can create the item
twice", "the list's own `updated_at` does not move when an item changes") are closed: see
"Follow-up of the follow-ups" below (#39, #40).

## Follow-up of the follow-ups: idempotent add, the list's own `updated_at`, the home store

| # | Where | What happened | Fix | Test |
|---|---|---|---|---|
| 39 | `features/profile/profileState.ts` `adoptNearestHomeStore`, `useResolveHomeStore` | The location was read before `GET /stores/nearest` and not compared with the location after the answer. A location changed while the request was in flight (a new city typed, the device fix arriving, "clear location") gave the profile the home store of the old place, and the baseline of the net saving was a store the shopper is not near. | After the answer the location is read again and compared with the one the request was made for (it is stored rounded to the neighborhood, so equal coordinates are the same question); a different one drops the answer, like the chain guard next to it. The hook that resolves the store once per chain now does so once per chain and location, so a dropped answer is asked again for the new place. | `profile/homeStore.test.tsx` (3 tests fail without the guard: the location changed meanwhile, cleared meanwhile, and the hook asking again; the controls: the same neighborhood set again still adopts) |
| 40 | `POST /me/lists/{id}/items`, `features/share/offlineQueue.ts`, `itemWrites.ts`, `useSharedList.ts` | An add whose response was lost (the server saved the item, the browser saw a network error) stayed in the offline queue and was sent again: the list had the item twice. Realtime mode's insert had the same hole. | `list_items.client_id` (migration `20261023090000_list_items_client_id_touch.sql`), unique per list; the queue makes a uuid per add (`state/clientId.ts`), keeps it with the queued add across reloads and sends it with every attempt; the API answers a repeat with the stored row (200, not 201). Realtime mode sends the key and, on the unique violation (`23505`), reads the stored row instead of treating it as a refusal. | `share/sharedList.addReplay.test.tsx` (the first answer is lost, the queue sends again, one item; fails without the key), `sharedList.addReplay.realtime.test.tsx`, `itemWrites.test.ts`, `offlineQueue.clientId.test.ts`, `mocks/handlers.listIdempotency.test.ts`, and on the API `test_api_list_item_idempotency.py` (11) |
| 41 | `lists.updated_at` | An item change did not move the parent list's `updated_at`, so the list somebody just edited kept its old place in `GET /me/lists` (ordered by it) and any "updated" label. | An `AFTER INSERT OR UPDATE OR DELETE` trigger on `list_items` sets `lists.updated_at = now()` (`SECURITY DEFINER`: an editor may write items and has no privilege on `lists`; its `search_path` is the migration's schema). An UPDATE that changes nothing leaves it. The web app reads no list-level `updated_at` (it orders by what the API returns and labels items, not lists), so nothing there needed to change; the mock now moves it the same way. | `test_api_list_updated_at.py` (9: owner and editor, no-op, ordering, move between lists, cascade delete), `test_api_security_data_api.py` (an editor through PostgREST), `services/ingest/tests/test_db.py` (the trigger follows the migration's schema, not `public`), `mocks/handlers.listIdempotency.test.ts` |

Not done: a replay after the item was deleted is a new add (the key identifies a live item). The
web app removes a queued add together with its key when the item is removed before it was sent, so
that case does not arise from the queue.

## Verification

| Check | Result |
|---|---|
| `npm run lint`, `npm run typecheck`, `prettier --check` | clean |
| `CI=true npx vitest run` | 116 files, 1277 tests, all pass (before the review: 98 files) |
| `npm run build` | passes |
| `npm run e2e` (Chromium, production build) | 308 passed |
| `npm run a11y` | 375 passed; the two aria snapshots that changed on purpose were updated by hand (`results`: the new status line; `split-view-moved`: the announcement price). The other snapshots are unchanged. |

Every fix above has a test. For the recipe, scan, shared-list poll, profile-sync, store-mode double
tap and photo add fixes the change was reverted and the test was seen to fail; the others assert the
old broken behavior directly (for example a read after a refused write) but were not reverted one by
one.

Follow-up round (#33 to #38): `npm run lint`, `typecheck` and `prettier --check` clean;
`CI=true npx vitest run` 122 files, 1313 tests, all pass; `npm run build` passes; Playwright e2e on
the production build for the share, swaps, alerts, beta, handoff and follow-up specs (49 passed) and
`aria-flows` (9 passed).

Follow-up of the follow-ups (#39 to #41): `npm run lint`, `typecheck`, `prettier --check` clean;
`CI=true npx vitest run` 130 files, 1378 tests, all pass; `npm run build` passes; Playwright e2e on
the production build for `phase2-share-swaps`, `followups`, `secondary-onboarding-profile` and
`secondary-split-map-store` (47 passed). Python: `pytest services/api services/catalog
services/ingest/tests/test_db.py` 2708 passed, 8 skipped (the API role tests that need a grant on
the `auth` schema, and the SEO regeneration). For #39 and #40 the fix was reverted and the new
tests were seen to fail (#39: 3 of the 4 new tests; the fourth is the control that the same
neighborhood still adopts).
