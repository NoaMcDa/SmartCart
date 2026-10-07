# Matching: embeddings, blocking, judge, review, evaluation

How a chain item becomes "this is canonical product X, at flexibility level Y, with confidence Z",
how a human corrects it, and how we measure it. Covers issues #29 (embeddings, blocking, HNSW),
#33 (match judge with hard rules), #38 (review UI, gold set, evaluation harness) and #43 (user
feedback loop). Decisions D4 (three flexibility levels) and D5 (precision over recall) govern
everything here; architecture section 3 steps C to E describe the plan this implements.

Code: `services/catalog/smartcart_catalog/` — `embed.py`, `block.py`, `judge.py`, `match.py`,
`evaluate.py`, `review_app.py`, `feedback.py`, `cli_matching.py`. Gold set: `data/gold/`.

> **The gold set is synthetic.** `data/gold/` holds 2,419 pairs over 831 items and 56 canonicals,
> generated from templates by `data/gold/build_gold.py`. They are placeholders until real chain
> items are loaded and labeled by a human. Numbers measured on them show that the pipeline runs
> end to end and that the hard rules hold; they are **not** an estimate of precision on real data.

## One item, end to end

```
items.raw_name ──> item_attributes (extraction, #25)  or  fallback_attributes (regex + lexicon)
      │                         │
      │                 block = (department of category_path, base unit)
      ▼                         │
 item_embeddings ──> top_k: one SQL statement, cosine <=> on canonical_products.embedding,
 (embed.py)            restricted to the block ──> k candidates with similarity
                                │
                     judge: hard rules veto, soft rules set the level, confidence
                                │
          ┌─────────── >= 0.90 ─┼─ 0.60..0.90 ──────────┬── < 0.60 ──┐
          ▼                     ▼                       ▼            ▼
   item_canonical          item_canonical            no mapping    (nothing)
   needs_review=false      needs_review=true ──> review UI ──> source='human'
          │                                                 ▲
          └── user: "not a good substitute" ──> needs_review=true (feedback marker)
```

`apply_decisions` is the only writer of machine mappings. It is idempotent, never touches a row
with `source = 'human'`, never re-creates a pair a human rejected, and keeps `needs_review` set
while a user report on that mapping is unresolved.

## Step C: embeddings and blocking (#29)

**Embedders** implement the `Embedder` protocol (`models.py`):

| Name | Use | Notes |
|---|---|---|
| `hash` (`HashEmbedder`) | tests, CI, local dev | Deterministic 1024-dim signed feature hashing of character 2-4-grams and words of the normalized text (final letters folded, nikud and quotes stripped, digits and `%` kept), L2-normalized. Similar strings get similar vectors; there is no semantics. |
| `bge-m3` (`BgeM3Embedder`) | production | BGE-M3 dense vectors via sentence-transformers (`uv sync --extra embed`), imported lazily, model name configurable (`$EMBEDDING_MODEL`, default `BAAI/bge-m3`). Not runnable in the build sandbox (Hugging Face is unreachable there), so no BGE-M3 numbers exist yet. |

**Batch jobs** `embed_canonicals` and `embed_items` are idempotent: an item already embedded with
the same model and not updated since is skipped; a canonical is re-embedded only when its vector
is missing, its name changed (fingerprint), or the model changed. Each run writes a `match_runs`
row (`kind = 'embed'`) with counts. `canonical_products` has no model column, so the model and
the name fingerprints live in that row (contract change requested below).

**Blocking.** An item is compared only with canonicals whose `taxonomy_id` is its department
prefix (`dairy` matches `dairy` and `dairy.*`, not `dairymilk`) and whose `base_unit` equals the
item's (100g, 100ml, unit, kg). The department comes from the item's `category_path`; with no
category the block is the base unit alone. Department depth (1) is the default because a wrong
second-level guess would cost recall; the judge's product-type rule handles the rest.

