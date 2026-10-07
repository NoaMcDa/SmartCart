-- First-party product events for the closed beta (issue #40, decisions D10 and D11).
--
-- No third-party analytics: the web app sends a small batch of events to POST /events and the API
-- writes them here. What may be stored is limited by the API: an allowlist of event names and, per
-- event, an allowlist of property keys whose values are numbers or members of a fixed set, so
-- free text (and with it personal data) cannot get in. See docs/beta-plan.md.
--
--   user_id     the signed-in user when the request carried a valid JWT, else NULL. Deleting the
--               account sets it to NULL (the events stay as anonymous statistics).
--   session_id  a random id the browser generates and keeps in localStorage (8 to 64 URL-safe
--               characters). It is not derived from anything about the person and is the actor
--               for return visits when nobody is signed in.
--   name, props the event and its allowlisted properties.
--
-- Nothing here is readable through the Supabase data API: row-level security is on with no
-- policy, the roles of the data API have no grants, and the views run with the caller's rights.
-- The API (service connection) writes; the weekly review reads the views below.

CREATE TABLE events (
  id          bigserial PRIMARY KEY,
  user_id     uuid REFERENCES auth.users (id) ON DELETE SET NULL,
  session_id  text NOT NULL CHECK (session_id ~ '^[A-Za-z0-9_-]{8,64}$'),
  name        text NOT NULL CHECK (name ~ '^[a-z][a-z0-9_]{2,47}$'),
  props       jsonb NOT NULL DEFAULT '{}'::jsonb
              CHECK (jsonb_typeof(props) = 'object' AND pg_column_size(props) <= 2048),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_name_created_idx ON events (name, created_at);
CREATE INDEX events_session_created_idx ON events (session_id, created_at);
CREATE INDEX events_user_created_idx ON events (user_id, created_at) WHERE user_id IS NOT NULL;

ALTER TABLE events ENABLE ROW LEVEL SECURITY;
-- No policy: anon and authenticated callers see and write nothing. The service connection that
-- the API uses owns the table and is not subject to RLS (no FORCE here on purpose).

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON events FROM anon;
    REVOKE ALL ON SEQUENCE events_id_seq FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON events FROM authenticated;
    REVOKE ALL ON SEQUENCE events_id_seq FROM authenticated;
  END IF;
END $$;

-- ---------------------------------------------------------------------------------------------
-- The three beta metrics (docs/beta-plan.md), per ISO week in Israel time (weeks start Monday).
-- security_invoker: the views never widen access beyond the caller's own rights on events.
-- ---------------------------------------------------------------------------------------------

-- 1. Substitution rejection rate = not_good verdicts / substitutions shown, per flexibility level.
--    Client events: substitutions_shown {flex_level, count} when a results view lists
--    substitutions, and substitution_verdict {flex_level, verdict} when the user answers.
CREATE VIEW beta_rejection_rate WITH (security_invoker = true) AS
WITH shown AS (
  SELECT (date_trunc('week', created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
         props->>'flex_level' AS flex_level,
         sum((props->>'count')::integer) AS shown
  FROM events
  WHERE name = 'substitutions_shown'
  GROUP BY 1, 2
), rejected AS (
  SELECT (date_trunc('week', created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
         props->>'flex_level' AS flex_level,
         count(*) AS rejected
  FROM events
  WHERE name = 'substitution_verdict' AND props->>'verdict' = 'not_good'
  GROUP BY 1, 2
)
SELECT s.week,
       s.flex_level,
       s.shown,
       coalesce(r.rejected, 0) AS rejected,
       round(coalesce(r.rejected, 0)::numeric / nullif(s.shown, 0), 4) AS rejection_rate
FROM shown s
LEFT JOIN rejected r USING (week, flex_level)
ORDER BY s.week DESC, s.flex_level;

-- 2. Paste-to-results time. Client events: results_shown {duration_ms, item_count, store_count},
--    where duration_ms runs from the paste to the results being on screen.
CREATE VIEW beta_paste_to_results WITH (security_invoker = true) AS
SELECT (date_trunc('week', created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
       count(*) AS results_shown,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY (props->>'duration_ms')::numeric))::numeric) AS median_ms,
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY (props->>'duration_ms')::numeric))::numeric) AS p90_ms
FROM events
WHERE name = 'results_shown' AND props ? 'duration_ms'
GROUP BY 1
ORDER BY 1 DESC;

-- 3. Return visits. An actor is the signed-in user, else the browser's session id. A returning
--    actor is active in the week and had their first app_opened before that week.
CREATE VIEW beta_return_visits WITH (security_invoker = true) AS
WITH opens AS (
  SELECT coalesce(user_id::text, session_id) AS actor,
         (created_at AT TIME ZONE 'Asia/Jerusalem')::date AS day
  FROM events
  WHERE name = 'app_opened'
  GROUP BY 1, 2
), firsts AS (
  SELECT actor, min(day) AS first_day FROM opens GROUP BY 1
)
SELECT date_trunc('week', o.day)::date AS week,
       count(DISTINCT o.actor) AS active_users,
       count(DISTINCT o.actor) FILTER (WHERE f.first_day < date_trunc('week', o.day)::date)
         AS returning_users,
       round(
         count(DISTINCT o.actor) FILTER (WHERE f.first_day < date_trunc('week', o.day)::date)::numeric
         / nullif(count(DISTINCT o.actor), 0), 4) AS returning_share,
       round(count(*)::numeric / nullif(count(DISTINCT o.actor), 0), 2) AS visit_days_per_user
FROM opens o
JOIN firsts f USING (actor)
GROUP BY 1
ORDER BY 1 DESC;

-- Every "not a good substitute" answer with its context, for the weekly review. The rows come from
-- substitution_feedback (written by POST /feedback/substitution, which also puts the mapping in the
-- review queue: item_canonical.needs_review). reviewed = a human has looked at the mapping since.
CREATE VIEW beta_rejected_substitutions WITH (security_invoker = true) AS
SELECT f.id AS feedback_id,
       f.created_at,
       cp.slug AS canonical_slug,
       cp.display_name_he AS canonical_name,
       oi.raw_name AS original_item,
       si.raw_name AS substitute_item,
       si.chain_id AS substitute_chain,
       ic.flex_level,
       ic.confidence,
       ic.needs_review,
       ic.reviewed_at IS NOT NULL AND ic.reviewed_at >= f.created_at AS reviewed
FROM substitution_feedback f
LEFT JOIN canonical_products cp ON cp.id = f.canonical_id
LEFT JOIN items oi ON oi.id = f.original_item_id
LEFT JOIN items si ON si.id = f.substitute_item_id
LEFT JOIN item_canonical ic ON ic.item_id = f.substitute_item_id AND ic.canonical_id = f.canonical_id
WHERE f.verdict = 'not_good'
ORDER BY f.created_at DESC;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON beta_rejection_rate, beta_paste_to_results, beta_return_visits,
                  beta_rejected_substitutions FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON beta_rejection_rate, beta_paste_to_results, beta_return_visits,
                  beta_rejected_substitutions FROM authenticated;
  END IF;
END $$;
