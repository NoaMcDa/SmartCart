# Methodology page and the public quality metric

Issue #21, decisions D10 (trust and neutrality as product rules) and D8 (the page lives with the
static SEO pages). The page is `/methodology` in `apps/web/src/app/(seo)/methodology/page.tsx`. It is
in Hebrew, static, on the main domain, linked from every SEO page, and carries a visible last-updated
date. This file is the English source of what it says and where each claim comes from. When you change
the page, change this file in the same commit and bump `METHODOLOGY_UPDATED` in
`apps/web/src/features/seo/config.ts`.

Labels follow `docs/README.md`: **verified** is a cited source or a measured result, **estimate** is a
judgement, **target** is a goal not yet reached. The page marks every quoted number as one of:
"נמדד" (measured), "הערכה" (estimate), "יעד" (target), "לפי החוק" (fixed by law).

## What the page says, and the basis of each claim

| Section (id) | Claim | Basis |
|---|---|---|
| `sources` | Prices come only from the chains' legally mandated transparency files | `product-and-market.md`, "Regulation and data" and "Legal rules we follow" (verified) |
| | Nothing is taken from chain online stores (prices, images, descriptions) | CLAUDE.md conventions; `product-and-market.md` legal rules |
| | A chain must update a file within an hour of a register change | `product-and-market.md` (verified); marked "לפי החוק" |
| | We load a full file nightly and deltas during the day for chains that publish them | `ingestion.md`, D13. **Re-check before launch**: infrastructure is not provisioned yet (`infra-provisioning.md`) |
| | A file that fails the quality gates is not loaded | `ingestion.md` quality gates (zero price, jump, item-count drop, stale date). The page names the gates without their thresholds |
| | Branch prices differ; base price per chain plus branch exceptions; club promos only for chosen clubs, with confidence; weighed produce is "estimate" | D6, `product-and-market.md` "Data limitations", `ux-design.md` |
| | "Price at checkout governs"; report-a-gap | D10 |
| `matching` | Chain items map to a canonical product with a confidence; three flexibility levels | D4, `catalog.md`, `matching.md` |
| | Critical attributes are hard rules, never replaced by similarity | D5, `matching.md` (the judge) |
| | Precision over recall; uncertain matches go to human review and are not shown | D5; `matching.md` (confidence bands: 0.60 to 0.90 is review) |
| | Kosher and diet flags are unverified and are not match rules | `catalog.md` section 2 (`ALWAYS_UNVERIFIED`) |
| | "Not a good substitute" sends the mapping to review and removes it from comparisons until reviewed | `api.md`, `POST /feedback/substitution` |
| | The catalog holds N canonicals (N read from `products.json`, "נמדד"); the list and ranking are an estimate and not yet reviewed by a domain expert | `catalog.md` "Choosing the canonicals" and "Open: domain-aware reviewer sign-off" |
| `saving` | Net saving = basket saving − travel cost − value of an extra stop, versus the user's own store, never versus the most expensive chain | D7, CLAUDE.md |
| | Comparison is per unit (100 g, 100 ml, unit, kg) | D6 |
| | A split is shown only if its net saving passes a minimum | D9, `api.md` (`min_split_saving`) |
| `neutrality` | No sale of user data; no sponsored ranking; any future referral labeled and never affecting ranking; no third-party ad or tracking SDKs | D10, D11, D12, issue #21 |
| `quality` | The public metric, from data (below) | D10 |
| `basket-index` | Fixed versioned basket, chain median per product, promos included except club, weighed goods estimated, snapshot per month, pre-publication checks | `basket_index.py`, issue #44 |
| `privacy` | Location rounded to neighborhood and only with consent; receipts processed and deleted (future); no sale; first-party beta events without list content or free text; data deletion from the profile | D11, `beta-plan.md` |

The page does not name competitors. The research (verified) records that one competitor sells consumer
data to chains; the neutrality section states our commitments instead of comparing.

## The public matching-quality metric

> "X% of substitutions correct on the evaluation set (synthetic until real data)"

It is generated, never typed:

1. `smartcart-catalog evaluate` (matching, issue #38) runs the judge over the gold set and writes a
   `match_runs` row with `kind = 'evaluate'`: precision and recall per flexibility level, the number of
   served predictions per level (`support.predicted_<level>`), the gold set size, and
   `synthetic_gold_set`.
2. `smartcart-catalog export-seo` (`export_seo.py`, `build_quality`) reads the latest finished
   `evaluate` row and writes `apps/web/public/seo/quality.json`: `precision` and `sample` per level,
   `measured_at` (the run's `finished_at`), `gold_items`, `gold_pairs`, `synthetic`, the judge name,
   and the 98% target. With no run it writes `{"available": false}` and the page says the metric has not
   been measured, with no number.
3. The page (`features/seo/QualityMetric.tsx`) renders the headline for the "any brand" level, a table
   for all three levels, the definition, the sample size, the measurement date, and, while the gold set
   is synthetic, the words "סינתטי עד שיהיו נתונים אמיתיים" in the same sentence as the number.
   Percentages are rounded down, so a measured 99.96% reads 99.9%, never 100.0%.

Definition shown on the page (it matches `evaluate.py`): of the substitutions the system serves to a user
at a flexibility level (auto-accepted: confidence at least 0.90 and not flagged for review), the share
that the evaluation set labels as qualifying for that level. Substitutions sent to review are
abstentions, not served.

**What the number is not.** The gold set is generated from templates (`data/gold/build_gold.py`,
`matching.md`). The number shows that the pipeline runs end to end and that the hard rules hold. It is
not an estimate of precision on real products. The 98% at "any brand" is a **target**, shown as such.

**Planned additions, not built yet.** After the closed beta (`beta-plan.md`) the page will also show the
user rejection rate (rejections over substitutions shown, per level) with its sample size and date, from
the `beta_rejection_rate` view. Until real labels exist the page must not say "98% of substitutions
approved" as a result: that phrase in the research (`product-and-market.md`, Positioning) is the
public-metric idea, and the 98% is a target.

## Where else the page is linked

- Every SEO page: the trust block (`TrustNote`) and the footer link to `/methodology`.
- The results footer and the substitution card belong to W4b. They should render
  `MethodologyLink` from `apps/web/src/features/seo/components.tsx` (or link to `/methodology`).
  Status: **not wired from this workstream**, listed in the pull request.
- `sitemap.xml` includes the page.

## Claims to re-check before the public launch

1. Update frequency (nightly full files, deltas during the day) once ingestion runs on the VPS.
2. The list of chains in `sources`, if the page names any (it does not today).
3. The quality metric: replace the synthetic gold set with a labeled real one, then remove the
   synthetic wording only when `synthetic` is false in `quality.json`.
4. The privacy section against the final consent text in `beta-plan.md`.
5. A legal read of the neutrality wording before it is public. Not done.