**Top-k** (`block.top_k`) is one SQL statement: a `LATERAL` subquery ordered by
`embedding <=> item_embedding` with `LIMIT k`, the block as filter, returning cosine similarity.
The HNSW index (`vector_cosine_ops`) can serve it; whether the planner uses it is a cost
decision. Measured on this schema with pgvector 0.6, the HNSW path costs about 200-260 against
11-36 for a seq scan plus top-N sort at 300-1,000 rows, because pgvector barely costs the distance
computation on TOASTed vectors; the crossover, extrapolated, is in the tens of thousands of rows.
At MVP size (150-300 canonicals) the exact seq scan runs, which is also the most accurate.
`tests/test_block.py` proves the index can serve the statement (with seq scans and sorts
disabled), so the index takes over as the catalog grows. `configure_session` raises
`hnsw.ef_search` and, on pgvector 0.8+ (the Supabase image), turns on iterative index scans so a
selective block still returns k rows.

## Step D: the judge (#33)

Embeddings never decide a match. The judge does, with hard rules that similarity cannot override.
Rules per candidate (`judge.RuleJudge`):

1. **Exact.** The item's barcode is one of the canonical's reference barcodes
   (`soft_attrs.barcodes`): level `exact`, confidence 1.0, source `rule`.
2. **Critical veto.** The product type and every critical key of the product type
   (`product_type_rules.critical_keys`) that the canonical defines in `critical_attrs` are
   compared with the item's attributes. Any known value that differs removes the candidate. It can
   never qualify at "any brand", or at all: 3% vs 1% milk, fresh vs frozen salmon, soy vs almond
   drink, cola vs cola zero, tuna in oil vs in water. The 1% item maps to the 1% canonical instead.
3. **Soft check.** Soft keys (`soft_keys`) the canonical defines are compared, brand keys
   excluded ("any brand" means the brand may differ). All equal or unknown: `any_brand`. Any
   difference (500 g vs 250 g, strawberry vs natural): `close`. Pack sizes are compared in g/ml.

When several candidates survive, the tighter level wins, then the higher confidence.

**Confidence** mixes similarity and attribute agreement:

```
sim_score  = clamp((similarity - sim_floor) / (sim_ceil - sim_floor), 0, 1)
attr_score = (agreed + 0.4 * unknown) / checked     # checked = product type + critical keys
confidence = 0.4 * sim_score + 0.6 * attr_score
```

`sim_floor`/`sim_ceil` default to 0.25/0.75, calibrated for `HashEmbedder` on the synthetic set;
recalibrate them on the real gold set for BGE-M3. The confidence is capped at 0.85 (review, never
auto-accepted) when any critical value of the item is unknown, when the product type has no rule,
or when the runner-up at the same level is within 0.03 (ambiguous).

| Confidence | Route | `item_canonical` |
|---|---|---|
| >= 0.90 | auto-accept | mapped, `needs_review = false` |
| 0.60 to < 0.90 | review queue | mapped, `needs_review = true` |
| < 0.60 | reject | no row (any earlier machine row is removed) |

Every mapping row carries `flex_level`, `confidence` and `source` (`rule` for `RuleJudge`,
`model` for `LLMJudge`, `human` from the review UI). The plain-words reason (which attributes
matched, which vetoed) is on the `MatchDecision`; it is not stored (no column), so the review UI
recomputes it.

**LLM judge** (`judge.LLMJudge`): Claude (`claude-sonnet-5-5` by default, `$MATCH_JUDGE_MODEL`)
chooses among the candidates that survived the hard rules, with structured output
(`output_config.format` JSON schema: `canonical_id`, `flex_level`, `confidence`, `reason`) and
server-side refusal fallback. It never sees vetoed candidates, cannot return one, cannot claim a
tighter level than the rules allow, and its confidence goes through the same bands (capped when a
critical value is unknown). Tests replay recorded-shape responses through a stub client; no test
touches the network. It has not been evaluated: there is no API key in the build environment.

**Choice of judge.** `RuleJudge` is the default (`--judge rule`). Its numbers are below. The LLM
judge is wired and tested but unmeasured; compare both on the real gold set before choosing, and
record the result here. A cross-encoder was not built: the rule judge plus review covers the MVP
catalog, and the LLM judge is the planned upgrade for the hard tail.

## Attributes before extraction lands

