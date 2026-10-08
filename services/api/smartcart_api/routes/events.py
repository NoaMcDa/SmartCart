"""First-party product events for the closed beta (issue #40, decisions D10 and D11).

``POST /events`` takes a batch of ``{name, props, session_id}`` and stores it in ``events``. There
is no third-party analytics: this is the only place the web app reports what people do.

What may be stored is enforced here, not trusted from the client:

* ``name`` must be one of ``EVENT_PROPS`` (the same list the OpenAPI schema publishes as an
  enum);
* every key in ``props`` must be allowlisted for that event, and its value is either an integer
  in a fixed range or a member of a fixed set. There is no free-text key, so a name, an address,
  a search string or a list item cannot be stored by mistake or on purpose;
* required keys are checked, because the beta metrics need them (``substitutions_shown`` without
  ``count`` would corrupt the rejection rate).

A bad event rejects the whole batch with 422 and a list of reasons; nothing is stored. The user id
is taken from the Supabase JWT when a valid one is sent; an invalid or expired token is treated
as anonymous (losing a beta event is worse than recording it without a user). Rate limit: at most
``EVENTS_PER_SESSION_PER_MINUTE`` events per session id per minute, counted in the table so it
holds across API processes; over the limit the batch is dropped with 429 and ``Retry-After``.
The limit is a proposal. See docs/beta-plan.md for the events and the SQL views over them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg.types.json import Jsonb

from smartcart_api import schemas
from smartcart_api.auth import User, optional_user
from smartcart_api.db import get_conn

router = APIRouter(prefix="/events", tags=["events"])

EVENTS_PER_SESSION_PER_MINUTE = 120

FLEX_LEVELS = frozenset({"exact", "any_brand", "close"})
PLATFORMS = ("ios", "android", "desktop", "other")
# Speech recognizers the voice list may use: the browser's Web Speech API, a server-side
# recognizer, or the fallback of typing instead.
VOICE_ENGINES = ("web_speech", "server", "manual")


@dataclass(frozen=True)
class Key:
    """One allowlisted property: an integer range or a set of allowed strings."""

    low: int | None = None
    high: int | None = None
    choices: frozenset[str] | None = None
    required: bool = False

    def problem(self, value: object) -> str | None:
        if self.choices is not None:
            if isinstance(value, str) and value in self.choices:
                return None
            return f"must be one of {sorted(self.choices)}"
        if isinstance(value, bool) or not isinstance(value, int):
            return "must be an integer"
        if self.low is not None and value < self.low or self.high is not None and value > self.high:
            return f"must be between {self.low} and {self.high}"
        return None


def _choices(*values: str, required: bool = False) -> Key:
    return Key(choices=frozenset(values), required=required)


EVENT_PROPS: dict[str, dict[str, Key]] = {
    # The app (or the PWA) was opened: one per visit. The actor of return visits.
    "app_opened": {"surface": _choices("web", "pwa"), "platform": _choices(*PLATFORMS)},
    # A static page was viewed (SEO pages, methodology, basket index): SEO to app funnel.
    "page_viewed": {
        "page_type": _choices("category", "product", "methodology", "basket_index", "other",
                              required=True)  # fmt: skip
    },
    # A shopping list was pasted: the start of paste-to-results.
    "list_pasted": {"item_count": Key(0, 200, required=True)},
    # Results are on screen. duration_ms runs from the paste to now (client clock).
    "results_shown": {
        "duration_ms": Key(0, 600_000, required=True),
        "item_count": Key(0, 200),
        "store_count": Key(0, 50),
    },
    # Substitutions were listed in a results view: the denominator of the rejection rate.
    "substitutions_shown": {
        "flex_level": _choices(*FLEX_LEVELS, required=True),
        "count": Key(1, 200, required=True),
    },
    # The user answered on a substitution card: not_good is the numerator.
    "substitution_verdict": {
        "flex_level": _choices(*FLEX_LEVELS, required=True),
        "verdict": _choices("not_good", "kept_original", "accepted", required=True),
    },
    "flex_changed": {"flex_level": _choices(*FLEX_LEVELS, required=True)},
    "split_viewed": {},
    "gap_reported": {},
    # --- phase 2 surfaces (#101, #102). No barcodes, item ids or prices: counts and outcomes only.
    # The camera opened on /scan. engine says which decoder was available.
    "scan_started": {"engine": _choices("native", "zxing", "manual")},
    # A scan ended. outcome is what the user saw; duration_ms runs from scan_started.
    "scan_completed": {
        "outcome": _choices("found", "not_found", "no_price", "cancelled", "error", required=True),
        "duration_ms": Key(0, 600_000),
        "engine": _choices("native", "zxing", "manual"),
    },
    # A price alert was created from product detail or the alerts screen.
    "alert_created": {"flex_level": _choices(*FLEX_LEVELS), "source": _choices("product", "alerts")},
    # Smart cart: a suggested swap was applied, undone, or dismissed (dismissal holds until prices change).
    "swap_applied": {"flex_level": _choices(*FLEX_LEVELS), "saving_agorot": Key(0, 100_000)},
    "swap_undone": {"flex_level": _choices(*FLEX_LEVELS)},
    "swap_dismissed": {"flex_level": _choices(*FLEX_LEVELS)},
    # Shared lists: an invite link was created; an invite was accepted.
    "list_shared": {"role": _choices("editor", "viewer")},
    "share_accepted": {"role": _choices("editor", "viewer")},
    # --- phase 3: voice list. No transcript, no audio: the outcome and counts only.
    # The microphone opened. engine says which recognizer was used.
    "voice_started": {"engine": _choices(*VOICE_ENGINES)},
    # A voice session ended. outcome is what the user saw; duration_ms runs from voice_started.
    "voice_completed": {
        "outcome": _choices("parsed", "empty", "cancelled", "error", required=True),
        "duration_ms": Key(0, 600_000),
        "item_count": Key(0, 200),
    },
    # --- finish round. No ids, names, prices, barcodes or images: platform, outcomes and counts.
    # The PWA was installed (beforeinstallprompt accepted or display-mode standalone first seen).
    "pwa_installed": {"platform": _choices(*PLATFORMS)},
    # Web push: the user allowed notifications; a notification was opened.
    # The push permission prompt was shown by our flow (the denominator of the opt-in rate, D15).
    "push_prompt_shown": {"platform": _choices(*PLATFORMS)},
    "push_opt_in": {"platform": _choices(*PLATFORMS)},
    "push_opened": {"platform": _choices(*PLATFORMS)},
    # In-store mode was opened with a plan.
    "store_mode_used": {"plan": _choices("single", "split"), "platform": _choices(*PLATFORMS)},
    # A receipt or list photo was read (#61, #68).
    "image_parsed": {
        "kind": _choices("receipt", "list", required=True),
        "outcome": _choices("parsed", "empty", "refused", "error", required=True),
        "item_count": Key(0, 200),
        "duration_ms": Key(0, 600_000),
    },
    # The user opened a chain's online store from a plan (#72): no chain id, only the action.
    "cart_handoff": {"action": _choices("copy", "share", "open_site", "open_item", required=True)},
    # The UI language was switched (#73).
    "locale_changed": {"locale": _choices("he", "ar", required=True)},
}


def validate_event(index: int, event: schemas.EventIn) -> list[str]:
    """Reasons this event may not be stored (empty when it is fine)."""
    keys = EVENT_PROPS.get(event.name)
    if keys is None:
        return [f"events[{index}]: unknown event name {event.name!r}"]
    problems = []
    for key, value in event.props.items():
        rule = keys.get(key)
        if rule is None:
            problems.append(f"events[{index}].props.{key}: key not allowed for {event.name}")
            continue
        why = rule.problem(value)
        if why:
            problems.append(f"events[{index}].props.{key}: {why}")
    for key, rule in keys.items():
        if rule.required and key not in event.props:
            problems.append(f"events[{index}].props.{key}: required for {event.name}")
    return problems


def maybe_user(authorization: Annotated[str | None, Header()] = None) -> User | None:
    """The signed-in user, or None for no token or one that does not verify."""
    try:
        return optional_user(authorization)
    except HTTPException:
        return None


@router.post("", response_model=schemas.EventsAck, summary="Record a batch of beta events")
def post_events(
    body: schemas.EventsRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    user: Annotated[User | None, Depends(maybe_user)],
) -> schemas.EventsAck:
    problems = [p for i, e in enumerate(body.events) for p in validate_event(i, e)]
    if problems:
        raise HTTPException(status_code=422, detail=problems)

    incoming = Counter(e.session_id for e in body.events)
    recent = dict(
        conn.execute(
            "SELECT session_id, count(*) FROM events"
            " WHERE session_id = ANY(%s) AND created_at > now() - interval '1 minute'"
            " GROUP BY session_id",
            (list(incoming),),
        ).fetchall()
    )
    if any(recent.get(s, 0) + n > EVENTS_PER_SESSION_PER_MINUTE for s, n in incoming.items()):
        raise HTTPException(
            status_code=429,
            detail=f"at most {EVENTS_PER_SESSION_PER_MINUTE} events per session per minute",
            headers={"Retry-After": "60"},
        )

    user_id = user.id if user else None
    with conn.cursor() as cur:
        cur.executemany(
            # a token for an account that no longer exists is stored as anonymous, not an error
            "INSERT INTO events (user_id, session_id, name, props)"
            " VALUES ((SELECT id FROM auth.users WHERE id = %s), %s, %s, %s)",
            [(user_id, e.session_id, e.name, Jsonb(e.props)) for e in body.events],
        )
    return schemas.EventsAck(accepted=len(body.events))
