-- Club promotions reach the people who are members (docs/adapters.md, "Club promotions").
--
-- No schema change: `promos.club_name` (and `effective_prices.club_name`, the keys of
-- `effective_prices.noclub -> 'clubs'`) used to hold one club name, or, for a boolean ClubID
-- expression, its names flattened into `A | B` (the `&` between groups lost, cut at 120 characters).
-- From this version the ingest writes a *rule over club labels* there: `A`, `A | B` (any of),
-- `A & B` (all of), `(A | B) & C`, or `אחר` for a restriction nobody can be a member of. The API
-- evaluates it as written (`basket.club_member`), so a flattened name written by the older ingest
-- would now be read as "any of", which for a promo that really needed an AND would give the club
-- price to someone who is not a member.
--
-- The older ingest recorded every expression it flattened in `promos.raw -> 'club_expression'`.
-- Those promos are reset to the "unknown" rule until the next load of their file rewrites them
-- (the loader upserts every promotion of a PromoFull file, and the nightly precompute follows):
-- fail closed, no club price. The derived rows of `effective_prices` that were built from them are
-- reset the same way, and the per-club alternatives they carried are dropped.

UPDATE promos
   SET club_name = 'אחר'
 WHERE club_only
   AND raw ->> 'club_expression' IS NOT NULL
   AND club_name IS DISTINCT FROM 'אחר';

UPDATE effective_prices AS ep
   SET club_name = 'אחר',
       noclub = CASE WHEN ep.noclub IS NULL THEN NULL ELSE ep.noclub - 'clubs' END
  FROM promos AS p
 WHERE ep.promo_id = p.id
   AND ep.club_required
   AND p.club_only
   AND p.raw ->> 'club_expression' IS NOT NULL;