The judge needs item attributes. They come from `item_attributes` (the extraction pipeline, #25).
When an item has no row there, `match.fallback_attributes` derives a minimal set from the name:
fat percent (`3%`), state words (טרי, קפוא, ...), pack size and unit (`1 ליטר`, `6*1.5 ל'`,
`250 גרם`), "zero"/"diet" as sugar-free, and product type, category and variety from a keyword
`Lexicon`. The only lexicon so far is the gold set's (`gold_catalog.yaml`, `lexicon`), which the
evaluation uses and `smartcart-catalog judge --gold-lexicon` can use. Without a lexicon the
product type is unknown, so nothing but barcode matches is auto-accepted: everything else goes
to review, which is the safe failure.

## Step E: review UI (#38)

```
uv run smartcart-catalog review        # or: uv run streamlit run services/catalog/smartcart_catalog/review_app.py
```

Needs `DATABASE_URL` with write access to `item_canonical` and `gold_pairs`. Tabs:

- **Review queue**: every `needs_review` mapping, items users reported as "not a good
  substitute" first (marked), then by canonical `rank` (best sellers first), then confidence.
  Each row shows the item name, chain, barcode, extracted attributes and their source, the block,
  the top candidates with similarity and the judge's reason for each (vetoes included).
  Actions: **Accept** (optionally at another level), **Reject**, **Re-map** to another candidate.
- **Best sellers (top 300)**: for the 300 lowest `rank` canonicals, mapped items, human-reviewed
  items and pending ones. Launch criterion: every one fully human-reviewed.
- **Feedback**: rejection rates per category and level.

Every decision writes `item_canonical` with `source = 'human'`, `reviewed_by`, `reviewed_at`
(and `confidence = 1`) and records the pair in `gold_pairs` (`any_brand`/`close`/`exact` on accept,
`no_match` on reject, note `review: ... by <reviewer>`), so human decisions grow the gold set. A
reject has no row to keep in `item_canonical` (its `flex_level` cannot say "no match"), so the
`no_match` gold pair is what stops the judge from re-creating it. The query and command functions
(`review_queue`, `explain`, `bestseller_status`, `accept`, `reject`, `remap`) are tested without
Streamlit in `tests/test_match_review.py`.

## Feedback loop (#43)

`feedback.record_feedback(conn, user_id, canonical_id, original_item_id, substitute_item_id,
verdict)` is the write path for the API (`verdict` is `not_good`, `kept_original` or `accepted`).
It inserts `substitution_feedback` and returns the mapping's level and confidence at that moment.
On `not_good` it sets `needs_review = true` on the (substitute item, canonical) mapping and
nothing else: a report alone never changes a mapping; a human decides in the review UI, where
the item appears first with a feedback marker. `rejection_rates` gives the rate per category and
level; `feedback_gold_candidates` lists reported pairs not yet in `gold_pairs` as candidate
`no_match` pairs for a human to confirm (a user report is not ground truth). `user_id` is
optional; no location is stored.

## Evaluation (#38)

```
uv run smartcart-catalog evaluate --fail-below 0.98
uv run python -m smartcart_catalog.cli_matching evaluate --fail-below 0.98   # until cli.py registers it
```

One command loads the gold set (chain `gold`, missing taxonomy, rules and canonicals, and
`gold_pairs`; idempotent), embeds what is missing, runs blocking, retrieval and the judge on every
gold item, prints precision and recall per level as separate numbers plus retrieval recall@k,
and saves the metrics in `match_runs` (`kind = 'evaluate'`) so runs can be compared over time.
`--fail-below` exits 1 when precision at "any brand" is below the threshold (or undefined).
`.github/workflows/matching-eval.yml` runs it on every change under `services/catalog/**` or
`data/gold/**` against the Supabase Postgres image, after checking that the committed gold files
match their generator, and puts the report in the job summary.

Definitions (`evaluate.py`): levels nest (an exact match also qualifies at "any brand" and
"close"). Only auto-accepted decisions are counted as predictions; review-queue and rejected
decisions are abstentions, because they cannot put a false match in front of a user.
Precision@L is the share of predictions at L (or tighter) whose gold label qualifies at L. A
prediction to a canonical with no gold pair for that item counts as wrong. Recall@L is the share
of gold items with a pair qualifying at L that were predicted correctly at L. Recall@k is the
share of items with a positive pair whose positive canonical is among the k retrieved
candidates. `gold_pairs` rows from human review count too.

**Measured on the synthetic gold set** (RuleJudge, HashEmbedder, k = 10, 2026-10-07):

| Level | Precision | Recall | Served predictions | Gold items |
|---|---|---|---|---|
| exact | 1.0000 | 1.0000 | 100 | 100 |
| any_brand | 1.0000 | 0.8079 | 530 | 656 |
| close | 1.0000 | 0.7546 | 609 | 807 |

Retrieval recall@10: 0.9988. Of 831 items, 609 auto-accepted, 197 to the review queue, 25
unmapped (the 24 orphans, correctly, and one other item). If the review queue were
auto-accepted, precision at "any brand" would be 0.9939: the review band is what keeps the rest
out. Why these numbers are optimistic: the labels, the item names and the fallback lexicon come
from the same generator; the hash embedder benefits from template names sharing substrings with
canonical names; and real chain names are messier (truncation, internal codes, typos). Treat
them as a regression baseline for the pipeline, not as the D5 target being met.

## Fine-tuning trigger

Retrieval is the recall ceiling: the judge can only accept what top-k returns. On the **real**
gold set with BGE-M3: if recall@10 is below **0.95** (`evaluate.RECALL_AT_K_TRIGGER`), or recall
at "any brand" is below 0.80 with most misses being retrieval misses, plan supervised contrastive
fine-tuning of the embedder on our labeled pairs (Peeters and Bizer, supervised contrastive
learning for product matching, a published result), with `gold_pairs` positives and the
`no_match` hard negatives (3% vs 1%, fresh vs frozen) as training pairs. The research's verified
benchmark says Hebrew retrieval is mediocre out of the box (multilingual-e5 0.397 and
NeoDictaBERT 0.404 NDCG@20 on the Hebrew retrieval challenge). The 0.95 and 0.80 thresholds are
our planning choices (estimates), not research numbers. Fine-tuning itself is out of scope for
phase 1 (#29).

## CLI

`cli_matching.register(app)` adds these to the `smartcart-catalog` app (`cli.py`):

| Command | What it does |
|---|---|
| `embed [--target canonicals\|items\|all] [--embedder hash\|bge-m3] [--force]` | Batch embeddings, idempotent |
| `judge [--judge rule\|llm] [--k 10] [--item-id N ...] [--dry-run] [--gold-lexicon]` | Match embedded items, write `item_canonical` |
| `evaluate [--fail-below 0.98] [--embedder] [--judge] [--k] [--gold-dir] [--no-load] [--json]` | Gold-set metrics, saved to `match_runs` |
| `review [--port 8502]` | Streamlit review UI |

The database is `$DATABASE_URL`; the embedder defaults to `$EMBEDDER` (`hash` when unset).

## Contract changes requested

The schema and `models.py` were not changed by this work; these would remove workarounds:

- `NormalizedItem.barcode` (or a barcode argument on `Judge.judge`): the exact rule needs it;
  today `RuleJudge`/`LLMJudge` take `barcode=` as an extra keyword.
- `CanonicalProduct.reference_barcodes` (or a `canonical_barcodes` table): reference barcodes
  live in `soft_attrs.barcodes` for now.
- `canonical_products.embedding_model text`: the model and name fingerprints live in `match_runs`.
- `item_canonical.reason text`: the judge's reason is recomputed by the review UI.
- A way to store a human "not this canonical" decision in `item_canonical` (a `rejected` status or
  `flex_level` allowing `no_match`): today the `no_match` row in `gold_pairs` carries it.
- `substitution_feedback`: add `list_item_id`, `flex_level` and `match_confidence` columns (#43
  context), and RLS (owner reads and inserts own rows) like the other user tables.
- `Attributes` has no key for a milk-alternative base or a variety; the gold set uses distinct
  product types (soy vs almond drink) and `flavor` (bread, rice, tuna variety).
