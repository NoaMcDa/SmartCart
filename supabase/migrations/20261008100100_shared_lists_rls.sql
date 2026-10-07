-- Shared lists, follow-up to 20261008100000_phase2.sql (issue #34).
--
-- 1. list_items policies. The phase 1 policy list_items_own (user_id = auth.uid()) let anyone
--    insert a row into any list as long as the row carried their own user_id, and it hid the
--    items a member added from the list's owner (their user_id is the member's). Access to an
--    item now follows its list: the owner and accepted members read it; the owner and editors
--    write it; a new row must carry the writer's own user_id (who added it). Viewers cannot
--    write. A stranger sees and writes nothing.
-- 2. list_shares.expires_at: an invite link that was not accepted by then cannot be used. The
--    API stores a SHA-256 of the invite token in invite_token, never the token itself.

CREATE OR REPLACE FUNCTION owns_list(p_list_id bigint)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM lists l WHERE l.id = p_list_id AND l.user_id = auth.uid())
$$;

DROP POLICY IF EXISTS list_items_own ON list_items;
DROP POLICY IF EXISTS list_items_shared_read ON list_items;
DROP POLICY IF EXISTS list_items_shared_write ON list_items;

CREATE POLICY list_items_read ON list_items FOR SELECT
  USING (owns_list(list_id) OR is_list_member(list_id, 'viewer'));
CREATE POLICY list_items_insert ON list_items FOR INSERT
  WITH CHECK (user_id = auth.uid() AND (owns_list(list_id) OR is_list_member(list_id, 'editor')));
CREATE POLICY list_items_update ON list_items FOR UPDATE
  USING (owns_list(list_id) OR is_list_member(list_id, 'editor'))
  WITH CHECK (owns_list(list_id) OR is_list_member(list_id, 'editor'));
CREATE POLICY list_items_delete ON list_items FOR DELETE
  USING (owns_list(list_id) OR is_list_member(list_id, 'editor'));

ALTER TABLE list_shares ADD COLUMN IF NOT EXISTS expires_at timestamptz;

GRANT EXECUTE ON FUNCTION owns_list(bigint) TO smartcart_app;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT EXECUTE ON FUNCTION owns_list(bigint) TO authenticated;
  END IF;
END $$;
