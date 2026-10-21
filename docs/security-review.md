# Security review of the API and the web app (before the closed beta)

A defensive review of our own code, done in October 2026 before real users arrive: authentication,
authorization, input limits, abuse, leakage and headers, with a fix and a regression test for each
defect that was clear, and a write-up here for what is a design decision. Nothing was weakened: every
existing check stayed, the full API suite (1,280 tests at the end, 794 before), the web unit tests, the
315 end-to-end tests and the 375 accessibility tests pass on the production build with the new CSP.

What was reviewed: `services/api/smartcart_api` (auth, every route, schemas, the recipe fetch, the push
sender), `supabase/migrations` (every table's policies and grants), `apps/web` (next config, service
worker, the Supabase client, what the app sends to which origin). Not reviewed: Supabase's own
services, the VPS and Caddy configuration beyond what the API assumes of them, the ingestion workers,
and anything that needs the real project (there is none yet).

How things were checked: by reading, then by trying to break each assumption in a test (a stranger, a
member, an anonymous caller, a forged token, a hostile string), and the database facts were read from a
`supabase/postgres:17` container with Supabase's stock roles and default privileges (the CI image), not
from the migration comments. Rate limits and caps below are proposals (estimates), not measured
against real traffic.

## Findings

Severity is the worst plausible outcome for a beta with real users: High is another person's data or
the catalog changed by a stranger; Medium is a way to cost money, take the service down, or make it
return a 500 or a wrong answer on purpose; Low is hardening.

| ID | Severity | Finding | Status |
|---|---|---|---|
| S1 | High | A signed-in user could give themselves access to anybody's list through the data API (`list_shares` policy) | fixed |
| S2 | High | `anon` and `authenticated` could read and write every table without row-level security: prices, catalog, gap reports | fixed |
| S3 | Medium | A push endpoint is a URL the server posts to from inside our network (SSRF) | fixed |
| S4 | Medium | The recipe fetch could be rebound by DNS, accepted special-purpose addresses, and could be inflated by compression | fixed |
| S5 | Medium | Bad input produced a 500: a `NaN` token, a lone surrogate, a NUL, a missing foreign key, a huge id | fixed |
| S6 | Medium | No request body limit; a 4000-character list was 2000 lookups; unbounded numbers and collections | fixed |
| S7 | Medium | No rate limit on the costly routes; the events limit could be bypassed with random session ids; invite-code guessing | fixed |
| S8 | Medium | The API role could not serve the beta and photo routes (grants missing): a 500 in production only | fixed |
| S9 | Low | JWT checks: the verifier's message was echoed, no clock-skew tolerance, role only half-checked, no issuer pin, e-mail passed into the database session | fixed |
| S10 | Low | The access log recorded the caller's exact coordinates for two GET routes | fixed |
| S11 | Low | Free text could carry terminal escape sequences and bidi overrides to whoever reads it later | fixed |
| S12 | Low | No per-user caps (lists, devices, invites, spend entries); no hardening headers on the API | fixed |
| W1 | Medium | The web app sent no security headers at all (no CSP, HSTS, frame-ancestors, referrer or permissions policy) | fixed |
| W2 | Low | The production bundle contained the MSW library and every mock handler as lazy chunks, off only at run time | fixed |
| R1 | Medium | One anonymous request can pull a product match out of the price run (`not_good` feedback) | open |
| R2 | Medium | The session token lives in `localStorage` and the CSP still needs `'unsafe-inline'` for scripts | open |
| R3 | Low | Limits are counted per process and per address | open |
| R4 | Low | `/parse-image` is anonymous; its monthly cap is global | open |
| R5 | Low | HS256 shared secret instead of Supabase's asymmetric signing keys | open |
| R6 | Low | A location is stored without consent when written through the data API, if it is ever opened for profiles | open |

### S1. Anybody could read and edit anybody's list (High, fixed)

