-- Native-app decision metrics (issue #56, docs/decisions.md D15, docs/beta-plan.md section 8).
--
-- Views over the first-party events table (20261007120000_events.sql), no new data collected. They
-- answer one question: is the installable web app (D1) holding people, and is something only a
-- native app can do (reliable iOS push, store mode that survives a locked screen) getting in the
-- way? `smartcart-catalog native-report` prints them with their sample sizes.
--
-- Conventions, as in the beta views:
--   * weeks are ISO weeks in Israel time (Asia/Jerusalem), starting Monday;
--   * an actor is the signed-in user id, else the browser's random session id. The same person on
--     two browsers, or before and after signing in, is two actors. An installed iOS PWA keeps its
--     storage apart from Safari's, so an anonymous iOS install is also a new actor. Every rate
--     below is therefore a lower bound on retention and an upper bound on "never installed";
--   * every rate comes with the counts it was computed from, and is NULL (not 0) when the
--     denominator is 0, so a reader cannot mistake "no data" for "nobody".
--
-- Nothing here is readable through the Supabase data API (security_invoker, no grants).

-- The five events that matter, with the Israel-time week and day and the actor.
CREATE VIEW native_events WITH (security_invoker = true) AS
SELECT (date_trunc('week', created_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
       (created_at AT TIME ZONE 'Asia/Jerusalem')::date AS day,
       coalesce(user_id::text, session_id) AS actor,
       name,
       props
FROM events
WHERE name IN ('app_opened', 'pwa_installed', 'push_opt_in', 'push_opened', 'store_mode_used');

-- 1. Cohort retention. The cohort is the week of an actor's first app_opened. D1, D7 and D30 are
--    "opened the app again exactly 1, 7, 30 days after the first open" (Israel dates), the usual
--    classic definition. An actor counts in the denominator of Dn only when day n is already over
--    (first open + n < today), so a young cohort is never penalised for time that has not passed.
--    With a few dozen beta users these are noisy: read the *_eligible columns first.
CREATE VIEW native_cohort_retention WITH (security_invoker = true) AS
WITH opens AS (
  SELECT DISTINCT actor, day FROM native_events WHERE name = 'app_opened'
), firsts AS (
  SELECT actor, min(day) AS first_day FROM opens GROUP BY actor
), today AS (
  SELECT (now() AT TIME ZONE 'Asia/Jerusalem')::date AS d
), returns AS (
  SELECT f.actor, f.first_day,
         coalesce(bool_or(o.day = f.first_day + 1), false)  AS d1,
         coalesce(bool_or(o.day = f.first_day + 7), false)  AS d7,
         coalesce(bool_or(o.day = f.first_day + 30), false) AS d30
  FROM firsts f
  LEFT JOIN opens o ON o.actor = f.actor AND o.day > f.first_day AND o.day <= f.first_day + 30
  GROUP BY f.actor, f.first_day
)
SELECT date_trunc('week', r.first_day)::date AS cohort_week,
       count(*) AS cohort_size,
       count(*) FILTER (WHERE r.first_day + 1 < t.d) AS d1_eligible,
       count(*) FILTER (WHERE r.first_day + 1 < t.d AND r.d1) AS d1_retained,
       round(count(*) FILTER (WHERE r.first_day + 1 < t.d AND r.d1)::numeric
             / nullif(count(*) FILTER (WHERE r.first_day + 1 < t.d), 0), 4) AS d1_rate,
       count(*) FILTER (WHERE r.first_day + 7 < t.d) AS d7_eligible,
       count(*) FILTER (WHERE r.first_day + 7 < t.d AND r.d7) AS d7_retained,
       round(count(*) FILTER (WHERE r.first_day + 7 < t.d AND r.d7)::numeric
             / nullif(count(*) FILTER (WHERE r.first_day + 7 < t.d), 0), 4) AS d7_rate,
       count(*) FILTER (WHERE r.first_day + 30 < t.d) AS d30_eligible,
       count(*) FILTER (WHERE r.first_day + 30 < t.d AND r.d30) AS d30_retained,
       round(count(*) FILTER (WHERE r.first_day + 30 < t.d AND r.d30)::numeric
             / nullif(count(*) FILTER (WHERE r.first_day + 30 < t.d), 0), 4) AS d30_rate
FROM returns r CROSS JOIN today t
GROUP BY 1
ORDER BY 1 DESC;

-- 2. Installs by platform. pwa_installed {platform}: the install prompt was accepted, or the app
--    was first seen in standalone mode. installers = distinct actors; the denominator is the
--    week's active actors (app_opened), whatever their platform (app_opened carries none).
CREATE VIEW native_installs_by_platform WITH (security_invoker = true) AS
WITH active AS (
  SELECT week, count(DISTINCT actor) AS active_users
  FROM native_events WHERE name = 'app_opened' GROUP BY week
), installs AS (
  SELECT week, coalesce(props->>'platform', 'unknown') AS platform,
         count(*) AS installs, count(DISTINCT actor) AS installers
  FROM native_events WHERE name = 'pwa_installed' GROUP BY 1, 2
)
SELECT i.week, i.platform, i.installs, i.installers,
       coalesce(a.active_users, 0) AS active_users,
       round(i.installers::numeric / nullif(a.active_users, 0), 4) AS installers_per_active_user
FROM installs i LEFT JOIN active a USING (week)
ORDER BY i.week DESC, i.platform;

-- 3. Push. Opt-in rate = actors who allowed notifications / the week's active actors (there is no
--    "prompt shown" event, so this is not the rate among people who were asked; it is a floor).
--    Open rate = push_opened events / pushes the server delivered that week
--    (alert_deliveries.channel = 'push'). Opens are reported by the client, so the rate undercounts
--    people who open the notification with the app in a context that does not send events.
CREATE VIEW native_push_engagement WITH (security_invoker = true) AS
WITH active AS (
  SELECT week, count(DISTINCT actor) AS active_users
  FROM native_events WHERE name = 'app_opened' GROUP BY week
), optin AS (
  SELECT week, count(DISTINCT actor) AS opt_in_users, count(*) AS opt_in_events
  FROM native_events WHERE name = 'push_opt_in' GROUP BY week
), opened AS (
  SELECT week, count(*) AS push_opened
  FROM native_events WHERE name = 'push_opened' GROUP BY week
), sent AS (
  SELECT (date_trunc('week', delivered_at AT TIME ZONE 'Asia/Jerusalem'))::date AS week,
         count(*) AS pushes_sent
  FROM alert_deliveries WHERE channel = 'push' GROUP BY 1
), weeks AS (
  SELECT week FROM active UNION SELECT week FROM optin
  UNION SELECT week FROM opened UNION SELECT week FROM sent
)
SELECT w.week,
       coalesce(a.active_users, 0) AS active_users,
       coalesce(o.opt_in_users, 0) AS opt_in_users,
       coalesce(o.opt_in_events, 0) AS opt_in_events,
       round(coalesce(o.opt_in_users, 0)::numeric / nullif(a.active_users, 0), 4) AS opt_in_rate,
       coalesce(s.pushes_sent, 0) AS pushes_sent,
       coalesce(p.push_opened, 0) AS push_opened,
       round(coalesce(p.push_opened, 0)::numeric / nullif(s.pushes_sent, 0), 4) AS push_open_rate
FROM weeks w
LEFT JOIN active a USING (week)
LEFT JOIN optin o USING (week)
LEFT JOIN opened p USING (week)
LEFT JOIN sent s USING (week)
ORDER BY w.week DESC;

-- 4. In-store mode per active user. store_mode_used {plan, platform}: store mode was opened with a
--    plan. The share is distinct store-mode actors / the week's active actors (weeks with no
--    store-mode use are listed too, with 0, so the share is never computed over the good weeks
--    only); events per user says how often a user who tries it comes back to it within the week.
CREATE VIEW native_store_mode_usage WITH (security_invoker = true) AS
WITH active AS (
  SELECT week, count(DISTINCT actor) AS active_users
  FROM native_events WHERE name = 'app_opened' GROUP BY week
), used AS (
  SELECT week,
         count(DISTINCT actor) AS store_mode_users,
         count(*) AS store_mode_events,
         count(*) FILTER (WHERE props->>'plan' = 'single') AS single_events,
         count(*) FILTER (WHERE props->>'plan' = 'split') AS split_events
  FROM native_events WHERE name = 'store_mode_used' GROUP BY week
)
SELECT coalesce(a.week, u.week) AS week,
       coalesce(a.active_users, 0) AS active_users,
       coalesce(u.store_mode_users, 0) AS store_mode_users,
       coalesce(u.store_mode_events, 0) AS store_mode_events,
       coalesce(u.single_events, 0) AS single_events,
       coalesce(u.split_events, 0) AS split_events,
       round(coalesce(u.store_mode_users, 0)::numeric / nullif(a.active_users, 0), 4)
         AS store_mode_user_share,
       round(u.store_mode_events::numeric / nullif(u.store_mode_users, 0), 2)
         AS events_per_store_mode_user
FROM active a FULL JOIN used u USING (week)
ORDER BY 1 DESC;

-- 5. The platform funnel over all time: of the actors seen with a platform on any of the four
--    platform-tagged events (install, push opt-in, push open, store mode), how many installed the
--    PWA and how many allowed push. For iOS this is the measurable form of "blocked by PWA push
--    limits": web push on iOS works only from an installed PWA, so an iOS actor who used the app
--    and never installed cannot be reached. Tagged events are fired by people who did something,
--    so actors_seen undercounts people who only browsed; read ios_not_installed_share as an
--    estimate of the share among engaged iOS users, not of all iOS users.
CREATE VIEW native_platform_funnel WITH (security_invoker = true) AS
WITH tagged AS (
  SELECT coalesce(props->>'platform', 'unknown') AS platform, actor, name
  FROM native_events WHERE name <> 'app_opened'
)
SELECT platform,
       count(DISTINCT actor) AS actors_seen,
       count(DISTINCT actor) FILTER (WHERE name = 'pwa_installed') AS installers,
       count(DISTINCT actor) FILTER (WHERE name = 'push_opt_in') AS push_opt_in_users,
       count(DISTINCT actor) FILTER (WHERE name = 'push_opened') AS push_opened_users,
       count(DISTINCT actor) FILTER (WHERE name = 'store_mode_used') AS store_mode_users,
       round(count(DISTINCT actor) FILTER (WHERE name = 'pwa_installed')::numeric
             / nullif(count(DISTINCT actor), 0), 4) AS installed_share,
       round(1 - count(DISTINCT actor) FILTER (WHERE name = 'pwa_installed')::numeric
             / nullif(count(DISTINCT actor), 0), 4) AS not_installed_share
FROM tagged
GROUP BY platform
ORDER BY platform;

DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format(
        'REVOKE ALL ON native_events, native_cohort_retention, native_installs_by_platform,'
        ' native_push_engagement, native_store_mode_usage, native_platform_funnel FROM %I', r);
    END IF;
  END LOOP;
END $$;
