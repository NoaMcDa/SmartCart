-- Phase 1 catalog: taxonomy, canonical products, extracted attributes, embeddings, matching,
-- gold set, feedback, effective prices, evaluation runs (issues #10, #15, #25, #29, #33, #38, #43, #47).
-- requires: vector

CREATE TABLE taxonomy (
  id         text PRIMARY KEY,                       -- stable slug, e.g. dairy.milk.fresh
  parent_id  text REFERENCES taxonomy (id),
  level      smallint NOT NULL CHECK (level BETWEEN 1 AND 4),
  name_he    text NOT NULL,
  name_en    text,
  sort       integer NOT NULL DEFAULT 0
);
CREATE INDEX taxonomy_parent_idx ON taxonomy (parent_id);

-- Per product type: which attributes must match at "any brand" and which may differ at "close".
CREATE TABLE product_type_rules (
  product_type   text PRIMARY KEY,
  critical_keys  text[] NOT NULL DEFAULT '{}',
  soft_keys      text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE canonical_products (
  id               bigserial PRIMARY KEY,
  taxonomy_id      text NOT NULL REFERENCES taxonomy (id),
  slug             text NOT NULL UNIQUE,
  display_name_he  text NOT NULL,
  product_type     text NOT NULL REFERENCES product_type_rules (product_type),
  base_unit        text NOT NULL CHECK (base_unit IN ('100g', '100ml', 'unit', 'kg')),
  critical_attrs   jsonb NOT NULL DEFAULT '{}'::jsonb,   -- values that define this canonical
  soft_attrs       jsonb NOT NULL DEFAULT '{}'::jsonb,   -- typical values, may differ at "close"
  embedding        vector(1024),
  is_mvp           boolean NOT NULL DEFAULT false,
  rank             integer,                              -- basket-frequency rank, 1 = most common
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX canonical_products_block_idx ON canonical_products (taxonomy_id, base_unit);
CREATE INDEX canonical_products_embedding_hnsw
  ON canonical_products USING hnsw (embedding vector_cosine_ops);
CREATE TRIGGER canonical_products_set_updated_at BEFORE UPDATE ON canonical_products
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- LLM or rule extraction output, one row per item, processed once.
CREATE TABLE item_attributes (
  item_id        bigint PRIMARY KEY REFERENCES items (id) ON DELETE CASCADE,
  attrs          jsonb NOT NULL DEFAULT '{}'::jsonb,
  verified_keys  text[] NOT NULL DEFAULT '{}',          -- keys a human confirmed
  extractor      text NOT NULL,                         -- rule | claude | human
  model          text,
  confidence     numeric,
  status         text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'retry', 'failed')),
  extracted_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX item_attributes_status_idx ON item_attributes (status) WHERE status <> 'ok';

CREATE TABLE item_embeddings (
  item_id      bigint PRIMARY KEY REFERENCES items (id) ON DELETE CASCADE,
  embedding    vector(1024) NOT NULL,
  model        text NOT NULL,
  embedded_at  timestamptz NOT NULL DEFAULT now()
);

-- Item -> canonical mapping with the flexibility level at which the item qualifies.
CREATE TABLE item_canonical (
  item_id       bigint NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  canonical_id  bigint NOT NULL REFERENCES canonical_products (id) ON DELETE CASCADE,
  flex_level    text NOT NULL CHECK (flex_level IN ('exact', 'any_brand', 'close')),
  confidence    numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  source        text NOT NULL CHECK (source IN ('rule', 'model', 'human')),
  needs_review  boolean NOT NULL DEFAULT false,
  reviewed_by   text,
  reviewed_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (item_id, canonical_id)
);
CREATE INDEX item_canonical_canonical_idx ON item_canonical (canonical_id, flex_level);
CREATE INDEX item_canonical_review_idx ON item_canonical (needs_review) WHERE needs_review;
CREATE TRIGGER item_canonical_set_updated_at BEFORE UPDATE ON item_canonical
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE gold_pairs (
  id            bigserial PRIMARY KEY,
  item_id       bigint NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  canonical_id  bigint NOT NULL REFERENCES canonical_products (id) ON DELETE CASCADE,
  label         text NOT NULL CHECK (label IN ('exact', 'any_brand', 'close', 'no_match')),
  category      text,
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (item_id, canonical_id)
);

CREATE TABLE substitution_feedback (
  id                  bigserial PRIMARY KEY,
  user_id             uuid,
  canonical_id        bigint REFERENCES canonical_products (id),
  original_item_id    bigint REFERENCES items (id),
  substitute_item_id  bigint REFERENCES items (id),
  verdict             text NOT NULL CHECK (verdict IN ('not_good', 'kept_original', 'accepted')),
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX substitution_feedback_pair_idx ON substitution_feedback (substitute_item_id, verdict);

-- Nightly precompute: best item and effective unit price per (canonical, store).
CREATE TABLE effective_prices (
  canonical_id          bigint NOT NULL REFERENCES canonical_products (id) ON DELETE CASCADE,
  store_id              bigint NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
  item_id               bigint NOT NULL REFERENCES items (id),
  flex_level            text NOT NULL CHECK (flex_level IN ('exact', 'any_brand', 'close')),
  shelf_price           numeric NOT NULL,
  effective_unit_price  numeric NOT NULL,
  uom                   text NOT NULL,
  promo_id              bigint REFERENCES promos (id),
  club_required         boolean NOT NULL DEFAULT false,
  club_name             text,
  price_valid_from      timestamptz NOT NULL,
  computed_at           timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (canonical_id, store_id, flex_level)
);
CREATE INDEX effective_prices_store_idx ON effective_prices (store_id);

CREATE TABLE match_runs (
  id           bigserial PRIMARY KEY,
  kind         text NOT NULL,            -- embed | judge | evaluate | precompute
  started_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz,
  metrics      jsonb NOT NULL DEFAULT '{}'::jsonb
);
