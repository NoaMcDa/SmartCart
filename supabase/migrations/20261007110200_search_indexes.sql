-- Hybrid search over canonical products (issue #54, docs/architecture.md section 6).
-- requires: vector
--
-- Three retrievers, merged with reciprocal rank fusion in the API (smartcart_api.search):
--   * pg_trgm word similarity on search_norm(display_name_he), for typos;
--   * full-text search with the `simple` configuration, for exact words. Postgres ships no Hebrew
--     dictionary or stemmer; `simple` only lowercases. The API compensates for the attached
--     one-letter prefixes (ו ה ב ל מ ש כ) by also querying each word without them, and uses
--     prefix matching (word:*). Inflection (plural, construct state) is left to trigram and
--     vector retrieval;
--   * pgvector cosine distance on canonical_products.embedding and on item_embeddings of the
--     items mapped to a canonical at exact or any_brand.
--
-- search_norm() must stay identical to smartcart_api.embedding.normalize_text for the
-- characters it touches: lower case, no niqqud or quote marks, final letters folded, punctuation
-- to spaces, single spaces.

CREATE OR REPLACE FUNCTION search_norm(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT btrim(regexp_replace(
           regexp_replace(
             translate(lower(t), 'ךםןףץ"''`׳״“”’', 'כמנפצ'),
             '[֑-ׇ]', '', 'g'),
           '[\s,;:!?()\[\]{}/\\*+=|<>~#&^$@-]+', ' ', 'g'))
$$;

CREATE INDEX canonical_products_name_trgm
  ON canonical_products USING gin (search_norm(display_name_he) gin_trgm_ops);
CREATE INDEX canonical_products_name_fts
  ON canonical_products USING gin (to_tsvector('simple', search_norm(display_name_he)));
CREATE INDEX item_embeddings_hnsw
  ON item_embeddings USING hnsw (embedding vector_cosine_ops);
