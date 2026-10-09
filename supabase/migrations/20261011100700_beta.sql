-- Closed beta tooling (issue #40, docs/beta-plan.md "Running the beta"): invite codes, members,
-- in-app feedback, and the metric views broken down by segment.
--
-- Privacy (D10, D11). A member row holds the user id the app already has, the invite code that
-- was used and the segment that code stands for. Nothing else: no name, no email, no answers
-- from a screening form. Feedback holds the segment, a 1 to 5 rating and free text, and NOT the
-- user id, so it cannot be tied back to a person from the database (the text is whatever the
-- person chose to write, which is why the feedback sheet tells them not to include personal
-- details). Leaving the beta deletes the member row; deleting the account cascades to it.
--
--   beta_invites   codes made by `smartcart-catalog beta-invite`. Readable by nobody through the
--                  app roles: RLS on, no policy, no grants. The API (service connection) is the
--                  only place that looks a code up, in POST /beta/join.
--   beta_members   one row per joined user. A member reads and deletes only their own row; nobody
--                  inserts through the data API (a row appears only when POST /beta/join
--                  consumed a valid code), so there is no INSERT grant.
--   beta_feedback  written by POST /beta/feedback on the service connection, read by the
--                  maintainer (`smartcart-catalog beta-feedback`). No policy, no grants.

CREATE TABLE beta_invites (
  code        text PRIMARY KEY CHECK (code ~ '^[A-Z0-9-]{6,32}$'),
  segment     text NOT NULL CHECK (segment IN ('large_family', 'kosher', 'periphery', 'general')),
  max_uses    integer NOT NULL DEFAULT 1 CHECK (max_uses >= 1),
  uses        integer NOT NULL DEFAULT 0 CHECK (uses >= 0),
  expires_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (uses <= max_uses)
);
CREATE INDEX beta_invites_segment_idx ON beta_invites (segment);

CREATE TABLE beta_members (
  user_id    uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  code       text NOT NULL REFERENCES beta_invites (code),
  segment    text NOT NULL CHECK (segment IN ('large_family', 'kosher', 'periphery', 'general')),
  joined_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX beta_members_segment_idx ON beta_members (segment);

CREATE TABLE beta_feedback (
  id          bigserial PRIMARY KEY,
  segment     text NOT NULL CHECK (segment IN ('large_family', 'kosher', 'periphery', 'general')),
  rating      smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body        text NOT NULL DEFAULT '' CHECK (char_length(body) <= 1000),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX beta_feedback_created_idx ON beta_feedback (created_at);

ALTER TABLE beta_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE beta_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE beta_feedback ENABLE ROW LEVEL SECURITY;
-- No FORCE: the API's service connection (the table owner) writes these tables and is not subject
-- to RLS, as with `events`.

CREATE POLICY beta_members_select_own ON beta_members FOR SELECT USING (user_id = auth.uid());
CREATE POLICY beta_members_delete_own ON beta_members FOR DELETE USING (user_id = auth.uid());
-- beta_invites and beta_feedback: no policy at all, so the app roles see and write nothing.

GRANT SELECT, DELETE ON beta_members TO smartcart_app;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT SELECT, DELETE ON beta_members TO authenticated;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON beta_invites, beta_members, beta_feedback FROM anon;
    REVOKE ALL ON SEQUENCE beta_feedback_id_seq FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON beta_invites, beta_feedback FROM authenticated;
    REVOKE ALL ON SEQUENCE beta_feedback_id_seq FROM authenticated;
  END IF;
END $$;
-- Supabase's default privileges may hand new tables to the data-API roles; the app role gets
-- nothing on the two private tables either.
REVOKE ALL ON beta_invites, beta_feedback FROM smartcart_app;
REVOKE ALL ON SEQUENCE beta_feedback_id_seq FROM smartcart_app;

-- ---------------------------------------------------------------------------------------------
-- The beta metrics by segment (docs/beta-plan.md section 4). events.user_id joined to the
-- member's segment. Events of people who are signed out, not members, or have left the beta have
-- no segment and are not in these views (the unsegmented views in 20261007120000_events.sql still
-- count them). Sample sizes come with every row: a segment with a small n says nothing yet.
-- Like the base views: Israel-time weeks, security_invoker, no access for the data-API roles.
-- ---------------------------------------------------------------------------------------------

CREATE VIEW beta_rejection_rate_by_segment WITH (security_invoker = true) AS
WITH shown AS (
  SELECT (date_trunc('week', e.created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
         m.segment,
         e.props->>'flex_level' AS flex_level,
         sum((e.props->>'count')::integer) AS shown,
         count(DISTINCT e.user_id) AS users
  FROM events e JOIN beta_members m ON m.user_id = e.user_id
  WHERE e.name = 'substitutions_shown'
  GROUP BY 1, 2, 3
), rejected AS (
  SELECT (date_trunc('week', e.created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
         m.segment,
         e.props->>'flex_level' AS flex_level,
         count(*) AS rejected
  FROM events e JOIN beta_members m ON m.user_id = e.user_id
  WHERE e.name = 'substitution_verdict' AND e.props->>'verdict' = 'not_good'
  GROUP BY 1, 2, 3
)
SELECT s.week, s.segment, s.flex_level, s.shown, s.users,
       coalesce(r.rejected, 0) AS rejected,
       round(coalesce(r.rejected, 0)::numeric / nullif(s.shown, 0), 4) AS rejection_rate
FROM shown s
LEFT JOIN rejected r USING (week, segment, flex_level)
ORDER BY s.week DESC, s.segment, s.flex_level;

CREATE VIEW beta_paste_to_results_by_segment WITH (security_invoker = true) AS
SELECT (date_trunc('week', e.created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
       m.segment,
       count(*) AS results_shown,
       count(DISTINCT e.user_id) AS users,
       round((percentile_cont(0.5) WITHIN GROUP
              (ORDER BY (e.props->>'duration_ms')::numeric))::numeric) AS median_ms,
       round((percentile_cont(0.9) WITHIN GROUP
              (ORDER BY (e.props->>'duration_ms')::numeric))::numeric) AS p90_ms
FROM events e JOIN beta_members m ON m.user_id = e.user_id
WHERE e.name = 'results_shown' AND e.props ? 'duration_ms'
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- Who is in the beta, per segment: codes made, places offered (the sum of max_uses), uses and
-- people currently joined (docs/beta-plan.md section 2: invited, joined). Active users per
-- segment and window are computed by `beta-report`.
CREATE VIEW beta_segment_overview WITH (security_invoker = true) AS
SELECT i.segment,
       count(*) AS codes,
       sum(i.max_uses) AS places,
       sum(i.uses) AS uses,
       (SELECT count(*) FROM beta_members m WHERE m.segment = i.segment) AS members
FROM beta_invites i
GROUP BY i.segment
ORDER BY i.segment;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON beta_rejection_rate_by_segment, beta_paste_to_results_by_segment,
                  beta_segment_overview FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON beta_rejection_rate_by_segment, beta_paste_to_results_by_segment,
                  beta_segment_overview FROM authenticated;
  END IF;
END $$;
REVOKE ALL ON beta_rejection_rate_by_segment, beta_paste_to_results_by_segment,
              beta_segment_overview FROM smartcart_app;
