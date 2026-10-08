"""Search misses: the demand signal for catalog expansion (issue #52).

``record_miss`` writes one row to ``search_misses`` when a query found nothing the parser would
accept. The catalog backlog (``supabase/queries/catalog_backlog.sql``) ranks the rows by frequency.
It is called by:

* ``GET /search`` when no hit reaches the parser floor (``NOT_FOUND_BELOW``);
* ``POST /parse-list`` for each row that comes back ``not_found``;
* ``POST /parse-recipe`` for each ingredient that goes to ``unresolved``;
* ``POST /parse-image`` later, with ``source='parse_image'``.

What is stored, and what is not (decision D11, privacy by design):

* the **normalized** query only (lower case, no punctuation, one space between words), at most
  ``MAX_QUERY_CHARS`` characters. Never the raw text, never a user, session or request id, and the
  time is rounded down to the hour by the table default;
* a query is **dropped, not stored** when it looks like personal data: an e-mail address or a link,
  a phone number or any run of seven or more digits (a barcode, an identity or card number, a
  phone number written with spaces or dashes), a string with no letter in it, or one longer than
  ``MAX_QUERY_CHARS`` (not a product name: a pasted sentence). A name written as words cannot be
  recognised by rules; the only protection against it is that nothing links a row to a person;
* rows older than ``RETENTION_DAYS`` (180) are deleted by every insert, a few hundred at a time.

Writing a miss never breaks the request: the insert and the purge run in a savepoint, any database
error is logged and swallowed, and the function answers False.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final, Literal

import psycopg
import structlog

from smartcart_api.embedding import normalize_text

log = structlog.get_logger("smartcart_api.misses")

MissSource = Literal["search", "parse_list", "parse_recipe", "parse_image"]

MAX_QUERY_CHARS: Final = 120
MIN_QUERY_CHARS: Final = 2
RETENTION_DAYS: Final = 180
PURGE_BATCH: Final = 500

_DIGIT_GLUE = re.compile(r"(?<=\d)[\s\-.()+/]+(?=\d)")  # 050-123 4567 -> 0501234567
_LONG_DIGITS = re.compile(r"\d{7,}")
_LINK = re.compile(r"://|\bwww\.|\.(?:com|co\.il|org\.il|net)\b", re.IGNORECASE)


def clean_query(text: str | None) -> str | None:
    """The normalized query to store, or None when it must not be stored."""
    if not text:
        return None
    raw = unicodedata.normalize("NFKC", text)
    if "@" in raw or _LINK.search(raw):
        return None
    if _LONG_DIGITS.search(_DIGIT_GLUE.sub("", raw)):
        return None
    query = normalize_text(raw)
    if not MIN_QUERY_CHARS <= len(query) <= MAX_QUERY_CHARS:
        return None
    if not any(ch.isalpha() for ch in query):
        return None
    return query


def record_miss(
    conn: psycopg.Connection,
    query: str | None,
    source: MissSource,
    best: float | None = None,
) -> bool:
    """Record that ``query`` found nothing acceptable; True when a row was written.

    ``best`` is the confidence of the best hit that was found but not accepted (None when the
    search found nothing). Safe to call inside a request transaction: a failure rolls back only
    its own savepoint.
    """
    cleaned = clean_query(query)
    if cleaned is None:
        return False
    confidence = None if best is None else min(max(round(float(best), 3), 0.0), 1.0)
    try:
        with conn.transaction():
            conn.execute(
                "INSERT INTO search_misses (query_norm, source, best_confidence, seen_at)"
                " VALUES (%s, %s, %s, date_trunc('hour', now()))",
                (cleaned, source, confidence),
            )
            conn.execute(
                "DELETE FROM search_misses WHERE id IN ("
                " SELECT id FROM search_misses"
                "  WHERE seen_at < now() - make_interval(days => %s)"
                "  ORDER BY seen_at LIMIT %s)",
                (RETENTION_DAYS, PURGE_BATCH),
            )
    except Exception as exc:  # a miss must never fail the request that found it
        log.warning("search miss not recorded", error=type(exc).__name__, source=source)
        return False
    return True
