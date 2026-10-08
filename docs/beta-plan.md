# Closed beta plan and instrumentation

Issue #40, decisions D5 (precision over recall), D10 (trust), D11 (privacy). Roadmap: phase 1,
weeks 9 and 10 (the author's estimates for a solo developer), exit criterion "beta substitution
rejection rate low enough that trust holds".

Labels follow `docs/README.md`. **Every threshold and quota below is a proposal**: a number chosen to
be argued with, not a measured value and not a research fact. AC 1 of #40 requires the thresholds to be
fixed before recruiting starts: when the maintainer accepts or edits section 4, record the final numbers
in the pull request or here, and in `BETA_THRESHOLDS` (`services/catalog/smartcart_catalog/cli_seo.py`),
before the first invitation goes out.

**What exists today.** The `events` table and the metric views, `POST /events` with its allowlist and
rate limit, the client function `trackEvent`, the `beta-report` command, and this plan. **What does not
exist and needs people:** the beta itself (recruiting 20 to 50 users), the consent screen, and the calls to
`trackEvent` inside the screens (W4b and W5, section 5).

## 1. Goal and the gate

Decide, with data from real shopping lists, whether matching is good enough to launch. One wrong
substitution costs more trust than ten missed ones (D5), so the measure that gates the public launch is
the **substitution rejection rate** per flexibility level. Paste-to-results time and return visits are
tracked as signals and do not gate the launch. Public launch needs the rejection-rate gate met, or a
written decision to change the threshold (AC 6).

The 98% precision at "any brand" is a project **target**, not a result. The gold set is synthetic until
real labels exist (`matching.md`), so the beta is the first time the product meets real data.

## 2. Recruitment: 20 to 50 users

Segments with proven demand named in the research (`product-and-market.md`, Positioning and Market gaps;
`roadmap.md`, Growth plan): **large families**, **kosher-conscious shoppers** (the Haredi shoppers with
kosher filters in the research), **periphery residents**.

| Segment | Proposed definition | Proposed quota |
|---|---|---|
| Large families | household of five or more, the person who does the weekly shop | at least 8 |
| Kosher-conscious | keeps a kosher-supervision preference when shopping, uses kosher filters | at least 8 |
| Periphery | lives outside the Tel Aviv, Jerusalem and Haifa metropolitan areas | at least 8 |
| Anyone else | adult weekly shopper, any chain | up to 20 |

Total target **30 to 40**, hard limits **20 to 50** (issue). A user may count in more than one segment;
the report counts each segment separately. Aim for at least four different home chains among the
users, because the match quality differs by chain naming.

How: personal outreach and invitations, no paid acquisition (out of scope of #35 and #40). Community and
parents' groups, neighbourhood and municipal groups, the maintainer's contacts, and a short screening
form: segment, home chain, how the weekly shop is done, phone type (so both Android and iPhone get
tested), assistive technology (so some screen-reader users take part, see `a11y-report.md`). Invite
codes, one per person, so the count is exact. No payment: a small thank-you at the end, not tied to
usage, to avoid rewarding rejections or acceptances. Adults only.

Record in the beta report: invited, joined, active in week 1 and week 2, by segment.

## 3. Consent and privacy

First-party instrumentation only (D11): no third-party analytics or advertising SDK, no data leaves our
own database. Privacy law amendment 13 treats location and purchase data as sensitive, so we collect the
minimum.

**Collected.** Event names and fixed numeric or enumerated properties (section 5); a random session id
the browser makes; the signed-in user id when the person signed in; each "not a good substitute" answer
with the product pair it was about (the existing `substitution_feedback` row); the rounded
neighborhood location they chose to give in onboarding.

**Never collected by the beta instrumentation.** The text of lists or searches, names, addresses, phone
numbers, exact location, receipts, device identifiers. The API rejects any property that is not on the
allowlist, so this is enforced in code, not by promise (`routes/events.py`).

**Proposed consent text (Hebrew, shown once on joining, with an unchecked box).** Pending a legal review,
which has **not happened**:

> אני משתתפת בבטא סגורה של SmartCart. כדי לבדוק אם ההחלפות שהמערכת מציעה טובות, נשמרים אצלנו
> אירועי שימוש בסיסיים: מתי נפתחה האפליקציה, כמה זמן לקח להגיע לתוצאות, כמה החלפות הוצגו וכמה
> סימנתי כ&quot;לא תחליף טוב&quot; ועל איזה זוג מוצרים. לא נשמר תוכן הרשימה שלי ולא טקסט חופשי. המידע
> נשמר בשרתים של SmartCart בלבד, לא נמכר ולא מועבר לרשתות או לאחרים, ויימחק או יהפוך לסטטיסטיקה
> אנונימית עד שישה חודשים אחרי סוף הבטא. אפשר לצאת בכל רגע ולבקש למחוק את כל הנתונים שלי מהפרופיל.

Notes: the six-month retention is a proposal. "Delete my data" must also delete the user's `events` rows
(they hold `user_id`; deleting the account sets it to NULL, which leaves anonymous rows, and the
session-id rows of a signed-out person can be deleted by that id on request). Opting out in the app calls
`setTrackingConsent(false)` (stored in the browser, stops events at once); the browser's Do Not Track
signal also stops them.

## 4. Metrics, definitions and thresholds (proposals)

All three come from first-party events and are views in `20261007120000_events.sql`; `smartcart-catalog
beta-report` prints them with the verdicts.

| Metric | Definition | View | Proposed threshold |
|---|---|---|---|
| **Substitution rejection rate** (gates launch) | `not_good` verdicts divided by substitutions shown, per flexibility level. Shown = the sum of `count` in `substitutions_shown` events; rejected = `substitution_verdict` events with `verdict = not_good` | `beta_rejection_rate` (per week) | **exact at most 2%, any brand at most 5%, close at most 15%**, each judged only with at least **100 substitutions shown** at that level; fewer is "inconclusive, extend the beta" |
| **Paste-to-results time** (signal) | `duration_ms` of `results_shown`: from the paste to the results on screen (client clock) | `beta_paste_to_results` | median at most **5 s**, 90th percentile at most **10 s** (roadmap: "a few seconds"), with at least 30 results |
| **Return visits** (signal) | share of the week's active users (opened the app) whose first open was in an earlier week; actor is the user id, else the browser session id | `beta_return_visits` | at least **40%** in the last complete week |

Why these numbers (reasoning, not evidence). A user rejecting a substitution is not the same as the match
being wrong: a correct "any brand" match is sometimes rejected for taste. So the rejection threshold for
any brand (5%) sits above the 2% error the 98% precision target implies, to leave room for taste, and the
beta's job is to see how much room is needed. A close substitute is allowed to differ, so it gets a
wider limit. At exact level a substitution should not happen, so any rejection signals a bug. Sample size:
at 100 shown, a 5% rate has roughly a four to five point margin of error, which is why fewer than 100
is inconclusive and the report never calls a small sample a pass.

Also reported, no threshold: rejection rate per category (the existing `feedback.rejection_rates`, which
uses answers as its denominator, not impressions: the two differ and the beta report says which it
shows), segment split of the three metrics, accepted and kept-original counts.

Every rejected substitution is stored with context (`substitution_feedback`: user id if signed in,
canonical, original item, substitute item, time) and flagged for review (`item_canonical.needs_review`);
`beta_rejected_substitutions` lists them with names, the match's level and confidence, and whether a
human has reviewed since.

## 5. Instrumentation

```
browser ── trackEvent(name, props) ── batch every 2 s or on page hide ──► POST /events
                                                                          │ allowlist, rate limit,
                                                                          │ user id from the JWT
                                                                          ▼
                                       events table ── views ──► beta-report, weekly review
```

**Client.** `apps/web/src/features/seo/track.ts` exports `trackEvent`, `flushEvents`,
`setTrackingConsent`, `setAuthTokenProvider`, `getSessionId`. It lives in `features/seo` only because W6
does not own `src/lib`; W4b and W5 import it from there (or move it, with its test). Off unless the build
sets `NEXT_PUBLIC_BETA_EVENTS=1`; never active against the mock API; honors Do Not Track and opt-out; a
failed send is dropped, never retried, never thrown. Types come from the API contract, and a compile-time
check fails if the client and the API disagree on the event names.

**API.** `POST /events` takes `{"events": [{name, props, session_id}, ...]}`, 1 to 50 per request.
Event names and property keys are allowlisted (`EVENT_PROPS` in `routes/events.py`); a value is an integer
in a fixed range or a member of a fixed set, so there is no free-text property. Any violation rejects the
whole batch with 422 and nothing is stored. User id comes from a valid Supabase JWT, otherwise null (an
expired or bad token is treated as anonymous, so an event is not lost). Rate limit: 120 events per session
id per minute, counted in the table (proposal), 429 with `Retry-After`.

| Event | Props | Fire it | Used by |
|---|---|---|---|
| `app_opened` | `surface`: web or pwa | once per visit, in the shell (W5) | return visits |
| `page_viewed` | `page_type` | SEO pages (done) | SEO to app funnel |
| `list_pasted` | `item_count` | list builder, on paste (W4b) | drop-off before results |
| `results_shown` | `duration_ms`, `item_count`, `store_count` | results screen when rendered (W4b) | paste-to-results |
| `substitutions_shown` | `flex_level`, `count` | results screen, once per level that lists substitutions (W4b) | rejection rate denominator |
| `substitution_verdict` | `flex_level`, `verdict` | substitution card, with `POST /feedback/substitution` (W4b) | rejection rate numerator |
| `flex_changed` | `flex_level` | flexibility sheet (W4b) | which level people move to |
| `split_viewed` | none | split view (W5) | feature use |
| `gap_reported` | none | report-a-gap (W4b) | data trust |
| `pwa_installed` | `platform`: ios, android, desktop or other | `appinstalled`, or the first standalone launch, once per browser (finish round, #56) | PWA install rate |
| `push_opt_in` | `platform` | push permission becomes granted through the alerts button (#56) | push opt-in rate |
| `push_opened` | `platform` | a push notification is tapped; the service worker messages the page (#56) | notification open rate |
| `store_mode_used` | `plan`: single or split, `platform` | store mode opens with a shopping session (#56) | share of sessions in store; iOS versus Android split |

**Wiring is not done.** Of these only `page_viewed` is called today. W4b and W5 add the rest, then call
`setAuthTokenProvider(() => session.access_token)` after sign-in, and add the consent screen and the
opt-out switch in the profile (the profile is W5's). Until then the numerator and denominator of the
rejection rate do not exist; `substitution_feedback` still records every `not_good` answer.

**Storage and access.** Table `events (id, user_id, session_id, name, props jsonb, created_at)`; row-level
security on with no policy and no grants for the Supabase data-API roles, so nothing is readable from a
browser; the views use `security_invoker`. The API service connection writes; the maintainer reads. Weeks
in the views are Israel-time weeks starting Monday.

## 6. Weekly review loop

Every Monday during the beta (two to four weeks; length is a proposal):

1. **Measure.** `uv run smartcart-catalog beta-report --since <beta start> --out docs/reports/beta-<date>.md`
   and read the weekly views (`SELECT * FROM beta_rejection_rate;` and the others).
2. **Triage rejections.** `smartcart-catalog review` opens the review queue; rejected pairs arrive first,
   with a feedback marker. For each cluster decide: wrong critical-attribute rule (fix `product_type_rules`),
   wrong attribute extraction (fix the extractor or its keywords), wrong canonical definition, a data issue
   (check `gap_reports`), or taste (no fix; maybe a smarter default flexibility). A human decision in the
   review UI changes the mapping; a report alone never does.
3. **Label.** Confirm or overturn `feedback.feedback_gold_candidates` so rejected pairs become real
   `no_match` gold pairs (the first real labels), and add confirmed good ones.
4. **Fix and re-measure.** Make the fix with a test, run `smartcart-catalog evaluate --fail-below 0.98`,
   deploy, and compare next week's rejection rate for the same category.
5. **Record** in the beta report: what was seen, what was fixed, what was not, and the decision for the next
   week (continue, recruit more to reach 100 shown at a level, change a threshold with the reason).
6. **Check on people.** Count active users per segment; reach out to a segment that is going quiet.

**End of beta.** The report states: users recruited per segment, the three metrics against the
thresholds, whether the rejection-rate gate was met at every level, what was fixed, and the launch
decision (launch, extend, or change a threshold with the reason written down). Indexing status of the SEO
pages (issue #35) goes in the same report.

## 7. Acceptance criteria of #40 against this plan

| Criterion | Status |
|---|---|
| Numeric threshold per flexibility level documented before recruiting | Proposed (section 4); needs the maintainer's confirmation |
| 20 to 50 users recruited across the segments | Not done: needs people; plan in section 2 |
| Dashboard or report shows the three metrics | Views and `beta-report` exist and are tested on seeded events; nothing real to show yet |
| Every rejected substitution stored with context and reviewed in the review UI | Storage and queue exist (`substitution_feedback`, `needs_review`); review happens during the beta |
| Beta report states whether the threshold was met and what was fixed | Template in `beta-report`; written at the end |
| Public launch gated on the threshold | Rule in section 1 |

## 8. Native-decision views (#56)

The events already collected answer the native-app question (decision D15, `decisions.md`) through six
more views, migration `20261011100300_retention.sql`. Like the beta views they are over `events`, use
Israel-time weeks starting Monday and `security_invoker`, and are not readable through the Supabase data
API. `smartcart-catalog native-report` prints them with their sample sizes and the D15 criteria.

| View | One row per | Answers |
|---|---|---|
| `native_events` | event | the five events below with week, day and actor (`app_opened`, `pwa_installed`, `push_opt_in`, `push_opened`, `store_mode_used`) |
| `native_cohort_retention` | cohort week (first `app_opened`) | cohort size and D1, D7, D30: eligible, retained, rate. Dn counts an actor only once day n is over; a rate is NULL, not 0, with no eligible actor |
| `native_installs_by_platform` | week and platform | `pwa_installed` events, distinct installers, active users that week |
| `native_push_engagement` | week | active users, push opt-in users and rate, pushes sent (`alert_deliveries.channel = 'push'`), `push_opened`, open rate |
| `native_store_mode_usage` | week | active users, store-mode users and share, opens by plan, opens per store-mode user (weeks with no use are listed with 0) |
| `native_platform_funnel` | platform (all time) | actors seen on a platform-tagged event, installers, push opt-ins and opens, store-mode users, share who never installed |

Limits (the report repeats them): an actor is a user id or a browser session id, so retention is a lower
bound and an installed iOS PWA is a separate actor from the Safari tab; `app_opened` has no platform, so
platform shares are among actors who fired a tagged event; there is no "push prompt shown" event, so
opt-in is a floor; opens are client-reported. No event carries an id, a name, a price or free text.
