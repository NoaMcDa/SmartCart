# Canonical catalog: taxonomy, canonical products, normalization, attribute extraction

Phase 1, Track A, first half (issues #10, #15, #20, #25). This covers matching steps A and B of
`architecture.md` section 3 and the data the later steps block and judge on. Embeddings, blocking,
the judge, the review UI and the evaluation harness (steps C to E) are documented with their own
modules.

Labels follow `docs/README.md`: **verified** means a cited source or a measured result; **estimate**
means a judgement, not a measurement.

```
items (ingest) ──► normalize.py ──► NormalizedItem ──► extract/ (rule | claude) ──► item_attributes
                    step A                               step B                     status ok/retry/failed
data/taxonomy.yaml ─┐
data/product_type_rules.yaml ─┼─► seed.py ──► taxonomy, product_type_rules, canonical_products
data/canonicals.yaml ─┘
```

| Piece | Where |
|---|---|
| Seed files (source of truth) | `data/taxonomy.yaml`, `data/product_type_rules.yaml`, `data/canonicals.yaml` |
| Load, validate, upsert | `services/catalog/smartcart_catalog/taxonomy.py`, `seed.py` |
| Rule normalization | `services/catalog/smartcart_catalog/normalize.py` |
| Attribute extraction | `services/catalog/smartcart_catalog/extract/` (`schema.py`, `rule.py`, `claude.py`, `queue.py`, `base.py`) |
| Configuration | `services/catalog/smartcart_catalog/settings.py` |
| Command line | `smartcart-catalog` (`cli.py`) |
| Tables | `supabase/migrations/20261007100000_catalog_v1.sql` |

## 1. Taxonomy

Four levels: department > category > product type > optional sub-type. The canonical product
itself is the conceptual fourth level of the research; it lives in `canonical_products` and points
at a level 3 (or 4) node through `taxonomy_id`.

**Ids.** Every node has a stable dotted slug: `dairy`, `dairy.milk`, `dairy.milk.fresh`. The parent
is the id without its last segment and the level is the number of segments, so structure and ids
cannot drift apart. Segments are lowercase ASCII (`[a-z][a-z0-9_]*`). Each node has a Hebrew
`name_he` (required, the display name) and an English `name_en`. File order is the `sort` column.

**Departments.** The research says the taxonomy starts from Hazol's 19 categories (research section
4.3; Hazol's catalog size, 171,173 products, is verified there) but it does not list those
categories, and we did not copy them from the Hazol site. The 19 departments below are our own list,
seeded from the department names in the phase 1 brief and adjusted where a supermarket shopper would
look elsewhere (design choice, not a research fact):

- eggs are folded into dairy ("מוצרי חלב וביצים"), as Israeli chains shelve them;
- a deli and chilled salads department is added (hummus, tahini salad, cold cuts are staples that fit
  neither dairy nor meat);
- household goods are merged into cleaning ("ניקיון ומוצרים לבית"), which keeps the count at 19.

| id | Hebrew | English | Canonicals | Nodes at level 3+ |
|---|---|---|---|---|
| dairy | מוצרי חלב וביצים | Dairy and eggs | 37 | 21 |
| meat | בשר ועוף | Meat and poultry | 18 | 10 |
| fish | דגים | Fish | 7 | 4 |
| deli | מעדנייה וסלטים | Deli and chilled salads | 7 | 5 |
| produce | פירות וירקות | Fruit and vegetables | 34 | 11 |
| bakery | לחם ומאפים | Bread and bakery | 9 | 4 |
| pantry | מזון יבש ובישול | Pantry and dry goods | 49 | 18 |
| canned | שימורים | Canned and jarred | 12 | 6 |
| frozen | קפואים | Frozen | 16 | 6 |
| beverages | משקאות | Beverages | 16 | 12 |
| snacks | חטיפים ומתוקים | Snacks and sweets | 13 | 7 |
| baby | תינוקות | Baby | 1 | 1 |
| cleaning | ניקיון ומוצרים לבית | Cleaning and household | 10 | 9 |
| paper | נייר וחד-פעמי | Paper and disposables | 8 | 7 |
| toiletries | טיפוח והיגיינה | Toiletries and cosmetics | 5 | 4 |
| health | בריאות ופארם | Health | 0 | 0 |
| pets | חיות מחמד | Pets | 0 | 0 |
| holiday | כשר לפסח ומוצרי חג | Passover and holiday | 1 | 1 |
| alcohol | יין ואלכוהול | Wine and alcohol | 2 | 2 |

203 nodes: 19 departments, 56 categories, 126 product type nodes, 2 sub-types. The staples (dairy,
bakery, pantry, beverages, produce, meat, fish, cleaning) reach product type level; health and pets
are shallow on purpose (out of scope of the MVP basket, issue #10).

**Validation** (`taxonomy.py`, run by `smartcart-catalog seed` and the tests): ids well formed and
unique, every parent exists, level 1 to 4, exactly 19 departments, Hebrew name present.

**Query.** All canonicals under a node: `taxonomy.canonicals_under(conn, "dairy.milk")`, which is

```sql
SELECT id, slug FROM canonical_products
WHERE taxonomy_id = 'dairy.milk' OR taxonomy_id LIKE 'dairy.milk.%'   -- whole segments only
ORDER BY rank;
```

### How to add or change a node

1. Edit `data/taxonomy.yaml`. Add the node under its parent; keep departments first.
2. Never rename or reuse an id: `canonical_products.taxonomy_id` and every stored `category_path`
   point at it. To retire a node, stop pointing canonicals at it and leave it in the file. Seeding
   never deletes; it reports rows that are in the database but not in the file.
3. `uv run smartcart-catalog seed --check` validates the three files together, then
   `uv run pytest services/catalog` and open a pull request.
4. **Who approves:** the catalog owner (the maintainer) reviews every taxonomy change. A change at
   level 1, or to a node that already has canonicals or matched items, also needs the domain-aware
   reviewer of issue #15, because it moves products between blocks of the matcher.
5. After merge, `smartcart-catalog seed` on the server. It is idempotent.

## 2. Canonical products and product type rules

`data/canonicals.yaml` holds **245 canonical products** (`is_mvp: true`), inside the 150-300 range
of the plan (the range is the research's plan, not a measured result). Each has a slug, Hebrew
display name, taxonomy node, product type, base unit, critical and soft attributes, and a rank.
A canonical may also list `reference_barcodes` (issue #92): the barcodes that are exactly this
product. `seed` stores them in `canonical_products.reference_barcodes` (a text array with a GIN
index) and the judge's exact rule reads them; they are no longer kept in `soft_attrs`. Validation
requires 8 to 14 digits and no barcode on two canonicals. A file entry without the key leaves the
stored barcodes untouched, so barcodes added later (from review or a barcode import) survive a
re-seed. The shipped `canonicals.yaml` lists none yet: reference barcodes come from loaded data.

### Choosing the canonicals and the ranking (estimate)

There is no basket-frequency data yet: the catalog is not loaded and no receipts exist. The list and
the rank are therefore a **judgement, marked estimate**, built from:

- the research: the staples it names, the 3% versus 1% milk, fresh versus frozen salmon and soy versus
  almond drink examples, and the 67-item press basket (verified as a survey, research section 3.1;
  its item list is not in the research, so it informed the scope, not the order);
- general knowledge of an Israeli weekly shop: dairy, bread, eggs, produce, chicken, hummus, rice and
  pasta, oil, sugar, tuna, water, snacks, cleaning and paper basics.

Method: each product was placed in one of five frequency tiers (tier 1, 24 products: bought by most
households most weeks, such as fresh milk 3%, cottage 5%, eggs L, tomatoes, chicken breast, standard
bread; tier 2, 54; tier 3, 77; tier 4, 75; tier 5, 15: occasional), then ordered by hand inside the
tier. Rank 1 is the most common. **Replace the rank with a measured one** (item frequency across
chains' catalogs and promos, then search and list data once users exist) before using it in any
claim; the rank only orders review work today.

Deliberately left out: diapers (size classes need their own attributes), baby formula, pets and
health, most cosmetics (D4 defaults them to "exact" matching, so canonicals add little), and the
long tail. Every MVP canonical is within the 300 best-sellers that get mandatory human review
(architecture step E), so the whole list is review-mandatory.

### Critical and soft attributes

`data/product_type_rules.yaml` defines, for each of the **222 product types**, which attributes must
be equal at "any brand" (`critical_keys`) and which may differ at "close substitute" (`soft_keys`).
The product type itself is always critical, so different types are never merged. Stored in
`product_type_rules` (text arrays) for the judge; keys are `Attributes` fields.

| Pattern | Product types | Critical | Example |
|---|---|---|---|
| Fat defines the product | milk types, cottage, white, yellow, bulgarian, safed cheese, labane, creams | `fat_pct` (milk also `state`) | 3% and 1% milk are two canonicals |
| Fresh versus frozen or canned | meat, fish, produce, peas, corn, chickpeas, frozen vegetables | `state` | fresh and frozen salmon fillet; frozen and canned peas |
| Flavor defines the product | fruit yogurt, desserts, jam, bisli, chips, chocolate, burekas, ice cream, soup powder | `flavor` | strawberry and peach yogurt |
| Plain yogurt, cream cheese | yogurt, cream_cheese | `fat_pct`, `flavor` | plain yogurt 3% |
| Type alone | bread, rice, pasta, oils, sauces, drinks, non-food | none beyond the type | white and whole wheat flour are separate types |
| Base of a plant drink | soy_drink, almond_drink, oat_drink | `base` | `soy-drink` has `base: soy`; an item read as `base: almond` is vetoed even if its type was guessed wrong |

Soft keys are `pack_size` and `brand` everywhere, plus `fat_pct` or `flavor` where they are not
critical.

**`base` and `variety`** (issue #92). `Attributes.base` is what a plant-based drink or milk
alternative is made from (`soy`, `almond`, `oat`, `rice`, `coconut`); `Attributes.variety` is a
named variety that is not a flavor (`barista`, `protein`). Both are attribute keys, so a product
type rule may list them: `base` as a critical key vetoes soy against almond even inside one
product type, `variety` as a soft key turns a barista drink into a "close" substitute.

**`base` is critical (issue #102, 2026-10-07).** The critical attribute list per pattern is in
the table above; `base` is now a critical key of the three plant drink types, which keep their
separate product types (the type already vetoes soy against almond; the base is the second
lock, for an item whose type was guessed wrong, or a rice or coconut drink, which has no type of
its own and is vetoed by its base). Three canonicals changed their critical attributes, which
the seed validation requires to equal the type's critical keys:

| Canonical | `critical_attrs` before | after |
|---|---|---|
| `soy-drink` | `{}` | `{base: soy}` |
| `almond-drink` | `{}` | `{base: almond}` |
| `oat-drink` | `{}` | `{base: oat}` |

No canonical was added or removed (still 245), slugs and ranks are unchanged, and no two
canonicals are indistinguishable at "any brand". The three types also declare
`implied: {base: ...}`, and `seed` now checks that a critical value a type implies is carried by
one of its canonicals (`seed.implied_conflicts`), so the extractor's default can never veto every
canonical of its own type. Other types were checked and left alone: there are no plant yogurts
or plant flours in the MVP list (the two flours are wheat, split by type), and soy sauce, soybean
oil, rolled oats and the rice types are not plant-milk products. To keep plant products out of
the dairy types, `milk`, `milk_long_life`, `milk_lactose_free`, `yogurt` and `yogurt_fruit` now
exclude the plant words (סויה, שקדים, שיבולת, קוקוס, אורז where they apply): "משקה סויה ללא
לקטוז" used to tie with the lactose-free milk keyword and was typed as cow's milk, and "יוגורט
סויה" was typed as a dairy yogurt. `oat_drink` gained the keywords "חלב שיבולת (שועל)", which
the rolled oats type used to win. The committed SEO snapshot was regenerated (`docs/seo.md`); the
three drinks are ranked 141 to 143, beyond the 130 product pages of the page budget, so they
appear as rows on `/c/beverages-plant_drinks`, not as pages of their own.

Kosher and diet flags are **not** critical keys: the chain files do not carry them
structurally, so extracted values are always unverified (`ALWAYS_UNVERIFIED`) and cannot gate a
match. They are user preference filters (features.md) instead. This differs from the glossary in
`docs/README.md`, which lists "kosher level" among critical attributes.

**Validation** (`seed.py`): critical attributes name exactly the type's critical keys, values pass the
`Attributes` model (for example `state` is one of fresh, frozen, chilled, canned, dry), soft
attributes are soft keys, slugs unique, ranks 1..N, every product type has a canonical, **no two
canonicals share product type and critical values** (they would be indistinguishable at "any brand"),
and a critical value a type implies (`implied: {base: soy}`) is carried by one of its canonicals.

### Base units

`100ml` for liquids, `100g` for packaged solids, `unit` for counted goods (eggs, pita, rolls, toilet
rolls, tea bags, herbs by the bunch, lettuce), `kg` for goods sold by weight (fresh meat, fish and
produce). Frozen meat and fish are packed, so their canonicals are `100g`. kg and 100g are the same
dimension: the blocking step should compare dimensions (mass, volume, count), not the raw base unit.

### Open: domain-aware reviewer sign-off

Issue #15 requires a domain-aware reviewer to sign the list off before matching builds on it. That
review has **not happened**. Checklist for the reviewer: the fat percentages (for example lactose-free
milk 2%, yellow cheese 28% and 9%, bulgarian 5% and 24%, whipping cream 32% and 38%) match common
Israeli SKUs; nothing important is missing from tiers 1 and 2; the critical keys per type are right
(for example whether "sliced" should split yellow cheese); the ranks look plausible.

## 3. Rule normalization (step A)

`normalize(item) -> NormalizedItem` for any `items` row (an `ItemRecord`, a dict row). Pure and
cheap, so consumers call it directly; `smartcart-catalog normalize` runs it over the table and
reports. `normalize_with_issues` also returns what was ambiguous.

The returned item carries the row's source fields as well (issue #92): `chain_id`, `chain_name`
(when the row has it), `manufacturer`, `barcode`, `raw_name`, and `issues` (the same list
`normalize_with_issues` returns). Extractors and judges read everything about an item from the
`NormalizedItem`; there is no side `context` map and no `barcode=` keyword any more. All of
these fields are optional, so a bare `{"raw_name": ...}` still normalizes.

1. **Clean the name.** Unify geresh and gershayim variants (`׳ ״ ’ ”` to `' "`), drop direction
   marks, expand abbreviations from the `ABBREVIATIONS` table, collapse whitespace. The table is
   extendable; add a row and a test.

   | Abbreviation | Expansion | Note |
   |---|---|---|
   | ש.ז. / ש.ז / ש"ז (also בש.ז.) | שמן זית | olive oil; general knowledge, reviewer to confirm |
   | מהד' | מהדורה | "מהד' מוגבלת", limited edition |
   | תפו"א | תפוחי אדמה | |
   | ק"ג, קג | קילוגרם | |
   | מ"ל | מיליליטר | |
   | גר', ג' after a number | גרם | ג' elsewhere (ג'בטה) is left alone |
   | ליט', ל' after a number | ליטר | |
   | יח', יחי' | יחידות | |

2. **Size.** Units convert to grams, milliliters or units (kg x1000, liter x1000). Sources in order:
   - the **name**, when it has a measure: `1 ליטר`, `250 גרם`, `1.5 ל'`, `1,5 ליטר`;
   - **multipacks** in the name: `6*1.5 ל'`, `4X250 מ"ל`, `4 x 330 מל`, `1.5 ליטר*6`, `250*4 מל`,
     `מארז 8 ... 150 גרם`, `מארז שישייה`, `זוג`; the per-piece size times the count is the total
     (`6*1.5 ל'` is 9000 ml);
   - the chain's **Quantity / UnitQty fields** when the name has no measure; then they are the pack
     total, and a count in the name (`4 יחידות`, `מארז 4`) splits it into pieces;
   - **counted goods**: `12 יח'`, `32 גלילים`, `72 מגבונים`, `100 שקיקים`.

   The fields win when the name is silent; the name wins when it has a measure. Fields of `1 יחידה`
   carry no size and are ignored next to a measure; `6 יחידות` next to `1.5 ליטר` makes a six-pack.
   A disagreement (fields 250 g, name 500 g; or ml against g) uses the name **and is reported**.
3. **Weighed goods.** `is_weighed` from the chain file, `במשקל` or `לק"ג` in the name, UnitQty in kg
   with quantity 1 (or none) and no size in the name, or a PLU-style item code (3 to 5 digits) with no
   size in the name. Weighed items are normalized as 1 kg with base unit `kg` and `is_weighed`; the
   chains publish their shelf price per kg.
4. **Unparseable.** No size anywhere: `quantity`, `total_quantity` and `base_unit` stay empty and the
   issue says "unparseable". Nothing is guessed.
5. **Unit price.** `unit_price(price, normalized) -> (Decimal, uom)` divides by the pack total: per
   100 g, per 100 ml, per unit, or per kg for weighed goods, whose price is returned as is and must be
   labeled estimated (D6, CLAUDE.md). It raises for an unparsed item.

Known limits: `מארז N ... S גרם` is read as N pieces of S (the common way chains write it, estimate);
when the Quantity field equals S it agrees with that reading, and when it equals N x S too. The test
names are realistic but not copied from loaded files (the ingest regression fixtures are synthetic
too); re-run `smartcart-catalog normalize` on the first real loads and turn its issue list into test
cases. Note that `prices.unit_price` is already filled by the ingest loader from the chains' own
published unit price; the name-based helper here is for the effective-price precompute and for items
whose published unit price is missing or wrong.

## 4. Attribute extraction (step B)

Per item, once: `{category_path, product_type, brand, is_private_label, fat_pct, state, flavor,
kosher, diet_flags, pack_size, unit, base, variety}` plus a confidence, stored in
`item_attributes`. `base` and `variety` were added in schema version 2 (issue #92); rows
extracted before simply lack them (unknown).

**Schema** (`extract/schema.py`): strict JSON schema, `additionalProperties: false`, every key
required, `null` for "not stated". `product_type` and `category_path` are enums built from the seed
files, so the model cannot invent a type the judge has no rule for; `flavor`, `diet_flags` and
`base` are closed vocabularies too. Output is validated with `jsonschema` and then the `Attributes` model.

**Extractors** (both implement the `Extractor` protocol, `extract(items)`, and read the chain,
manufacturer and raw name from each `NormalizedItem`):

- `RuleExtractor` (`extract/rule.py`), the default (`EXTRACTOR=rule`): keyword tables from
  `product_type_rules.yaml` pick the product type (whole-word match, longest keyword wins, excludes
  veto), regexes read the fat percentage (not cocoa or juice percentages), keyword lists give state,
  flavor, kosher text and diet flags, a brand list and per-chain private-label lists give brand and
  `is_private_label`. For plant drink types it fills `base` from the name (סויה or סוייה,
  שקדים, שיבולת שועל, אורז, קוקוס; the first one wins, and one right after "בטעם" is a flavor,
  not a base) or from the type itself; an untyped name that says it is a drink, a "milk" or a
  yogurt ("משקה אורז", "חלב קוקוס", "יוגורט סויה") gets its base too, so the base vetoes the
  plant drink canonicals it is not. `variety` comes from בריסטה / חלבון. Types may
  imply a value (milk without "עמיד" is fresh; produce is fresh). The
  private-label lists hold only the chains' own names for now (estimate); house-brand names must be
  collected from loaded data. Confidence is capped at 0.8.
- `ClaudeExtractor` (`extract/claude.py`): Message Batches API with `claude-sonnet-5-5` (decision
  D14). One request per item, `custom_id = item-<id>`, a cached system prompt with the instructions
  and both vocabularies, structured output through `output_config.format` with the schema, adaptive
  thinking with no budget at `effort: low`, `max_tokens` 1024. It submits a batch, polls until
  `ended`, and reads results keyed by `custom_id` (they arrive in any order). The deterministic size
  from step A overrides the model's `pack_size` and `unit`.

**Never trusted until valid.** A refusal, a cut-off answer (`max_tokens`), empty or malformed JSON,
a schema violation (an unknown product type, an extra key such as a model-supplied `verified_keys`),
an errored, canceled or expired request, or a missing result becomes an `ExtractionError`.

**Queue** (`extract/queue.py`). Pending items are those without an `item_attributes` row or with
`status = 'retry'`, read in id order in chunks of `EXTRACTION_BATCH_SIZE`.

| Outcome | status | attrs | verified_keys | confidence |
|---|---|---|---|---|
| valid attributes | ok | the set values | empty unless the source is `human` | extractor's |
| retryable error | retry | `{"_retry": {"reason", "attempts"}}` only | empty | NULL |
| non-retryable error, or `EXTRACTION_MAX_ATTEMPTS` (3) reached | failed | same as retry | empty | NULL |

`ok` and `failed` rows are never selected again, so a re-run skips done items and each item is
processed once; within a run an item is attempted at most once. Readers must use `status = 'ok'`
rows only. `verified_keys` is always empty for rule and model output: only a human verifies, and kosher
and diet flags stay unverified unless a human confirmed them (`ALWAYS_UNVERIFIED`); the UI shows
every other set key as "unverified" (D10).

**Cost tracking.** Every run writes a `match_runs` row (`kind = 'extract'`) with counts and, per
model batch, the input, output, cache-read and cache-write tokens the API reported and an estimated
USD figure. `smartcart-catalog cost-report` prints them. The USD figure is an **estimate** at
Sonnet 5.5 batch rates: $1 per million input tokens and $5 per million output tokens (50% of the $2 /
$10 list price), cache reads at 0.1x and cache writes at 1.25x input. The bill is the source of truth.

**Fixtures.** Tests never call the network. `tests/fixtures/claude/request_item.json` is the request
the extractor builds (prompt and schema as placeholders); `batch_results.json` holds results in the
documented batch result shape and parses with the SDK's own types. Both are hand-written because no
API key was available; re-record them from the first real batch.

## 5. Command line and settings

```
uv run smartcart-catalog seed [--check]              # validate data/*.yaml, upsert (idempotent)
uv run smartcart-catalog normalize [--chain ID]      # report sizes, multipacks, unparseable names
uv run smartcart-catalog extract [--extractor rule|claude] [--chain ID] [--limit N] [--batch-size N]
uv run smartcart-catalog cost-report [--runs N]      # tokens and estimated USD per model batch
```

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` | none | Postgres DSN |
| `ANTHROPIC_API_KEY` | none | required for `EXTRACTOR=claude` only |
| `EXTRACTOR` | `rule` | `rule` or `claude` |
| `EXTRACTION_MODEL` | `claude-sonnet-5-5` | D14 |
| `EXTRACTION_BATCH_SIZE` | 500 | items per batch |
| `EXTRACTION_MAX_TOKENS` | 1024 | per item |
| `EXTRACTION_EFFORT` | `low` | |
| `EXTRACTION_POLL_SECONDS` | 60 | |
| `EXTRACTION_MAX_ATTEMPTS` | 3 | retries before `failed` |
| `CATALOG_DATA_DIR` | `<repo>/data` | seed files |

Other modules add commands through `register(app)` in a module listed in `cli.EXTENSIONS`
(`smartcart_catalog.cli_matching` is listed already and is skipped until it exists).

## 6. Open items

- Domain-aware reviewer sign-off of the canonical list (issue #15).
- The model comparison on a labeled sample (Sonnet 5.5 batch against the rule baseline and a local
  Dicta-LM) and the first cost run on the MVP catalog, both pending an API key and loaded data (D14).
- Measured ranking to replace the estimated rank.
- House-brand lists per chain and the brand list, from loaded data.
- Real chain names as normalization fixtures, from the first loads.
