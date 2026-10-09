-- Catalog expansion backlog (issue #52, docs/catalog.md section 9).
--
-- What should the catalog learn next? Two demand signals, ranked separately because their units
-- differ (people who asked versus shelves that stock it):
--
--   missed_query    queries that found nothing the parser accepts (search_misses: GET /search,
--                   POST /parse-list, POST /parse-recipe), over the last `days` days. Rows are
--                   deduplicated by normalized form and clustered by trigram similarity, so
--                   "עגבניות שרי", "עגבניות שירי" and "שרי עגבניות" count as one demand. The
--                   representative is the most frequent query of the cluster. demand = number of
--                   misses; secondary = distinct spellings in the cluster.
--   unmapped_item   products seen in loaded price files that no canonical covers: no row in
--                   item_canonical at all, ignoring human rejections (an item waiting in the
--                   review queue already has a candidate and is the review queue's business).
--                   Grouped by barcode across chains (an item without a barcode stands alone).
--                   demand = how many stores carry it (a chain base price counts every physical
--                   store of the chain; a per-store price counts that store); secondary = how many
--                   chains.
--
-- Parameters (psycopg named placeholders):
--   days            window for misses, default 30
--   min_similarity  trigram similarity for two queries to be one demand, default 0.5
--   min_misses      drop clusters asked for fewer times than this, default 1
--   item_days       an item counts when its row was touched by a load in the last N days, default 60
--   top             rows per kind, default 20
--
-- Result, ordered by kind then position (missed_query first):
--   kind, position, label, demand, secondary, examples text[], last_seen
--
-- Clustering is greedy and deterministic: a query joins the most frequent query it is similar to
-- (ties: the shorter, then alphabetical), and that query's own cluster is followed once more, so a
-- chain A ~ B ~ C collapses into A even when A and C are not similar to each other. It never
-- compares against more than the distinct queries of the window, which stays small (hundreds to a
-- few thousand), so the self join is cheap.
--
-- Run it from Python (smartcart_catalog.active.catalog_backlog), with `smartcart-catalog backlog`,
-- or with psql after turning the placeholders into psql variables (see supabase/queries/README.md).

WITH misses AS (
  SELECT search_norm(query_norm) AS q,
         count(*) AS n,
         max(seen_at) AS last_seen
  FROM search_misses
  WHERE seen_at >= now() - make_interval(days => %(days)s)
  GROUP BY 1
), pass1 AS (
  SELECT m.q, m.n, m.last_seen,
         (SELECT b.q FROM misses AS b
          WHERE b.q = m.q OR similarity(b.q, m.q) >= %(min_similarity)s
          ORDER BY b.n DESC, length(b.q), b.q
          LIMIT 1) AS head
  FROM misses AS m
), pass2 AS (
  SELECT p.q, p.n, p.last_seen, coalesce(h.head, p.head) AS head
  FROM pass1 AS p LEFT JOIN pass1 AS h ON h.q = p.head
), clusters AS (
  SELECT head AS label,
         sum(n) AS demand,
         count(*) AS secondary,
         (array_agg(q ORDER BY n DESC, q))[1:5] AS examples,
         max(last_seen) AS last_seen
  FROM pass2
  GROUP BY head
  HAVING sum(n) >= %(min_misses)s
), missed AS (
  SELECT 'missed_query'::text AS kind,
         row_number() OVER (ORDER BY demand DESC, secondary DESC, label) AS position,
         label, demand, secondary, examples, last_seen
  FROM clusters
), uncovered AS (
  SELECT i.id AS item_id, i.chain_id, i.raw_name, i.updated_at,
         coalesce(nullif(i.barcode, ''), i.chain_id || ':' || i.item_code) AS product_key
  FROM items AS i
  WHERE i.updated_at >= now() - make_interval(days => %(item_days)s)
    AND NOT EXISTS (
      SELECT 1 FROM item_canonical AS ic WHERE ic.item_id = i.id AND NOT ic.human_rejected)
), carried AS (
  SELECT u.product_key, u.chain_id, u.raw_name, u.updated_at,
         CASE WHEN bool_or(p.store_id IS NULL)
              THEN (SELECT count(*) FROM stores AS s
                    WHERE s.chain_id = u.chain_id AND s.channel = 'physical')
              ELSE count(DISTINCT p.store_id)
         END AS stores
  FROM uncovered AS u
  JOIN prices AS p ON p.item_id = u.item_id
  GROUP BY u.item_id, u.product_key, u.chain_id, u.raw_name, u.updated_at
), per_chain AS (
  SELECT product_key, chain_id,
         max(stores) AS stores,
         (array_agg(raw_name ORDER BY stores DESC, length(raw_name), raw_name))[1] AS raw_name,
         max(updated_at) AS last_seen
  FROM carried
  GROUP BY product_key, chain_id
), products AS (
  SELECT product_key,
         sum(stores) AS demand,
         count(*) AS secondary,
         (array_agg(raw_name ORDER BY stores DESC, length(raw_name), raw_name))[1] AS label,
         (array_agg(raw_name ORDER BY stores DESC, length(raw_name), raw_name))[1:5] AS examples,
         max(last_seen) AS last_seen
  FROM per_chain
  GROUP BY product_key
), unmapped AS (
  SELECT 'unmapped_item'::text AS kind,
         row_number() OVER (ORDER BY demand DESC, secondary DESC, label, product_key) AS position,
         label, demand, secondary, examples, last_seen
  FROM products
)
SELECT kind, position, label, demand, secondary, examples, last_seen
FROM (SELECT * FROM missed UNION ALL SELECT * FROM unmapped) AS ranked
WHERE position <= %(top)s
ORDER BY kind, position
