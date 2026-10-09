# Cart handoff to chain online stores (#72)

After SmartCart picks the cheapest store, a user who shops online can continue on that chain's own
site: copy or share the list for that store, open the chain's public site, and open the chain's public
site search for each item. This page says what is built, why it is not scraping, what is unverified, and
what an official "items land in the chain's cart" integration needs.

**Status.** The link handoff is built and off by default. The issue's first acceptance criterion, "a
user can send a cart and see the items in the chain's online cart", stays **open**: it needs a partner
API or an official cart-prefill link, and none exists in this repository (see
[What an official integration needs](#what-an-official-cart-prefill-integration-needs)).

## What the user gets

On each store card of the results and in each column of the split view, when that store's chain is
switched on, a "המשך באתר הרשת" action opens a sheet with:

1. the list for that store as text, one `name × quantity` per line, with a copy button (clipboard, with
   the select-the-text fallback the share sheet uses) and the phone's share sheet where the browser has
   one;
2. "לאתר הרשת", a link to the chain's online store;
3. per item, "חיפוש באתר", a link to the chain's public site search for the item's display name
   (URL-encoded), shown only when the chain has a search template;
4. a disclaimer that is always visible: online prices, availability and delivery fees may differ from
   the transparency files, and the price at checkout governs;
5. when the chain's `online_referral` is true, a "קישור שותפים" label next to every link and a note that
   the links may earn a fee at no cost to the user and do not affect ranking, prices or savings.

Every link is `target="_blank" rel="noopener noreferrer"`. Nothing is shown for a disabled chain, and a
failed `GET /chains/online` hides the action without touching the results.

## Why this is not scraping

CLAUDE.md and `docs/architecture.md` (section 10) forbid scraping chain online stores; only the legally
mandated transparency files are fetched. This feature fetches nothing from any chain:

- the server never requests a chain's site, and the web app never requests it either. The only request
  is `GET /chains/online` to our own API, which reads two text columns from our database;
- the "link" is an `<a href>`. The user's own browser opens the chain's own public page, the same way
  it opens any link in a message;
- no item is matched against the online catalog, no price, stock or product id is read from the site,
  no cart is touched, no account or credentials are involved;
- the search link is a public URL pattern the chain publishes by having a search box. We build it from
  the item's name and the user clicks it;
- the Playwright spec `tests/e2e/handoff.spec.ts` fails if the page itself requests the chain's host.

This also satisfies the issue's "no code path scrapes or automates a chain's online store".

## Neutrality

Ranking is independent of the handoff and of any referral (D10, D12):

- `services/api/tests/test_api_handoff_independence.py`: `/compare` and `/optimize` responses are
  byte-identical with `CART_HANDOFF_CHAINS` unset or set to any combination of chains, with addresses
  present or absent and referral flags on or off; the ranking modules must not mention the handoff
  columns, the setting or the route;
- `apps/web/tests/unit/handoff-independence.test.ts`: no ranking, pricing or savings module of the web
  app reads handoff data, the handoff is imported only by the two store cards, and the handoff reads no
  price, saving or ranking field.

## Configuration

| Name | Where | Meaning |
|---|---|---|
| `CART_HANDOFF_CHAINS` | API environment | Comma separated chain ids whose handoff is on. Empty or unset: every chain is disabled. |
| `chains.online_url` | database | The chain's own online-store home page (https only, CHECK). |
| `chains.search_url_template` | database | The chain's public site-search URL; must contain `{q}` (https only, CHECK). |
| `chains.online_referral` | database | `NOT NULL DEFAULT false`. True labels the links "קישור שותפים". Never read by ranking. |

`GET /chains/online` returns every chain row with `enabled = (chain id in CART_HANDOFF_CHAINS) AND
online_url is present`. It is public and sent with `Cache-Control: public, max-age=3600`, so flipping the
flag takes up to an hour to reach a browser. Details in `docs/api.md`.

To enable a chain: verify its row in the table below by opening the two URLs in a browser, then add the
chain id to `CART_HANDOFF_CHAINS` and restart the API. To disable it, remove it from the variable.
There is no per-chain code.

## Per-chain addresses

Migration `20261011100100_chain_online.sql` seeds a few addresses. **All of them are unverified, check
before enabling.** The repository's docs and fixtures contain no online-store address (the only chain
URLs in the repo are the transparency-file portals, which are not shops). The addresses below are the
chains' public sites as widely known, written down without being checked against a live site from the
development container, whose network cannot reach them. Where the site-search pattern is not known with
confidence the template is NULL: better NULL than wrong. A chain with no home page here has no row of
addresses and its handoff cannot be enabled.

| Chain | Chain id | `online_url` | `search_url_template` | Source | Verified |
|---|---|---|---|---|---|
| Shufersal (שופרסל) | 7290027600007 | `https://www.shufersal.co.il/online/` | `https://www.shufersal.co.il/online/he/search?text={q}` | public site, from general knowledge | unverified, check before enabling |
| Rami Levy (רמי לוי) | 7290058140886 | `https://www.rami-levy.co.il/he/online` | `https://www.rami-levy.co.il/he/online/search?q={q}` | public site, from general knowledge | unverified, check before enabling |
| Yochananof (יוחננוף) | 7290803800003 | `https://yochananof.co.il/` | NULL (pattern not known) | public site, from general knowledge | unverified, check before enabling |
| Victory (ויקטורי) | 7290696200003 | `https://www.victoryonline.co.il/` | NULL (pattern not known) | public site, from general knowledge | unverified, check before enabling |
| Osher Ad, Tiv Taam, Carrefour/Mega, Hazi Hinam, Machsanei Hashuk, King Store | | NULL | NULL | no address stated | not seeded |

Chain rows are created by the ingest loader, usually after the migration. The seed therefore lives in
`chain_online_seed` and a `BEFORE INSERT` trigger on `chains` fills a new row's addresses when it has
none; the migration also updates rows that already exist. Editing an address later is a plain `UPDATE`
on `chains`. The loader never overwrites these columns (it updates only `name` and `portal`).

Before enabling a chain, also read its site terms for deep links to its search page, and confirm the
site works with `rel="noopener noreferrer"` (no referrer is sent, which some sites may treat as direct
traffic). A referral flag may be set only with a written agreement (below).

## What an official cart-prefill integration needs

The sheet cannot put items in the chain's cart, and cannot map our chain-scoped items to the online
catalog without reading it. Both need the chain's cooperation. Per chain, one of:

1. **A partner API** (cart or basket creation) with documented terms, credentials held server side in a
   secret store, rate limits, and a stable product identifier we may map to. The mapping can start from
   the barcode (GS1) that both the transparency file and the shop use, so unmatched items are listed for
   the user.
2. **An official deep link or cart-prefill URL** the chain documents for third parties (for example a
   link that takes a list of barcodes and quantities). Same mapping, no credentials.
3. **A delivery-service partnership** that already holds the chain integration.

For any of them we need before writing code:

- **Legal basis and terms**, in the repository next to this page: who the counterparty is, what we may
  send and receive, whether a referral fee is paid, the term and how to end it (issue #72 asks for each
  integration's legal basis and terms to be documented). No integration is described here because none
  exists.
- **A per-chain flag**: the existing `CART_HANDOFF_CHAINS` plus a new capability field on `chains` (for
  example `cart_prefill`: `none`, `link`, `api`). The UI would show "send the cart" only for `link` and
  `api`, and the sheet in this page stays as the fallback.
- **Graceful failure**: a clear message and the user's list kept, never a lost cart (issue #72).
- **Referral labeling**: if any fee exists, `online_referral = true` and the "קישור שותפים" label,
  with the ranking independence tests above kept green. Sponsored ranking and paid placement stay out of
  scope (D10, D12).
- **No credentials of the user's chain account** stored, no order placing, no payment.

Until such an agreement exists, the acceptance criterion "items land in the chain's cart" stays open on
#72, and what ships is the link handoff above.

## Tests

API: `services/api/tests/test_api_chains.py` (flag default off, flag and address both needed, referral as
stored, Cache-Control, https and `{q}` CHECKs, the seed trigger) and
`test_api_handoff_independence.py`. Web: `features/handoff/links.test.ts` (URL building, https only),
`features/handoff/HandoffAction.test.tsx` (enabled and disabled chains, sheet, disclaimer, link
attributes, referral label, copy and fallback, share, failed request leaves the results unchanged),
`tests/unit/handoff-independence.test.ts`, `tests/e2e/handoff.spec.ts` (phone and desktop, results and
split view, no request to the chain's host, axe on the sheet in both themes).
