-- Vectors of the canonicals' non-Hebrew names (issue #73, vectors half).
--
-- canonical_products.embedding holds ONE vector per canonical, of display_name_he, and it stays: the
-- Hebrew retriever and its gold evaluation read it and nothing about them changes. The Arabic names
-- (canonical_products.names_ar, 1-3 per canonical) get their own table instead of more columns on
-- canonical_products, because the number of names varies, a name can be changed or removed on its own,
-- and a language column lets another language (Russian, English) reuse the table without a schema
-- change. One row per (canonical, language, name): a canonical's colloquial and standard spellings are
-- different strings and a query is close to one of them, not to their average.
--
-- `smartcart-catalog embed` fills it (embed_canonicals); the API's Arabic vector retriever reads rows
-- with lang = 'ar' and embedding_model equal to the query embedder's model, like the Hebrew one. The
-- retriever stays recall-only for Arabic (confidence capped at 0.60, never answers on its own).

CREATE TABLE canonical_name_embeddings (
  canonical_id     bigint NOT NULL REFERENCES canonical_products (id) ON DELETE CASCADE,
  lang             text NOT NULL,
  name             text NOT NULL,
  embedding        vector(1024) NOT NULL,
  embedding_model  text NOT NULL,
  embedded_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (canonical_id, lang, name)
);

CREATE INDEX canonical_name_embeddings_hnsw
  ON canonical_name_embeddings USING hnsw (embedding vector_cosine_ops);

-- The API role (20261011100500) reads the catalog tables it lists and nothing else: add this one to
-- the list its grant function walks, so a database where the role is (re)granted later has it too.
DO $$
DECLARE
  def text := pg_get_functiondef('smartcart_grant_api_role(name)'::regprocedure);
  patched text := replace(def, '''item_embeddings'', ''file_tracking''',
                          '''item_embeddings'', ''canonical_name_embeddings'', ''file_tracking''');
BEGIN
  IF patched = def THEN
    RAISE EXCEPTION 'smartcart_grant_api_role no longer lists item_embeddings, file_tracking: update this migration';
  END IF;
  EXECUTE patched;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartcart_api') THEN
    PERFORM smartcart_grant_api_role('smartcart_api');
  END IF;
END $$;
