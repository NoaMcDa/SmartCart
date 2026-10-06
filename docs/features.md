# Features and monetization

## Savings levers (what the product actually does)

1. **Canonical product and unit price.** "Tomato paste", "fresh milk 3% 1 liter", "unsweetened soy drink", "frozen salmon fillet" are nodes in a taxonomy. Comparison is per 100 g or per liter, matching Israeli shelf-labeling rules.
2. **Three flexibility levels per item.** Exact product (barcode). Any brand (same canonical, same critical attributes, private label included). Close substitute (soft attributes open: frozen instead of fresh, different pack size, 1% instead of 3%). Smart defaults by category.
3. **Promo optimization.** Effective price for 1+1, "3 for 20", "buy X get Y", basket promos. Offer to round up quantity when it pays ("add one more and save 4 ILS"). Filtered by the user's clubs.
4. **Cart split with total cost.** Basket cost plus travel (km times cost per km, or public transport) plus the user's value of time plus delivery fees online. User sets max stores (1–3) and the minimum saving that justifies an extra stop.
5. **Alerts and timing.** Price drop alerts at the canonical level, not just barcode. Simple promo-cycle prediction from history.
6. **Preference filters.** Kosher and supervision level, vegan, gluten-free, allergens. Extracted from names and kosher marks; uncertain values ask the user and are labeled unverified, since transparency files do not carry allergens or kosher structurally.

## MVP

- Free-text Hebrew search at the canonical level, and paste a whole list.
- Flexibility level per item with smart defaults.
- Basket comparison across stores in a user-chosen radius, with unit price.
- Two-store split with travel cost and saving threshold.
- Transparent explanation for every substitution, and an update date on every price.
- Saved recurring lists ("the weekly shop").

## Phase 2

- Barcode scanning that maps a shelf item to a canonical and shows a cheaper substitute.
- Canonical-level price drop alerts.
- Price history.
- Shared family lists in real time.
- Promo and club optimization (MILP).
- "Smart cart": the one swap with the biggest effect ("3 swaps save you 41 ILS").

## Future

- Receipt scan to list (Snaplist already offers it, so it is table stakes eventually).
- Voice list. Handwritten list photo.
- Promo prediction and purchase timing.
- Monthly budget and spend tracking.
- Recipe to list.
- Cart transfer to chain online stores (WiseList pattern).
- Arabic UI.

## Monetization, in priority order

1. **Freemium.** Core free. Subscription of about 10–15 ILS per month unlocks 3-store splits, unlimited alerts, full history, family sharing. The WiseList+ and Grocer.nz model.
2. **Transparent partnerships** with online stores and delivery services. Clearly labeled referral fee that never affects ranking.
3. **Private-label or manufacturer offers**, labeled and separate from ranking.
4. **Aggregate anonymized market reports** for research and press, not for chains.
5. **Grants.** Innovation Authority, or a future consumer-authority call (the previous 5.85M ILS call got zero bids because support was conditioned on usage).

Never depend on chain commissions as the only revenue. That is how MySupermarket died.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Data quality (partial promos, app-versus-checkout gaps) | Confidence per promo, visible update date, report-a-gap feeding checks, track the authority's improved schema, register as an app maker with the authority |
| Matching accuracy | Hard rules on critical attributes, precision over recall, small hand-labeled catalog first, user feedback as labels, public quality metric |
| User trust | Net saving versus own store, explanation and undo on every swap, declared neutrality, methodology page |
| Adoption and retention | Low friction (paste, receipts, recurring lists), value on first use, press and monthly basket index, segments with proven demand |
| Monetization | Operating cost under 150 USD per month, freemium independent of chains, grants, transparent partnerships |
| Chain reaction (blocking, format changes) | Data is public by law, Israeli-IP worker, per-chain adapters with breakage alerts, no online-store scraping |
| Regulatory change (exemptions, new schema) | Adapter layer, follow Knesset proceedings |
| Fast competitors (Snaplist, Oshek) | Differentiate on depth, make matching quality a visible metric |
