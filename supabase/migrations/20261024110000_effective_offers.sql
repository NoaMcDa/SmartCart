-- effective_offers: the other offers kept for a (canonical, store, flexibility level)
-- (docs/optimizer.md, "Offers for the quantity asked").
--
-- effective_prices keeps ONE row per key: the offer with the best effective unit price (rank 0,
-- kind 'unit'). A unit price does not know the quantity asked. At `close` a tray of 30 eggs at 1.00
-- an egg beats a 12-pack at 1.18, so the line for 12 eggs was the whole tray (29.90) though the
-- 12-pack (14.20) is the cheapest way to buy 12; a "2 for 14" promo that only pays at two packs lost
-- to a deeper one that needs four.
--
-- This table holds up to four more rows per key (rank 1 to 4), written by the nightly precompute
-- (smartcart_api/offers.py chooses them): the offers that are the cheapest line for some quantity
-- up to six requested packs, or for some audience (everybody, each club on its own, a member of all).
-- A key whose best unit price is also the cheapest for every quantity has no row here, which is
-- most keys. /compare and /optimize take, per line, the cheapest line for the quantity asked among
-- the effective_prices row, the options its `noclub` JSON carries and these rows; /search, the
-- price history, the alerts and the SEO export read effective_prices alone and are unchanged.
--
--   rank   1..4, the order the precompute added them (the most useful first); the row at rank 0 is
--          the effective_prices row. A rank is not a price order.
--   kind   why it is kept, for people reading the table: 'club' (needs a club), 'bundle' (a promo
--          over several packs: "N for X", buy X get Y) or 'pack' (a plain item or a per-pack deal)
--   the other columns are effective_prices', with the same meaning; pack_units is the units in the
--   item. A club row is only for members (club_name); it is never replaced by a fallback, because
--   the non-club offers are rows of their own.
--
-- Additive: effective_prices is not touched. The migration works in current_schema(), like the
-- others: every name is unqualified (the migration tests apply the files inside a throwaway schema).

CREATE TABLE IF NOT EXISTS effective_offers (
  canonical_id          bigint NOT NULL REFERENCES canonical_products (id) ON DELETE CASCADE,
  store_id              bigint NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
  flex_level            text NOT NULL CHECK (flex_level IN ('exact', 'any_brand', 'close')),
  rank                  smallint NOT NULL CHECK (rank BETWEEN 1 AND 4),
  kind                  text NOT NULL CHECK (kind IN ('pack', 'bundle', 'club')),
  item_id               bigint NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  shelf_price           numeric NOT NULL,
  effective_unit_price  numeric NOT NULL,
  uom                   text NOT NULL,
  promo_id              bigint REFERENCES promos (id) ON DELETE SET NULL,
  club_required         boolean NOT NULL DEFAULT false,
  club_name             text,
  price_valid_from      timestamptz NOT NULL,
  computed_at           timestamptz NOT NULL DEFAULT now(),
  effective_price       numeric NOT NULL,
  promo_min_qty         numeric,
  is_estimated          boolean NOT NULL DEFAULT false,
  pack_units            numeric CHECK (pack_units IS NULL OR pack_units > 0),
  PRIMARY KEY (canonical_id, store_id, flex_level, rank)
);

CREATE INDEX IF NOT EXISTS effective_offers_lookup_idx
  ON effective_offers (store_id, flex_level, canonical_id);

-- Nothing in the data API reaches it (see 20261021120100_data_api_lockdown.sql: no default
-- privileges for anon or authenticated; belt and braces below). The app role reads it like
-- effective_prices; the API role through the grants function, wrapped as 20261022120000 did.
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON effective_offers FROM %I', r);
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_app') THEN
    GRANT SELECT ON effective_offers TO smartcart_app;
  END IF;
END $$;

ALTER FUNCTION smartcart_grant_api_role(name) RENAME TO smartcart_grant_api_role_pre_offers;

CREATE OR REPLACE FUNCTION smartcart_grant_api_role(p_role name)
RETURNS void
LANGUAGE plpgsql AS $fn$
BEGIN
  PERFORM smartcart_grant_api_role_pre_offers(p_role);
  EXECUTE format('GRANT SELECT ON effective_offers TO %I', p_role);
END
$fn$;

REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM PUBLIC;
REVOKE ALL ON FUNCTION smartcart_grant_api_role_pre_offers(name) FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role(name) FROM %I', r);
      EXECUTE format('REVOKE ALL ON FUNCTION smartcart_grant_api_role_pre_offers(name) FROM %I', r);
    END IF;
  END LOOP;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api') THEN
    PERFORM smartcart_grant_api_role('smartcart_api');
  END IF;
END $$;
