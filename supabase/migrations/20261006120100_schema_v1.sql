-- Schema v1: the ingestion side (issue #27, docs/architecture.md section 2).
--
-- Needs no extension. stores.geog and its GiST index are added by the next migration, which
-- needs PostGIS; every real environment (CI, Supabase, docker compose) applies both, so the
-- schema is the same everywhere.
--
-- Conventions:
--   * Prices are change events only: base price per chain (store_id IS NULL) plus per-store
--     exceptions, partitioned by month on valid_from.
--   * Unit prices are per 100 g, per 100 ml or per unit; weighed produce per kg, flagged
--     estimated.
--   * Monthly partitions are created by ensure_price_partition(); the loader calls it before
--     inserting and a nightly job keeps two months ahead (see supabase/README.md).

-- ---------------------------------------------------------------------------------------------
-- Shared trigger: keep updated_at current.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;

-- ---------------------------------------------------------------------------------------------
-- chains
-- ---------------------------------------------------------------------------------------------
CREATE TABLE chains (
  id          text PRIMARY KEY,               -- chain id, e.g. the GS1 chain code or a slug
  name        text NOT NULL,
  portal      text CHECK (portal IN ('cerberus', 'shufersal', 'matrix', 'bina', 'web', 'other')),
  club_names  text[] NOT NULL DEFAULT '{}',   -- loyalty clubs promos may be restricted to
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER chains_set_updated_at BEFORE UPDATE ON chains
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------------------------
-- stores (geog added in the next migration)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE stores (
  id          bigserial PRIMARY KEY,
  chain_id    text NOT NULL REFERENCES chains (id),
  store_code  text NOT NULL,
  name        text NOT NULL,
  address     text,
  city        text,
  channel     text NOT NULL DEFAULT 'physical' CHECK (channel IN ('physical', 'online')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chain_id, store_code)
);
CREATE TRIGGER stores_set_updated_at BEFORE UPDATE ON stores
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------------------------
-- items: chain-scoped. The barcode may be a chain-internal code, so it is not unique.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE items (
  id              bigserial PRIMARY KEY,
  chain_id        text NOT NULL REFERENCES chains (id),
  item_code       text NOT NULL,
  barcode         text,
  raw_name        text NOT NULL,
  manufacturer    text,
  quantity        numeric,
  unit            text,
  is_weighed      boolean NOT NULL DEFAULT false,
  raw_attributes  jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chain_id, item_code)
);
CREATE INDEX items_barcode_idx ON items (barcode) WHERE barcode IS NOT NULL;
CREATE TRIGGER items_set_updated_at BEFORE UPDATE ON items
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------------------------
-- file_tracking: one row per transparency file seen, keyed by content hash.
-- chain_id has no foreign key on purpose: the audit trail must record files from a chain that is
-- not (yet) in chains, rather than fail to record them.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE file_tracking (
  id              bigserial PRIMARY KEY,
  sha256          char(64) NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  chain_id        text NOT NULL,
  store_code      text,
  kind            text NOT NULL
                  CHECK (kind IN ('stores', 'price_full', 'price', 'promo_full', 'promo')),
  path            text,                       -- raw file location in object storage
  published_at    timestamptz,
  schema_version  text NOT NULL DEFAULT 'unknown' CHECK (schema_version IN ('v1', 'v2', 'unknown')),
  status          text NOT NULL DEFAULT 'seen'
                  CHECK (status IN ('seen', 'downloaded', 'held', 'loading', 'loaded',
                                    'quarantined', 'failed')),
  reason          text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX file_tracking_latest_idx
  ON file_tracking (chain_id, store_code, kind, published_at DESC);
CREATE INDEX file_tracking_open_idx
  ON file_tracking (status) WHERE status NOT IN ('loaded', 'quarantined');
CREATE TRIGGER file_tracking_set_updated_at BEFORE UPDATE ON file_tracking
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE quarantine_events (
  id          bigserial PRIMARY KEY,
  file_id     bigint NOT NULL REFERENCES file_tracking (id) ON DELETE CASCADE,
  gate        text NOT NULL,                  -- e.g. zero_price, price_jump, item_count_drop
  detail      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX quarantine_events_file_idx ON quarantine_events (file_id);

-- ---------------------------------------------------------------------------------------------
-- prices: change events, partitioned by month on valid_from.
-- store_id IS NULL is the chain base price; a row with a store_id is that store's exception.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE prices (
  item_id       bigint NOT NULL REFERENCES items (id),
  store_id      bigint REFERENCES stores (id),
  price         numeric NOT NULL CHECK (price >= 0),
  unit_price    numeric CHECK (unit_price >= 0),
  uom           text,                         -- '100g', '100ml', 'unit' or 'kg'
  is_estimated  boolean NOT NULL DEFAULT false, -- unit price of weighed produce
  valid_from    timestamptz NOT NULL,
  file_id       bigint REFERENCES file_tracking (id),
  -- Also the "latest price per item and store" index: equality on item_id and store_id (NULL
  -- included, thanks to NULLS NOT DISTINCT) and a backward scan on valid_from.
  CONSTRAINT prices_event_key UNIQUE NULLS NOT DISTINCT (item_id, store_id, valid_from)
) PARTITION BY RANGE (valid_from);

-- Store-first access for basket pricing across the stores in a radius.
CREATE INDEX prices_store_item_idx ON prices (store_id, item_id, valid_from DESC);

COMMENT ON TABLE prices IS
  'Price change events. store_id NULL = chain base price; otherwise a per-store exception.';

-- Creates the monthly partition of prices that contains p_month, if missing. Months are UTC.
-- Returns the partition name (prices_YYYY_MM).
CREATE OR REPLACE FUNCTION ensure_price_partition(p_month date) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
  v_month timestamp := date_trunc('month', p_month::timestamp);
  v_name  text := 'prices_' || to_char(v_month, 'YYYY_MM');
  v_from  timestamptz := v_month AT TIME ZONE 'UTC';
  v_to    timestamptz := (v_month + interval '1 month') AT TIME ZONE 'UTC';
  v_nsp   text;
BEGIN
  -- Serialize concurrent callers so two loaders cannot race on CREATE TABLE.
  PERFORM pg_advisory_xact_lock(hashtext('ensure_price_partition'));
  -- Put the partition next to the prices table that the search_path resolves.
  SELECT n.nspname INTO v_nsp
  FROM pg_class AS c JOIN pg_namespace AS n ON n.oid = c.relnamespace
  WHERE c.oid = 'prices'::regclass;
  IF to_regclass(format('%I.%I', v_nsp, v_name)) IS NULL THEN
    EXECUTE format('CREATE TABLE %I.%I PARTITION OF %I.prices FOR VALUES FROM (%L) TO (%L)',
                   v_nsp, v_name, v_nsp, v_from, v_to);
  END IF;
  RETURN v_name;
END
$$;

-- Creates every monthly partition from p_from through p_to (inclusive).
CREATE OR REPLACE FUNCTION ensure_price_partitions(p_from date, p_to date) RETURNS SETOF text
LANGUAGE sql AS $$
  SELECT ensure_price_partition(m::date)
  FROM generate_series(date_trunc('month', p_from::timestamp),
                       date_trunc('month', p_to::timestamp),
                       interval '1 month') AS m
$$;

-- Last month through two months ahead, so a fresh database can load right away.
SELECT ensure_price_partitions((now() - interval '1 month')::date,
                               (now() + interval '2 months')::date);

-- The price that applies to an item at a store at time p_at: the latest store-specific event if
-- the store has one, otherwise the latest chain base price. An exception stays in force until a
-- newer event for that store supersedes it, so the loader writes a store event whenever a
-- store's price changes, including when it returns to the base price.
CREATE OR REPLACE FUNCTION current_price(
  p_item_id  bigint,
  p_store_id bigint,
  p_at       timestamptz DEFAULT now()
) RETURNS TABLE (
  item_id         bigint,
  store_id        bigint,
  price           numeric,
  unit_price      numeric,
  uom             text,
  is_estimated    boolean,
  valid_from      timestamptz,
  is_store_price  boolean
)
LANGUAGE sql STABLE AS $$
  SELECT p.item_id, p_store_id, p.price, p.unit_price, p.uom, p.is_estimated, p.valid_from,
         p.store_id IS NOT NULL
  FROM prices AS p
  WHERE p.item_id = p_item_id
    AND (p.store_id = p_store_id OR p.store_id IS NULL)
    AND p.valid_from <= p_at
  ORDER BY (p.store_id IS NOT NULL) DESC, p.valid_from DESC
  LIMIT 1
$$;

-- Latest event per (item, store-or-base) as of now. Base rows have store_id NULL.
CREATE VIEW latest_prices AS
  SELECT DISTINCT ON (p.item_id, p.store_id)
         p.item_id, p.store_id, p.price, p.unit_price, p.uom, p.is_estimated, p.valid_from
  FROM prices AS p
  WHERE p.valid_from <= now()
  ORDER BY p.item_id, p.store_id, p.valid_from DESC;

-- ---------------------------------------------------------------------------------------------
-- promos: structured. store_id IS NULL means the promo applies chain-wide.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE promos (
  id            bigserial PRIMARY KEY,
  chain_id      text NOT NULL REFERENCES chains (id),
  store_id      bigint REFERENCES stores (id),
  promo_id      text NOT NULL,                -- the chain's own promotion id
  description   text NOT NULL,                -- raw description as published
  starts_at     timestamptz,
  ends_at       timestamptz,
  hours         text,                         -- daily time window when the source has one
  club_only     boolean NOT NULL DEFAULT false,
  club_name     text,
  min_qty       numeric,
  max_qty       numeric,
  reward_type   text NOT NULL DEFAULT 'other'
                CHECK (reward_type IN ('price', 'percent', 'buy_x_get_y', 'bundle', 'other')),
  reward_value  numeric,
  raw           jsonb NOT NULL DEFAULT '{}'::jsonb,
  file_id       bigint REFERENCES file_tracking (id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT promos_source_key UNIQUE NULLS NOT DISTINCT (chain_id, store_id, promo_id)
);
CREATE INDEX promos_store_active_idx ON promos (store_id, ends_at);
CREATE INDEX promos_chain_active_idx ON promos (chain_id, ends_at) WHERE store_id IS NULL;
CREATE TRIGGER promos_set_updated_at BEFORE UPDATE ON promos
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE promo_items (
  promo_id  bigint NOT NULL REFERENCES promos (id) ON DELETE CASCADE,
  item_id   bigint NOT NULL REFERENCES items (id),
  PRIMARY KEY (promo_id, item_id)
);
CREATE INDEX promo_items_item_idx ON promo_items (item_id);
