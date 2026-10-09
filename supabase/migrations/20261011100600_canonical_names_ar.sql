-- Arabic names for canonical products and the indexes that search them (issue #73, matching half).
--
-- canonical_products.names_ar holds 1-3 Arabic names per canonical, as Arab-Israeli shoppers write
-- them (Modern Standard, Levantine colloquial, the Hebrew loanword when that is what people say),
-- each stating the critical attributes (fat %, fresh or frozen, soy or almond). They are MACHINE
-- DRAFTED in data/canonicals.yaml and need a native-speaker review; `smartcart-catalog seed`
-- writes them. Hebrew search is untouched: it still reads display_name_he.
--
-- search_norm_ar() folds Arabic spelling variants the way smartcart_catalog.normalize.fold_ar
-- does (the two must stay identical; services/catalog/tests/test_arabic_fold_sql.py checks it):
--   * NFKC (presentation forms to letters), lower case;
--   * alef with hamza or madda, and alef wasla, to bare alef; ى to ي; ة to ه; ؤ to و; ئ to ي;
--     standalone hamza removed (بيضاء and بيضا meet); Persian/Urdu ک ی ڤ پ to ك ي ف ب;
--   * tashkeel, tatweel and bidirectional marks removed;
--   * Arabic-Indic and Persian digits to Latin digits; ٪ to %, ٫ to ., ، to ',', ؛ to ';', ؟ to ?;
--   * quote marks removed, punctuation to spaces, single spaces.
-- The article ال and the conjunction و are NOT removed here: the API strips them from the query
-- (prefix variants, like the Hebrew prefix letters), and canonical names are written without them.

ALTER TABLE canonical_products
  ADD COLUMN IF NOT EXISTS names_ar text[] NOT NULL DEFAULT '{}';

CREATE OR REPLACE FUNCTION search_norm_ar(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT btrim(regexp_replace(
           regexp_replace(
             translate(lower(normalize(t, NFKC)),
                       'أإآٱىةؤئکیڤپ٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٪٫،؛؟ءـ٬"''`’‘“”',
                       'اااايهوي' || 'كيفب' || '01234567890123456789' || '%.,;?'),
             '[ً-ٰٟۖ-ۭ‎‏؜‪-‮⁦-⁩]',
             '', 'g'),
           '[\s,;:!?()\[\]{}/\\*+=|<>~#&^$@«»…–—•·-]+', ' ', 'g'))
$$;

-- All of one canonical's names as one normalized string: the trigram and full-text indexes cover
-- it, and the API re-scores each name on its own.
CREATE OR REPLACE FUNCTION canonical_names_ar_norm(names text[]) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT public.search_norm_ar(array_to_string(names, ' | '))
$$;

CREATE INDEX canonical_products_names_ar_trgm
  ON canonical_products USING gin (canonical_names_ar_norm(names_ar) gin_trgm_ops);
CREATE INDEX canonical_products_names_ar_fts
  ON canonical_products USING gin (to_tsvector('simple', canonical_names_ar_norm(names_ar)));
