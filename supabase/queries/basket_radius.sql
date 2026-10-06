-- Basket pricing across every store within a radius (Phase 0 exit criterion, issue #60;
-- docs/architecture.md section 4, Layer 4).
--
-- requires: postgis (stores_within) and schema_v1 (current_price, items, stores).
--
-- Parameters (psycopg named placeholders, see supabase/queries/README.md for psql):
--   barcodes        text[]    the basket; duplicates are collapsed, NULL entries ignored
--   lon, lat        float8    the search point, WGS 84 degrees
--   radius_m        float8    search radius in meters
--   include_online  boolean   count online-channel stores too; NULL means false
--
-- One row per store in the radius, ordered so that complete baskets come first, then by total:
--   basket_total     sum of the current price of every found barcode (a partial total when
--                    something is missing; 0 when nothing was found)
--   found_count      barcodes with a current price at that store
--   missing_barcodes barcodes with no current price at that store, as an array (empty when none)
--   is_complete      true when no requested barcode is missing
--
-- A store with missing items is never dropped and never has its gap hidden: it appears with its
-- partial total and the list of missing barcodes, so a store cannot look cheap by not stocking
-- half the list. Compare totals only between rows where is_complete is true.
--
-- A barcode is found at a store when an item of that store's chain has that barcode and
-- current_price(item, store) returns a row: the latest store-specific event if the store has
-- one, otherwise the latest chain base price, ignoring events dated in the future. When a chain
-- has several items with the same barcode (barcodes can be chain-internal codes), the one with
-- the lowest current price at that store is used.

WITH wanted AS (
  SELECT DISTINCT t.barcode
  FROM unnest(%(barcodes)s::text[]) AS t(barcode)
  WHERE t.barcode IS NOT NULL
),
nearby AS (
  SELECT sw.store_id, sw.chain_id, sw.distance_m,
         s.name AS store_name, s.city, s.channel
  FROM stores_within(%(lon)s::float8, %(lat)s::float8, %(radius_m)s::float8) AS sw
  JOIN stores AS s ON s.id = sw.store_id
  WHERE s.channel = 'physical' OR COALESCE(%(include_online)s::boolean, false)
),
basket AS (
  SELECT n.store_id, w.barcode, hit.item_id, hit.price
  FROM nearby AS n
  CROSS JOIN wanted AS w
  LEFT JOIN LATERAL (
    SELECT i.id AS item_id, cp.price
    FROM items AS i
    CROSS JOIN LATERAL current_price(i.id, n.store_id) AS cp
    WHERE i.chain_id = n.chain_id
      AND i.barcode = w.barcode
    ORDER BY cp.price, i.id
    LIMIT 1
  ) AS hit ON true
)
SELECT n.store_id,
       n.chain_id,
       n.store_name,
       n.city,
       n.channel,
       round(n.distance_m)::int AS distance_m,
       COALESCE(sum(b.price), 0) AS basket_total,
       count(b.item_id) AS found_count,
       COALESCE(array_agg(b.barcode ORDER BY b.barcode) FILTER (WHERE b.item_id IS NULL),
                '{}'::text[]) AS missing_barcodes,
       count(*) FILTER (WHERE b.item_id IS NULL) = 0 AS is_complete
FROM nearby AS n
JOIN basket AS b USING (store_id)
GROUP BY n.store_id, n.chain_id, n.store_name, n.city, n.channel, n.distance_m
ORDER BY count(*) FILTER (WHERE b.item_id IS NULL), COALESCE(sum(b.price), 0), n.distance_m, n.store_id;