`list_shares_owner` was `USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid())` and the table
was writable by `authenticated` (PostgREST). Nothing tied `owner_id` to the list. A signed-in user could
insert `(list_id = <someone else's list>, owner_id = self, member_id = self, accepted_at = now())`;
the foreign key to `lists` is checked without row-level security, the row went in, `is_list_member()`
then answered true, and `lists_shared`, `list_items_read` and (for an editor) `list_items_insert` gave
the attacker the list and its items. List ids are sequential. The API never offers that insert, which
is why the API tests did not see it; the data API does. Reproduced in SQL on the CI image before the
fix (the attacker read the victim's item), not possible after.

Fix: migration `20261021120000_list_shares_owner_check.sql`. The policy now also requires
`owns_list(list_id)`, for reading, writing and the new row of an UPDATE, and the migration deletes any
share row whose owner does not own the list.
Tests: `test_api_security_rls.py::test_a_user_cannot_forge_a_membership_of_somebody_elses_list`,
`::test_the_migration_removes_forged_shares`, `::test_a_viewer_reads_and_an_editor_writes_but_neither_owns`,
and the parametrized matrix `::test_another_user_sees_and_changes_nothing` /
`::test_a_row_cannot_be_written_for_another_user` over every user table
(profiles, lists, list_items, preferences, price_alerts, push_subscriptions, list_shares,
spend_entries, substitution_feedback), plus `::test_every_table_with_a_user_column_is_covered`, which
fails when a new table with `user_id`, `owner_id` or `member_id` is added without a case or an entry in
the private list. `test_rls_contract.py` (issue #64) covered four of the nine; this file covers all.

### S2. The data API roles owned every table (High; the worst thing found)

On Supabase, PostgREST serves `anon` (anyone holding the project's anon key, which is in the web
bundle) and `authenticated`. Supabase's default privileges give both of them ALL on every table, view
and sequence created in `public`. Row-level security is what is supposed to stop them, and only the user
tables had any. On the CI image, before the fix, `anon` and `authenticated` had INSERT, UPDATE, DELETE
and TRUNCATE on `prices`, `promos`, `items`, `item_canonical`, `effective_prices`, `canonical_products`,
`chains`, `stores`, `taxonomy`, `gap_reports` (free-text notes and user ids), `alert_deliveries`,
`file_tracking`, `quarantine_events`, `gold_pairs`, `match_runs` and `schema_migrations`. With the
public key anyone could change a price, repoint a product match, empty the catalog or read the gap
reports, with one HTTPS request to `/rest/v1/<table>`. The earlier migrations had revoked the grants
one table at a time for `events`, `ocr_usage` and the beta tables only. This is on a stock Supabase
image, not on a hosted project (there is none yet); a project whose Data API is switched off is not
exposed, but nothing in the repo said to switch it off, and the web app uses it.

Fix: migration `20261021120100_data_api_lockdown.sql` revokes everything on every table and sequence
of `public` from both roles, gives `authenticated` back exactly what the web app uses, which is
`list_items` (`apps/web/src/features/share/useSharedList.ts` is the only `supabase-js` `.from()` call;
the docs listed PostgREST for profiles, lists and more, the code never used it), and removes the
default privileges that would hand the next table to them again. `anon` gets nothing. Everything else
the app does goes through the API, which has its own checks (consent for a location, ranges, limits).
Tests (`test_api_security_data_api.py`): `test_anon_has_no_privilege_on_anything`,
`test_authenticated_has_only_what_the_web_app_uses` (a privilege matrix over every table, view and
partition, so the next table fails the test unless it is meant to be exposed),
`test_nobody_in_the_data_api_has_a_sequence`, `test_a_table_created_later_is_not_open_to_the_data_api`,
`test_the_data_api_roles_cannot_touch_the_catalog_or_private_tables` (19 statements as each role),
`test_authenticated_still_edits_the_items_of_a_list_it_may_see` (owner, editor, viewer, stranger and
anonymous through the roles PostgREST uses).
Left as it is: Supabase's own default privileges declared for `supabase_admin` in `public` (the
migrating role may not change them; they only matter for tables that role creates), and functions
(`owns_list`, `is_list_member` are SECURITY DEFINER and answer only for the caller's own id; the other
functions run with the caller's rights, which no longer reach any table).

### S3. The push endpoint is a request our server makes (Medium, fixed)

`POST /me/push-subscriptions` stored any string up to 2000 characters, and the alerts job later POSTed
to it from inside our network: `https://169.254.169.254/...`, `https://10.0.0.5:8443/...`, a name that
resolves to localhost. Blind (the response is not returned), but a status code decides whether the
subscription is deleted. Fix: `push.validate_endpoint` (https only, default port, no credentials, a
host name that is not an address and not local by construction, optional allowlist of push services in
`API_PUSH_ENDPOINT_HOSTS`) at registration, applied by the schema, and `push.deliverable` right before
every send: the name must resolve to public addresses only, otherwise the subscription is dropped (410)
or retried later (lookup failure). Fields `p256dh` and `auth` got length limits.
Tests (`test_api_security_ssrf.py`): `test_push_endpoints_that_could_reach_the_inside_are_refused`,
`test_real_push_services_are_accepted`, `test_an_operator_can_pin_the_push_services`,
`test_the_sender_checks_where_the_name_points_now`, and `test_push_subscription_field_bounds` in
`test_api_security_input.py`. Known limit: the send-time check resolves the name itself and
`pywebpush` resolves it again (a rebinding window remains for this path). Set
`API_PUSH_ENDPOINT_HOSTS=fcm.googleapis.com,.push.services.mozilla.com,.notify.windows.com,.push.apple.com`
in production and the window is closed (only those hosts are ever contacted).

### S4. The recipe page fetch (Medium, fixed)

`recipe_fetch.py` already refused private addresses, other schemes and ports, credentials and
redirects to them. The review added what was missing:

- DNS rebinding: the host was checked, then httpx resolved it again to connect. Now the name is
  resolved once and the request goes to that checked address (URL host replaced by the address,
  `Host` kept, `sni_hostname` so TLS still verifies the certificate against the name). There is no
  second lookup. `test_the_request_is_pinned_to_the_checked_address_and_keeps_the_name_for_tls`,
  `test_a_name_that_changes_its_answer_after_the_check_gets_nothing`, `test_port_and_ipv6_pinning`.
- Address classes: the check was a list of "not private, loopback, link-local, multicast, reserved,
  unspecified". It now uses "is global" (so carrier-grade NAT 100.64/10, benchmarking and
  documentation ranges are out) and unwraps IPv4 inside IPv6 (mapped, 6to4, NAT64).
  `test_special_purpose_addresses_are_not_public` (35 addresses), the URL tests with the real
  resolver for `127.1`, `0x7f.0.0.1`, `0177.0.0.1`, `2130706433`, `[::ffff:7f00:1]`, and
  `test_a_redirect_to_a_name_that_resolves_privately_is_refused`.
- Compression: `Accept-Encoding: identity` is sent and a compressed answer is refused, because a
  small gzip body inflates past the 2 MB cap inside one network chunk before it is counted;
  a declared `Content-Length` over the cap is refused without reading.
  `test_a_compressed_response_is_refused_because_it_was_not_asked_for`,
  `test_a_declared_length_over_the_cap_is_refused_without_reading`.
- Time: the 5 s budget now covers the whole fetch, redirects included (it was per read).
  `test_the_time_budget_covers_the_whole_fetch_not_each_hop`.

Checked and fine: only HTTP(S), default ports, no credentials, at most 3 redirects each checked,
HTML or plain text only, 2 MB, no cookies, the page is only parsed (never executed), the route is
limited to 8 requests a minute per client.

### S5. Input that produced a 500 (Medium, fixed)

Each of these was reproduced with a failing test first.

- A raw JSON `NaN` or `Infinity`, or a lone surrogate (`"\ud800"`), made FastAPI's own 422 body
  unserializable, so the error response itself was a 500. The 422 body also echoed the posted value
  (up to the body size). Now a handler returns `{type, loc, msg}` only.
- A NUL character in any string reached Postgres (`PostgreSQL text fields cannot contain NUL`): a 500.
  Every string of every request model now refuses NUL and lone surrogates with a 422, `GET /search`
  too (`pattern`).
- A foreign key to a row that does not exist (`canonical_id`, `home_store_id`), a CHECK, an id past
  64 bits: an unhandled database error, so a 500 for what is the caller's mistake. Now
  `IntegrityError` is a 422 (a `UniqueViolation` a 409), `DataError` a 422, a down or exhausted
  database a 503 with `Retry-After`, and anything else a fixed `{"detail":"internal error"}` (the
  exception goes to the server log, never into the body).
Tests: `test_api_security_input.py::test_nul_and_lone_surrogates_are_422_not_500`,
`::test_nul_is_refused_in_every_string_of_a_request`, `::test_nul_in_a_query_string_is_422`,
`::test_nan_and_infinity_tokens_in_raw_json_are_422`; `test_api_security_leakage.py::test_an_unexpected_error_is_a_fixed_500`,
`::test_a_database_that_is_down_or_busy_is_a_503_without_details`,
`::test_a_value_the_database_refuses_is_a_422_without_the_sql_error`,
`::test_validation_errors_do_not_echo_what_was_posted`,
`::test_a_key_with_a_lone_surrogate_cannot_break_the_error_response`;
`test_api_security_idor.py::test_made_up_ids_are_404_or_422_never_500` (10 routes by 4 ids).

### S6. Sizes, lengths and ranges (Medium, fixed)

Uvicorn has no body limit, so a 1 GB JSON post to `/parse-list` was buffered before validation ran.
`BodyLimitMiddleware` refuses at `API_MAX_BODY_BYTES` (256 KB; a declared length at once, a chunked
body as it streams, with the CORS headers on the 413); `/parse-image` keeps its own 8 MB + envelope.
A 4000-character list of commas was 2000 items and several queries each: now at most 200 items
(the same ceiling as `/compare`). Bounds added where there were none: quantities (0 < q <= 1000, at
most 20 digits; `1e30` and `NaN` were accepted), `cost_per_km` (<= 100), `min_split_saving`,
alert thresholds, gap-report prices (a negative price was a CHECK violation, a 500), `clubs`,
`diet_flags` (30 items of 60 characters), `kosher_level`, `flex_defaults` (1000 entries, 60-character
keys), push fields. Existing limits were kept and now have both-sides tests: list name 100, item text
200, items per list 200, basket 200, recipe text 20,000, event batch 50, `radius_m` 500 to 15,000,
coordinates, `max_stores`, `candidate_stores`, `extra_stop_value`, `monthly_budget`.
Tests: the whole of `test_api_security_input.py` (123 cases), notably `test_a_body_over_the_limit_is_413_before_any_route_reads_it`,
`::test_a_chunked_body_without_content_length_is_counted_as_it_streams`,
`::test_a_list_has_at_most_200_items`, `::test_basket_quantities_are_bounded`,
`::test_odd_unicode_in_a_list_never_breaks_the_parser` (bidi controls, nikud, Arabic with diacritics
and Arabic-Indic digits, tatweel, combining marks, astral characters, 4000-character words, mixed
white space).

`/parse-image` was reviewed and needed no change: the format is decided by magic bytes, the body is
cut at 8 MB while streaming, the pixel count is read from the header and refused over 25 MP before
any pixel is decoded (Pillow's decompression-bomb limit is not relied on), upload and image stay in
memory (`MultiPartParser.spool_max_size`), nothing is logged, a count and an estimate are all that is
stored. Covered by `test_api_image_limits.py` and `test_api_image_privacy.py`.

### S7. Rate limits (Medium, fixed)

Only the OCR monthly cap and a per-session events limit existed; the session id is chosen by the
client, so a new one per request removed the events limit, and nothing limited `/parse-recipe` (a
fetch for the caller), `/optimize` (a solver), invite-code guessing or the rest. Now
`smartcart_api/ratelimit.py`: a sliding window per client, where the client is the verified user, else
the peer address (a forged token falls back to the address, and `X-Forwarded-For` is ignored by the
application: uvicorn rewrites the peer only for `FORWARDED_ALLOW_IPS`, default `127.0.0.1`, which is
the Caddy on the same host). Over the limit: 429 with `Retry-After` and CORS headers.

| Route | Per minute | Per hour |
|---|---|---|
| every route (ceiling) | 600 | 12,000 |
| `POST /parse-list` | 30 | 600 |
| `GET /search` | 120 | 3,000 |
| `POST /compare` | 60 | |
| `POST /optimize`, `POST /optimize/swaps` | 20 | 400 |
| `POST /parse-recipe` | 8 | 100 |
| `POST /parse-image` | 6 | 40 |
| `POST /events` | 30 | 600 |
| `POST /feedback/*` | 30 | 300 |
| `POST /beta/join` | 6 per user and 20 per address | 20 and 60 |
| `POST /beta/feedback` | 6 | 30 |
| `POST /me/lists/{id}/share` | 10 | 60 |
| `POST /lists/accept/{token}` | 10 | 60 |
| `/me/*` | 240 | |

`API_RATE_LIMIT=0` turns it off (the load test script sets it, the test suite sets it, one test file
turns it on). Tests: `test_api_security_ratelimit.py` (14): the window, the table bound, per-route
numbers, user versus address, forged tokens, spoofed headers, 429 headers, the events bypass with a new
session id each time, code guessing per account and across accounts.

### S8. The API's database role could not serve the beta and photo routes (Medium, fixed)

`docs/deploy.md` has the API connect as `smartcart_api`, a login role that is not the table owner.
`beta_invites`, `beta_members` (insert), `beta_feedback` and `ocr_usage` have row-level security with no
policy and were never granted to it; they relied on "the service connection is the owner". As
`smartcart_api`, `POST /beta/join`, `POST /beta/feedback` and the OCR cap check answer 500 while every
test (a superuser connection) passes. It fails closed, but the beta could not open. Migration
`20261021120200_api_role_beta_ocr.sql` wraps `smartcart_grant_api_role` (the first version keeps its
name with `_v1`) and adds exactly the columns and commands the routes use, with the policies that name
the role. Tests: `test_api_security_data_api.py::test_the_api_role_can_run_the_beta_and_photo_routes`
(runs the routes' statements as the role), `::test_the_api_role_gets_no_more_than_the_routes_need_on_the_private_tables`.
Caveat: the existing `SMARTCART_TEST_AS_API_ROLE=1` mode and `test_api_role.py` skip on this image
(the migrating role cannot grant on the `auth` schema), so the whole suite as that role was not run
here; run it once on the real project.

### S9. JWT verification (Low, fixed; the core was already sound)

Already right: HS256 pinned (`alg: none`, `HS384`, `RS256` headers refused whatever the key), `exp` and
`sub` required, `aud` checked, `anon` refused, `sub` a UUID, `user_conn` switches to a role without
BYPASSRLS and sets the claims transaction-locally, no `/me/*` route reachable without a token.
Changed: the 401 no longer repeats the library's message (`invalid token`, `token expired`); 30 s of
clock skew is tolerated (it was 0, so a small drift made a fresh token a 401); the `role` claim must be
`authenticated` (it only refused `anon`, so `service_role` or any other role claim with a `sub` got
through); `SUPABASE_JWT_ISSUER`, when set, pins `iss` (opt-in so a custom auth domain cannot lock
everyone out); a token over 8 KB is refused undecoded; the database session gets only
`sub, role, aud, exp, iat, is_anonymous`, not the e-mail, phone and user metadata (`rls_claims`).
Tests: `test_api_security_auth.py` (63): scheme and header forms, garbage, size, wrong secret, tampered
payload, `none`, `HS384/512`, `RS256/ES256/PS256/EdDSA` confusion, header-supplied keys, every claim
(`exp`, `sub` types, `aud` forms, `role`, `nbf`, `iat`, skew both sides, issuer), 503 without a secret,
fixed messages, optional-auth routes, events never trusting a body user id, and the route inventory:
`test_every_route_not_listed_as_public_requires_a_user` takes every path of the OpenAPI document and
fails for a new route that is neither protected nor in the explicit public list.

### S10 to S12. Logs, free text, caps and API headers (Low, fixed)

- Access log: uvicorn prints the query string, so `GET /stores/nearest?lat=..&lon=..` and
  `GET /items/barcode/..?lat=..&lon=..` logged where a person stood, at full precision, which the
  app promises to keep at neighborhood level (D11). `logsafe.StripQuery` cuts the query off the logged
  line (`smartcart-api serve` installs it). Tests: `test_access_log_lines_lose_their_query_string`,
  `test_the_uvicorn_config_installs_the_filter_on_the_access_logger`,
  `test_requests_leave_no_token_email_or_location_in_the_logs` (tokens, an e-mail claim and
  coordinates across profile, compare, optimize, nearest, barcode, alerts: none in the logs),
  `test_coordinates_are_stored_only_rounded_and_only_in_two_user_tables`,
  `test_an_alert_stores_the_rounded_point_of_a_consenting_user`, `test_a_request_location_is_never_stored`.
  The peer address is still in the access log (needed for abuse handling).
- Free text: every request string loses control characters other than newline and tab (terminal
  escape sequences, carriage returns, BEL) and the bidi embedding, override and isolate controls
  (U+202A to U+202E, U+2066 to U+2069); the marks Hebrew and Arabic use (LRM, RLM, ALM) stay. Beta
  feedback is printed in the maintainer's terminal, list names and items are shown to the people a list
  is shared with. `test_terminal_escapes_and_bidi_overrides_are_stripped_from_free_text`.
- Caps: 200 lists per user, 20,000 spend entries, 20 push devices, 50 invites and members per list
  (`test_a_user_has_a_ceiling_on_lists_and_devices`, `test_spend_has_a_ceiling_per_user`,
  `test_a_list_has_a_ceiling_on_invites`).
- API response headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, a
  `default-src 'none'; frame-ancestors 'none'` CSP on everything except `/docs`, `Cache-Control:
  no-store` on `/me`, `/beta` and `/lists/accept`, HSTS when the request came in over https
  (`test_every_response_has_the_hardening_headers`, `test_per_user_responses_are_not_cacheable`,
  `test_the_docs_keep_working_without_the_api_csp`, `test_hsts_only_over_https`).
- CORS was reviewed and not changed: the origins come from `API_CORS_ORIGINS`, there is no wildcard
  and no credentials flag (the token is a header, not a cookie), headers are `Authorization`,
  `Content-Type`, `X-Image-Consent`, methods GET, POST, PUT, PATCH, DELETE, OPTIONS (PATCH was added with the per-item list routes). Now pinned by
  `test_cors_allows_only_the_configured_origins`, `test_cors_never_allows_credentials_and_limits_headers_and_methods`.
  `API_CORS_ORIGINS` defaulting to `http://localhost:3000` is harmless (a local origin) but must be set in
  production (`docs/deploy.md` already says so).

### Authorization (IDOR) review: no defect in the API, tests added

Every route that takes an id scopes to the caller in SQL (`WHERE id = %s AND user_id = %s`) and under
row-level security as `smartcart_app`; the invite token is 32 random bytes, only its SHA-256 is stored,
single use, expiring, revocable; spend `client_id` is unique per user; beta feedback stores no user id.
`test_api_security_idor.py` (58) tries each of them as a stranger and as a member: lists, members,
share by id, by token and by member id (with the right list id, with the caller's own list id, with
a sibling list id), accept of a used, expired and revoked token and of guesses, spend (including
re-using another user's `client_id`), alerts (and the location they copy), push subscriptions, profile,
beta membership and feedback, body-supplied user ids (always a 422), and made-up ids.
One documented behavior: a push endpoint registered by one account is taken over when another
account registers the same endpoint (a shared device that switched accounts). The endpoint is an
unguessable URL issued by the browser, so this needs the secret first.

### W1. Web security headers (Medium, fixed)

`apps/web/security-headers.ts`, served by `next.config.ts` on every route:

| Header | Value | Why |
|---|---|---|
| Content-Security-Policy | `default-src 'self'`; `script-src 'self' 'unsafe-inline'`; `style-src 'self' 'unsafe-inline'`; `img-src 'self' data: blob: https://tile.openstreetmap.org`; `font-src 'self'`; `connect-src 'self'` + the API origin + Supabase (https and wss) + the tile origin; `worker-src 'self' blob:`; `manifest-src 'self'`; `media-src 'self' blob:`; `frame-src 'none'`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`; `frame-ancestors 'none'` | see the file's header comment for each directive; the API and Supabase origins come from the build's `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_SUPABASE_URL`; development adds `'unsafe-eval'` and the hot-reload socket |
| Strict-Transport-Security | `max-age=31536000; includeSubDomains` | no `preload`: that is a commitment to make with the domain's owner |
| X-Content-Type-Options | `nosniff` | |
| X-Frame-Options | `DENY` | for browsers that predate `frame-ancestors` |
| Referrer-Policy | `strict-origin-when-cross-origin` | other origins get our origin without the path (invite links and beta codes are in the path); `no-referrer` would get the OpenStreetMap tiles blocked, whose usage policy needs a referrer |
| Permissions-Policy | `camera=(self)`, `microphone=(self)`, `geolocation=(self)`; payment, usb, serial, bluetooth, midi, motion sensors, display capture, FLoC and Topics off | camera for the barcode scan and receipt photo, microphone for the voice list, geolocation for the neighborhood |
| Cross-Origin-Opener-Policy | `same-origin` | sign-in is an e-mail code, no popup flow |

Fonts: Heebo and Noto Sans Arabic are self-hosted (`next/font/local`); the CSP allows no font origin
and the existing e2e test blocks every non-local request while loading all weights. Map tiles: the
OpenStreetMap raster origin in `img-src` and `connect-src` (MapLibre fetches them), its worker from a
`blob:`.
Verified on the production build: every one of the 24 routes loads under the policy with no
`securitypolicyviolation` event and no CSP console error, the map starts its worker and requests its
tiles, the service worker registers, an injected cross-origin script and frame are blocked, `/sw.js`
keeps its no-store headers. `tests/e2e/security-headers.spec.ts` (7) and
`src/security/securityHeaders.test.ts` (11).

### W2. The mock API in the production bundle (Low, fixed)

`NEXT_PUBLIC_API_MOCK` was off in production, but the dynamic import in `src/api/client.ts` made the
bundler build the MSW library and every mock handler (invented prices) into lazy chunks. They were
never requested, and they were shipped. Now `next.config.ts` aliases `msw` and `@/mocks/handlers` to an
empty module unless the build asks for the mock (`src/mocks/disabled.ts`), the build **refuses**
`NEXT_PUBLIC_API_MOCK=1` when `SEO_STRICT_SITE_URL=1` (what `deploy.yml` sets) or Vercel says production,
and the e2e test reads `.next/static` for MSW and a handler-only string
(`the production bundle does not contain the mock API`). `npm run dev:mock` and the mock e2e helpers are
unchanged.

## What remains, and why

**R1. Anonymous `not_good` feedback pulls a match out of the price run (Medium).**
`POST /feedback/substitution` accepts anonymous callers (a trust signal, D10) and a `not_good` verdict
from the substitution card sets `item_canonical.needs_review`, which removes that mapping from the next
effective-price precompute until a human reviews it (`smartcart_catalog.feedback.record_feedback`).
One script can flag every mapping it can guess ids for: 30 a minute per address now. The fix is a
product decision in the catalog code, not an API patch: flag only after N distinct reporters
(session or account), or only for signed-in users, and keep the verdict anonymous otherwise; or flag but
keep the mapping in the run until a threshold. Until then the review queue should be watched during the
beta and a flagged mapping can be restored with `human_rejected = false, needs_review = false`.

**R2. The session lives in `localStorage`, and scripts may be inline (Medium).** `supabase-js` keeps the
access and refresh tokens in `localStorage`, readable by any script that runs in the page. The CSP
blocks every other origin, `eval`, `<object>`, `<base>` and framing, but `script-src` needs
`'unsafe-inline'`: Next emits inline scripts into every page, and the layout's theme and locale scripts
must run before first paint. A nonce policy needs every page rendered per request, which ends the
static SEO pages (`docs/seo.md`). The app renders no user-supplied HTML (React escapes text, JSON-LD
escapes `<`), which is what makes this acceptable for a beta. Options for the owner, in order of
effort: hashes for the two layout scripts plus Next's experimental SRI (webpack builds only); a nonce
CSP on the app routes only (`/(core)`, `/(phase2)`, `/(secondary)`) while the SEO routes stay static,
with a different, stricter policy; cookie sessions (`@supabase/ssr`) so the token is not readable by
script, which also means the API reads a cookie and gets CSRF handling.

**R3. Limits are per process and per address (Low).** With `WEB_CONCURRENCY` workers the limit is the
configured one times the workers; a mobile carrier's shared address is one client for the people who
are signed out (signed-in people are counted per account). The events route also has its per-session
limit in the database, which holds across processes. A shared counter (the database, as events do, or
Redis) is the next step if the beta shows abuse; the numbers are proposals, not measured.

**R4. `/parse-image` is anonymous (Low).** The monthly cap is global, so a determined caller from many
addresses can use it up (availability, not cost: the cap is the brake). Requiring a signed-in user for
photos, or a per-user monthly count, would fix it; it changes the product (a signed-out person can use
photos today).

**R5. HS256 shared secret (Low).** `SUPABASE_JWT_SECRET` can mint any user's token, so whoever reads
the API's environment is every user. Supabase projects can sign with an asymmetric key (published as
JWKS); verifying with the public key and pinning ES256 removes the secret from the API host. Do this
when the project is created, before the first token is issued, since changing it signs everyone out.

**R6. Consent for a location is enforced by the API only (Low).** `profiles` has no CHECK that a
location needs `consent_location`; the API enforces it. After S2 the data API cannot write `profiles`,
so there is no path today. If it is ever opened for profiles, add the CHECK first (the existing tests
insert locations without consent, which is why it was not added here).

Smaller notes: `/docs` and `/openapi.json` are public (needed by nobody in production; set
`docs_url=None` if you prefer); the join-code response distinguishes unknown (404) from used up (410),
which is cheap to guess-limit and not worth hiding; the Realtime channel for shared lists is filtered
by `list_id` and by row-level security, not by a channel secret.

## Operator checklist (new settings)

| Variable | Where | Meaning |
|---|---|---|
| `SUPABASE_JWT_ISSUER` | API | `https://<project>.supabase.co/auth/v1`; set it once the project exists |
| `API_RATE_LIMIT` | API | `0` switches the per-client limits off (load tests only) |
| `API_MAX_BODY_BYTES` | API | default 262144 |
| `API_PUSH_ENDPOINT_HOSTS` | API | `fcm.googleapis.com,.push.services.mozilla.com,.notify.windows.com,.push.apple.com` in production |
| `FORWARDED_ALLOW_IPS` | uvicorn | `127.0.0.1` (the default) when Caddy is on the same host; the proxy's address otherwise, or every client shares one limit |
| `API_CORS_ORIGINS` | API | the site's origin(s) only (already required) |
| `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL` | web build | also build the CSP's `connect-src`; a wrong value blocks the call in the browser |

In the Supabase dashboard: after the migrations, the Data API only needs `list_items` (and Realtime for
it). Keeping "exposed schemas" at `public` is fine after S2; removing `public` from it and exposing a
dedicated schema is stricter and not needed now. Run `SELECT smartcart_grant_api_role('smartcart_api')`
after the migrations if the role was created before them (the migration does it when the role exists).

## Re-running the review

```bash
uv run pytest services/api -q -k "api_security or rls_contract"      # all of the above, against DATABASE_URL
cd apps/web && npm run test -- src/security && npm run build && npx playwright test tests/e2e/security-headers.spec.ts
```

When adding: a route needs an entry in `PUBLIC` of `test_api_security_auth.py` or a user dependency; a
table with a user column needs a case in `test_api_security_rls.py`; a table for the data API needs a
GRANT in its own migration and a line in `AUTHENTICATED_MAY` of `test_api_security_data_api.py`; a
string field that reaches a person's screen goes through the request models, which clean it.
