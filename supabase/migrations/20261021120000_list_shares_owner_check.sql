-- Security review: a user could grant themselves access to somebody else's list (docs/security-review.md,
-- finding S1).
--
-- list_shares_owner (20261008100000_phase2.sql) was
--     USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid())
-- and the table is writable by the data-API role `authenticated` (and by smartcart_app). Nothing
-- tied owner_id to the list: any signed-in user could INSERT
--     (list_id = <someone else's list id>, owner_id = <self>, member_id = <self>, accepted_at = now())
-- through PostgREST. The foreign key to lists is checked without row-level security, so the row went
-- in, is_list_member() then answered true, and lists_shared / list_items_read / list_items_insert
-- gave the attacker the victim's list and its items (and, as an editor, write access). List ids are
-- sequential. The API never offers that insert, which is why its tests did not see it; PostgREST does.
--
-- Fix: the owner policy now also requires that the caller owns the list (owns_list is the SECURITY
-- DEFINER helper of 20261008100100_shared_lists_rls.sql), for reading, writing and for the new row
-- of an UPDATE. Rows forged before this migration are removed.

DROP POLICY IF EXISTS list_shares_owner ON list_shares;
CREATE POLICY list_shares_owner ON list_shares
  USING (owner_id = auth.uid() AND owns_list(list_id))
  WITH CHECK (owner_id = auth.uid() AND owns_list(list_id));

-- A share row whose owner is not the list's owner can only have been forged (the API writes
-- owner_id from the list it just checked). The migrating role is the table owner / BYPASSRLS on
-- Supabase and a superuser locally, so this sees every row.
DELETE FROM list_shares s
WHERE NOT EXISTS (SELECT 1 FROM lists l WHERE l.id = s.list_id AND l.user_id = s.owner_id);
