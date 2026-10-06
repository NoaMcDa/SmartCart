# Product and market

English summary and conclusions from the market research of October 2026. The original (Hebrew, with
sources) is `research/2026-10-market-research-and-product-plan.he.md`.

## The one-paragraph thesis

The Israeli market has plenty of price comparison tools and none that combines trust with a real
savings mechanism. The veterans (CHP, Pricez) compare by barcode. The 2025–2026 newcomers (Oshek,
Hazol, Snaplist, SROK, IsraBis) add free-text and AI but none offers a semantic canonical product,
per-item flexibility the user controls, promo optimization, and a cart split that accounts for travel
cost. That gap is the product. The consumer authority is also fixing chain reporting quality through
2026, which makes the timing good.

## Competitors

| Competitor | Platform | Comparison basis | Substitutes | Split | Business model | Notes |
|---|---|---|---|---|---|---|
| CHP | Web, iOS, Android | Barcode or name | No | No | Ads, BI to chains | One-person operation since 2016. Dated UI. Compares only items present in every store. |
| Pricez | Web, iOS, Android | Barcode or name | By unit price within category | No | Sells consumer data to chains | Hourly updates, 2,000+ stores, history, alerts, shared lists. Data-selling is a conflict a newcomer can exploit. |
| Oshek (oshek.co.il) | Web | Free text with AI | When missing in a chain | No | Unclear, SEO-heavy | No signup. Daily updates. 6 chains in footer versus "10+" in copy. |
| Hazol (hazol.co.il) | Web | Barcode | No | No | Social venture, free | 171k products, 24 chains, 1,103 stores. Admits data is sometimes partial or late. |
| Snaplist | iOS, Android | AI, receipts | By price-quantity ratio | No | Free, in beta | Closest to our vision. Receipt scan, list from habits, hidden promos. Watch closely. |
| SROK | iOS | Barcode | No | By location | Unknown | Coupon alerts. |
| IsraBis | Claims 49 chains | AI | | | | App Store link is a placeholder id; may not exist. |
| MySupermarket IL | Closed 2022 | | "Swap and save" | | Commissions | Pioneer. Bought by One Technologies in 2020, closed for lack of business viability. Lesson: do not depend on chain cooperation. |

International references worth copying: Trolley.co.uk (tiny volunteer team, 4.8 stars, 17k reviews),
Shopsplit (claims 2 stores capture ~80% of available savings), Allsupers (10–16% saving from two
cheapest chains), WiseList (paid Smart Split, "never forces inaccurate matches"), GroceryChop (three
modes: single store, best per item, split trip), Grocer.nz (freemium at 6 USD/month).

## Market gaps identified

1. No existing product has a canonical product whose flexibility the user controls.
2. No tool computes a split that includes travel cost and "buy X" promos.
3. Trust: inaccurate data and app-versus-checkout gaps are the main cause of churn.
4. Dated interfaces, no accessibility for segments with proven demand (Haredi with kosher filters, Arabic UI, periphery).
5. No competitor can claim full neutrality; some sell data to chains.

## How much can a user really save

Verified facts:
- Identical 67-item basket: Rami Levy 908 ILS versus Tiv Taam 1,147 ILS, a gap over 26%.
- Private label is typically 15–25% cheaper than branded (Competition Authority study, January 2026). Private-label share in Israel is only ~7% versus 33–34% in France and Germany.
- Private label is not always cheaper: one olive oil check showed the private label 24% more expensive. Comparison must be by actual unit price.

Author's estimates:
- Loyal discount-chain shopper, brand-loyal: 3–8% from promo and store optimization.
- Adds "any brand" flexibility: another 10–15%.
- Switching from an expensive chain with full flexibility: 25–35%.
- On a ~3,000 ILS monthly basket that is roughly 300–900 ILS per month for a flexible user.

The "up to 30%" and "up to 50%" numbers in competitor marketing are edge cases. Our messaging should
say 10–20% for a typical user.

## Regulation and data

- Legal basis: Food Competition Law 2014 and the Price Transparency Regulations 2015, later extended to pharmacy chains. Applies to retailers with turnover above 250M ILS.
- Three file types in a uniform structure: Stores, Prices (PriceFull daily plus hourly Price deltas), Promos (PromoFull plus Promo deltas). Gzip XML, each chain with its own dialect and encoding quirks.
- Update within one hour of a change at the register. Files kept 3 months. 99.5% availability required.
- Enforcement exists: fines of 300–600k ILS to major chains in 2021.
- The authority is rolling out an improved reporting model through 2026 (uniform promo definitions, item-and-store accuracy, AI for substitutes). Our adapters must support the old and new schema in parallel.
- A proposed bill would raise the turnover threshold and exempt more retailers. Risk: losing small cheap chains. Track it.
- The AWS-based "price transparency project" is for supervision and research. The authority says app makers will be able to use it, but no public API is verified.
- Ater and Rigbi (AEJ Microeconomics 2023): transparency lowered prices 4–5% in treated products, cross-chain price variance fell 50%, but consumers barely used comparison sites. The effect came through press coverage. Conclusion: adoption is a product problem, and press is the growth channel.

## Data limitations and how we handle them

| Limitation | Handling |
|---|---|
| Prices differ per store within a chain | Base price per chain, per-store exceptions |
| Online prices differ from store prices | Identify the online "store" record, show channel explicitly |
| Club and credit-card promos | Filter by clubs the user marks in profile |
| Complex or incomplete promos | Confidence score per promo, "report a gap" button |
| Weighed goods with internal codes | Normalize per kg, semantic name mapping, "estimated price" label |
| Private-label and chain-internal barcodes | Only semantic matching solves this. This is the core advantage. |
| Encodings and dialects (windows-1255, UTF-16, zip, `<Item>` versus `<Product>`) | Per-chain parsers based on OpenIsraeliSupermarkets |
| Some portals block cloud IPs | Ingestion worker on an Israeli VPS or proxy |

## Legal rules we follow

- Transparency files are public by law and intended for app makers. Using them is permitted.
- Never scrape chain online stores (images, descriptions). Copyright and terms of use apply.
- Avoid misleading presentation: show update date, say "price at checkout governs", label every substitute, never inflate savings.
- Privacy law amendment 13: location and receipts are sensitive. Minimize data, process receipts on device where possible, explicit consent, never sell personal data.
- Accessibility: Israeli standard 5568 (WCAG 2.0 AA equivalent) applies to apps and sites.

## Positioning

Differentiate on depth (taxonomy, flexibility, optimization), not on a single feature. Make matching
quality a public metric ("98% of substitutions approved"). State neutrality explicitly: no data sales
to chains, no sponsored ranking. Grow through press with a monthly basket index, the channel the Ater
and Rigbi study showed actually works. First audiences: large families, kosher-conscious shoppers,
periphery.
