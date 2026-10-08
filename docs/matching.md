# Matching: embeddings, blocking, judge, review, evaluation

How a chain item becomes "this is canonical product X, at flexibility level Y, with confidence Z",
how a human corrects it, and how we measure it. Covers issues #29 (embeddings, blocking, HNSW),
#33 (match judge with hard rules), #38 (review UI, gold set, evaluation harness) and #43 (user
feedback loop). Decisions D4 (three flexibility levels) and D5 (precision over recall) govern
everything here; architecture section 3 steps C to E describe the plan this implements.

Code: `services/catalog/smartcart_catalog/` — `embed.py`, `block.py`, `judge.py`, `match.py`,
`evaluate.py`, `review_app.py`, `feedback.py`, `cli_matching.py`. Gold set: `data/gold/`.

> **The gold set is synthetic.** `data/gold/` holds 2,523 pairs over 857 items and 58 canonicals,
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
   (+ reason)              (+ reason)                 │        (accept, or human_rejected=true)
          │                                           ▲
          └── user: "not a good substitute" ──> needs_review=true (feedback marker)
```

`apply_decisions` is the only writer of machine mappings. It is idempotent, stores the judge's
reason in `item_canonical.reason`, never touches a row with `source = 'human'`, never re-creates
a pair a human rejected (`human_rejected = true`), and keeps `needs_review` set while a user
report on that mapping is unresolved.

## Step C: embeddings and blocking (#29)

**Embedders** implement the `Embedder` protocol (`models.py`):

| Name | Use | Notes |
|---|---|---|
| `hash` (`HashEmbedder`) | tests, CI, local dev | Deterministic 1024-dim signed feature hashing of character 2-4-grams and words of the normalized text (final letters folded, nikud and quotes stripped, digits and `%` kept), L2-normalized. Similar strings get similar vectors; there is no semantics. |
| `bge-m3` (`BgeM3Embedder`) | production | BGE-M3 dense vectors via sentence-transformers (`uv sync --all-packages --extra embed`; the extra belongs to `smartcart-catalog`, so a bare `uv sync --extra embed` at the workspace root fails), imported lazily, model name configurable (`$EMBEDDING_MODEL`, default `BAAI/bge-m3`). Not runnable in the build sandbox (Hugging Face is unreachable there); the "BGE-M3 evaluation" workflow runs it on a GitHub runner (below). |

**Measuring BGE-M3 (issue #29, `.github/workflows/bge-eval.yml`).** A `workflow_dispatch` job, also
run weekly (Mondays 02:41 UTC), on the same Supabase Postgres image as the gate. It installs the
`embed` extra, caches the model under `~/.cache/huggingface` (key: the model name), and runs
`scripts/unblock/bge_eval.py`, which calls the real CLI three times: `evaluate --embedder hash`
(loads the gold set exactly as `matching-eval.yml` does and gives the hash baseline on the same
items), `embed --target all --embedder bge-m3` (timed: the reported embed time excludes the model
download, which a separate step does first), and `evaluate --no-load --embedder bge-m3` with the
gate's judge and k (rule, 10). The report, in the job summary and the `bge-eval-report` artifact
(Markdown and JSON, 30 days), gives precision and recall per level for both embedders, retrieval
recall@10, the embed time, the model revision (the commit in the Hugging Face cache) and the
sentence-transformers and torch versions, then compares any-brand precision with the 0.98 gate and
recall with the fine-tuning triggers below. It never fails on a number: it is a measurement, and
the gold set is still synthetic. Inputs: `max_items` (0 for all 857 gold items; a round-robin
sample across departments otherwise, e.g. 100 for a quick run) and `model` (any 1024-dimension
sentence-transformers model). Locally, on a fresh migrated database:
`BGE_EVAL_EMBEDDER=hash uv run --no-sync python scripts/unblock/bge_eval.py --max-items 120`
reproduces the flow without torch. Two cautions when reading the first BGE-M3 numbers:
`sim_floor`/`sim_ceil` are calibrated for the hash embedder, so a change in precision or in the
review band can be calibration rather than retrieval; and recall@10 is the number that speaks to
the embedder itself. No BGE-M3 result is recorded here until the workflow has run; paste the
table from its summary with the run link when it has.

**Model name (issue #102).** Every embedder exposes `model_name: str` (the `Embedder` protocol in
`models.py`; no separate `name` attribute was added). It names the vector space, and it is the
value `embed` writes to both `canonical_products.embedding_model` and `item_embeddings.model`:

| Embedder | `model_name` | Constant |
|---|---|---|
| `get_embedder("hash")`, `HashEmbedder()` | `hash-ngram-2-3-4-v1` | `embed.HASH_MODEL_NAME` |
| `get_embedder("bge-m3")`, `BgeM3Embedder()` | `BAAI/bge-m3` (or `$EMBEDDING_MODEL`) | `embed.BGE_M3_MODEL_NAME` |

`tests/test_embed.py` pins both strings: changing one means re-embedding every row. A reader that
compares a query vector with stored vectors (the API's `/search`) must embed the query with the
same embedder (`smartcart_catalog.embed.get_embedder(...)`) and filter
`canonical_products.embedding_model = embedder.model_name` (and `item_embeddings.model` for item
vectors). Another implementation of the same idea, with another name, is another vector space.
The catalog's own top-k does the same: it compares an item only with canonicals embedded by the
item's model (`cp.embedding_model = e.model`), so a half-finished re-embed returns no candidates
instead of distances across two spaces.

**Batch jobs** `embed_canonicals` and `embed_items` are idempotent: an item already embedded with
the same model and not updated since is skipped; a canonical is re-embedded only when its vector
is missing, its `canonical_products.embedding_model` differs from the embedder's model (or is
NULL, as on rows embedded before the column existed), or its name changed. The model sits next to
each vector (`canonical_products.embedding_model`, `item_embeddings.model`), so a model change is
visible on the row without reading `match_runs` (issue #92); anything that compares a query
vector with these vectors must use the same model. Name changes are still detected through a
name fingerprint kept in the last canonical embed run's `match_runs` metrics, because the
`updated_at` trigger fires on the embedding update itself. Each run writes a `match_runs` row
(`kind = 'embed'`) with counts.

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

1. **Exact.** The item's barcode (`NormalizedItem.barcode`) is one of the canonical's reference
   barcodes (`CanonicalProduct.reference_barcodes`, the `canonical_products.reference_barcodes`
   column): level `exact`, confidence 1.0, source `rule`.
2. **Critical veto.** The product type and every critical key of the product type
   (`product_type_rules.critical_keys`) that the canonical defines in `critical_attrs` are
   compared with the item's attributes. Any known value that differs removes the candidate. It can
   never qualify at "any brand", or at all: 3% vs 1% milk, fresh vs frozen salmon, soy vs almond
   drink (the product type, and `base` where a rule lists it), cola vs cola zero, tuna in oil vs in
   water. The 1% item maps to the 1% canonical instead.
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

Every mapping row carries `flex_level`, `confidence`, `source` (`rule` for `RuleJudge`,
`model` for `LLMJudge`, `human` from the review UI) and `reason`: the plain-words explanation
from the `MatchDecision` (which attributes matched, which vetoed), stored by `apply_decisions` and
shown as is by the review UI. A human decision prefixes its own note (`human: accepted by noa |
judge: ...`).

**Human rejections.** A reviewer's "not this canonical" keeps the row with
`human_rejected = true`, `source = 'human'`, `confidence = 0` and `needs_review = true` (the last
two so that a reader that only filters `NOT needs_review` or a confidence floor still never
serves it). `match.load_items` collects each item's rejected canonicals and `match_item` removes
them from the retrieved candidates (fetching extra rows so k remain) before the judge runs, so
the judge never proposes them again and decides among the others; `apply_decisions` refuses the
pair as well. A rejection is not a human mapping: the item can still be matched to another
canonical. **Every reader of `item_canonical` must filter `NOT human_rejected`.**

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
`Lexicon`. For the lexicon's `base_types` the plant base comes from its `bases` keywords in the
name (the first one, skipping one right after "בטעם", which is a flavor), else from the type's
`implied` base (issue #102). The only lexicon so far is the gold set's (`gold_catalog.yaml`, `lexicon`), which the
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
and records the pair in `gold_pairs` (`any_brand`/`close`/`exact` on accept, `no_match` on reject,
note `review: ... by <reviewer>`), so human decisions grow the gold set. Accept sets
`confidence = 1` and clears `human_rejected`; reject sets `human_rejected = true` (see "Human
rejections" above). `gold_pairs` is used for evaluation only: it no longer decides what the judge
may write. The queue shows the stored judge reason; `explain` re-runs retrieval only to list the
candidates a reviewer can re-map to (rejected canonicals excluded). The query and command
functions (`review_queue`, `explain`, `bestseller_status`, `accept`, `reject`, `remap`) are
tested without Streamlit in `tests/test_match_review.py`.

## Feedback loop (#43)

`feedback.record_feedback(conn, user_id, canonical_id, original_item_id, substitute_item_id,
verdict, *, list_item_id=None, flex_level=None, match_confidence=None)` is the write path for the
API (`verdict` is `not_good`, `kept_original` or `accepted`). It inserts `substitution_feedback`,
with the context columns `list_item_id` (the list line), `flex_level` (the level the list asked
for) and `match_confidence` (the confidence shown) when they are given (issue #92), and returns
the mapping's level and confidence at that moment. A human-rejected pair is never flagged. The
table has row level security since migration 20261008100000 (a signed-in user reads and inserts
only their own rows); the catalog jobs run as a role that bypasses it.
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

**Measured on the synthetic gold set** (RuleJudge, HashEmbedder, k = 10, 2026-10-07, after
issue #102). These are synthetic-gold-set numbers, a pipeline regression baseline, **not
evidence** of precision on real chain data:

| Level | Precision | Recall | Served predictions | Gold items |
|---|---|---|---|---|
| exact | 1.0000 | 1.0000 | 104 | 104 |
| any_brand | 1.0000 | 0.8125 | 546 | 672 |
| close | 1.0000 | 0.7611 | 634 | 833 |

Retrieval recall@10: 0.9988. Of 857 items, 634 auto-accepted, 198 to the review queue, 25
unmapped (the 24 orphans, correctly, and one other item). If the review queue were
auto-accepted, precision at "any brand" would be 0.9940: the review band is what keeps the rest
out. Run the same way as `.github/workflows/matching-eval.yml` (fresh database, `EMBEDDER=hash`,
`python -m smartcart_catalog.cli_matching evaluate --fail-below 0.98`); exit 0.

Before issue #102, on the earlier set (2,419 pairs, 831 items, same day): exact 1.0000 / 1.0000
(100 served), any_brand 1.0000 / 0.8079 (530 of 656), close 1.0000 / 0.7546 (609 of 807),
recall@10 0.9988, 609 auto-accepted, 197 review, 25 unmapped; review-queue-accepted any_brand
precision 0.9939. Those numbers were also identical after the issue #92 contract changes.

**What issue #102 changed in the gold set.** No existing pair changed label and none was removed:
every one of the 124 earlier pairs that crosses a base boundary (a soy item against the almond or
oat canonical, the rice drink orphans against all three) was already `no_match`, because the
plant drinks are separate product types. The type therefore did all the vetoing and `base` never
decided a pair. `BASE_SPECS` in `build_gold.py` add 26 items and 104 pairs on two plant yogurts
that share one product type (`plant_yogurt`) and differ only by base (soy, coconut): 4 exact,
12 any_brand, 10 close and 78 no_match, of which 26 are base-boundary negatives that only the
`base` key can veto (the other 52 are the plant yogurt against the dairy yogurt and a random
dairy canonical). The soy yogurt "בטעם קוקוס" variant checks that a base word after "בטעם" is
read as a flavor. All 150 base-crossing pairs are `no_match` (`tests/test_gold.py`). The new
items are generated after the others with their own random stream, so the earlier 2,419 pairs
are byte-identical. Why these numbers are optimistic: the labels, the item names and the fallback lexicon come
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

## Contract changes (issue #92, done)

The workarounds this work started with are gone; migration 20261008100000 added the columns.

| Before | Now |
|---|---|
| `RuleJudge`/`LLMJudge` took `barcode=`; extractors took a `context` map | `NormalizedItem` carries `chain_id`, `chain_name`, `manufacturer`, `barcode`, `raw_name`, `issues`; the `Judge` and `Extractor` protocol signatures are unchanged |
| Reference barcodes in `soft_attrs.barcodes` | `CanonicalProduct.reference_barcodes` and `canonical_products.reference_barcodes`; `seed` loads them from `canonicals.yaml`, the gold set from `gold_catalog.yaml` |
| Embedding model in `match_runs` only | `canonical_products.embedding_model`, compared row by row |
| Judge reason recomputed by the review UI | `item_canonical.reason` |
| A `no_match` row in `gold_pairs` blocked the judge | `item_canonical.human_rejected`; `gold_pairs` is evaluation only |
| `substitution_feedback` without context or RLS | `list_item_id`, `flex_level`, `match_confidence`; RLS |
| Plant-drink base only as separate product types | `Attributes.base` (soy, almond, oat, rice, coconut) and `Attributes.variety` |

What readers outside the catalog must do: filter `NOT human_rejected` on every `item_canonical`
read, and compare query embeddings only with canonicals whose `embedding_model` is the query
embedder's `model_name` (see "Model name" under step C).
