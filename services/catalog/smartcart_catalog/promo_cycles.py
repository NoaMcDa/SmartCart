"""Promo cycle prediction from promo history (issue #69). A statistical baseline, no model.

Per (canonical product, chain):

1. **Windows.** Promos of the chain (chain-wide or any of its stores) on items mapped to the
   canonical at ``exact`` or ``any_brand`` (not ``needs_review``, not ``human_rejected``), from
   loaded files, with a start date not in the future and a reward the precompute applies
   (``reward_type <> 'other'``). Club-only promos count only when ``include_club`` accepts the
   club (the API passes the user's marked clubs; the default leaves them all out). Dates are
   Israel local days; a promo without an end lasts its start day. Windows that overlap or are at
   most ``MERGE_GAP_DAYS`` apart are one window (the same promo published per store, or renewed).
2. **Cycles.** ``gaps`` are the days from one window's start to the next. ``cycles_seen`` is the
   number of gaps; ``median_gap_days`` their median.
3. **Confidence** = ``n / (n + COUNT_HALF)`` x ``max(0, 1 - cv)``, where ``n`` is
   ``cycles_seen`` and ``cv`` the coefficient of variation of the gaps (sample standard
   deviation over the mean). Fewer than two gaps give 0: one gap says nothing about regularity.
4. **Next window**: the last start plus the median gap, widened by a tolerance of
   ``max(MIN_TOLERANCE_DAYS, ceil(standard deviation of the gaps))`` days before the start and
   after the end (the median promo length).
5. **Gate** (precision over recall, D5 and D10): fewer than ``MIN_CYCLES`` cycles or a confidence
   under ``MIN_CONFIDENCE`` shows no prediction (``next_expected_*`` null, advice ``unknown``).
   A window that already passed without a promo also answers ``unknown``: the rhythm broke.
6. **Advice** when the gate passes: ``buy_now`` while a promo is running, or when the next
   window opens more than ``WAIT_HORIZON_DAYS`` from today; ``wait`` when it opens within that
   horizon (or is open now). It is a hint for timing, never a promise.

Every threshold here is an estimate chosen on synthetic history (``synthetic_history``), not
measured on real promo files; ``backtest`` is the harness to re-tune them on real history. See
docs/promo-cycles.md.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

import psycopg

Advice = Literal["buy_now", "wait", "unknown"]

MIN_CYCLES = 3
MIN_CONFIDENCE = 0.6
COUNT_HALF = 1.5
MERGE_GAP_DAYS = 2
MIN_TOLERANCE_DAYS = 3
WAIT_HORIZON_DAYS = 14
HISTORY_DAYS = 730

IncludeClub = Callable[[str | None, str, Sequence[str]], bool]


@dataclass(frozen=True, order=True)
class Window:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class CycleEstimate:
    cycles_seen: int
    median_gap_days: float | None
    confidence: float
    last_start: date | None
    last_end: date | None
    next_from: date | None
    next_to: date | None
    advice: Advice


@dataclass(frozen=True)
class ChainCycle:
    chain_id: str
    chain_name: str
    estimate: CycleEstimate
    windows: tuple[Window, ...] = ()


def merge_windows(
    spans: Iterable[tuple[date, date | None]], gap_days: int = MERGE_GAP_DAYS
) -> list[Window]:
    """Overlapping or nearly adjacent promo spans as one window each, oldest first."""
    ordered = sorted((s, e if e is not None and e >= s else s) for s, e in spans)
    out: list[Window] = []
    for start, end in ordered:
        if out and (start - out[-1].end).days <= gap_days:
            last = out[-1]
            out[-1] = Window(last.start, max(last.end, end))
        else:
            out.append(Window(start, end))
    return out


def gaps_of(windows: Sequence[Window]) -> list[int]:
    return [(b.start - a.start).days for a, b in zip(windows, windows[1:], strict=False)]


def confidence(gaps: Sequence[int]) -> float:
    if len(gaps) < 2:
        return 0.0
    mean = statistics.fmean(gaps)
    if mean <= 0:
        return 0.0
    cv = statistics.stdev(gaps) / mean
    n = len(gaps)
    return round(n / (n + COUNT_HALF) * max(0.0, 1.0 - cv), 3)


def estimate(windows: Sequence[Window], today: date) -> CycleEstimate:
    """The cycle estimate for one chain's windows (oldest first) as of ``today``."""
    windows = sorted(windows)
    if not windows:
        return CycleEstimate(0, None, 0.0, None, None, None, None, "unknown")
    gaps = gaps_of(windows)
    last = windows[-1]
    median = float(statistics.median(gaps)) if gaps else None
    conf = confidence(gaps)
    unknown = CycleEstimate(len(gaps), median, conf, last.start, last.end, None, None, "unknown")
    if len(gaps) < MIN_CYCLES or conf < MIN_CONFIDENCE or median is None:
        return unknown
    tol = max(MIN_TOLERANCE_DAYS, math.ceil(statistics.stdev(gaps)))
    length = int(statistics.median(w.days for w in windows))
    start = last.start + timedelta(days=round(median))
    nxt_from = start - timedelta(days=tol)
    nxt_to = start + timedelta(days=length - 1 + tol)
    if last.start <= today <= last.end:
        advice: Advice = "buy_now"
    elif nxt_to < today:
        return unknown
    elif nxt_from <= today + timedelta(days=WAIT_HORIZON_DAYS):
        advice = "wait"
    else:
        advice = "buy_now"
    return CycleEstimate(len(gaps), median, conf, last.start, last.end, nxt_from, nxt_to, advice)


# --- backtest ------------------------------------------------------------------------------------


@dataclass
class Backtest:
    """Predictions made at the end of each historical window, judged on the next real start."""

    min_windows: int
    opportunities: int = 0
    predictions: int = 0
    hits: int = 0
    early: int = 0  # the promo came before the predicted window
    false_alarms: int = 0  # the predicted window passed with no promo starting in it

    @property
    def hit_rate(self) -> float | None:
        return round(self.hits / self.predictions, 3) if self.predictions else None

    @property
    def false_alarm_rate(self) -> float | None:
        return round(self.false_alarms / self.predictions, 3) if self.predictions else None

    @property
    def coverage(self) -> float | None:
        return round(self.predictions / self.opportunities, 3) if self.opportunities else None

    def as_dict(self) -> dict[str, object]:
        return {
            "min_windows": self.min_windows,
            "opportunities": self.opportunities,
            "predictions": self.predictions,
            "hits": self.hits,
            "early": self.early,
            "false_alarms": self.false_alarms,
            "hit_rate": self.hit_rate,
            "false_alarm_rate": self.false_alarm_rate,
            "coverage": self.coverage,
        }


def backtest(series: Iterable[Sequence[Window]], min_windows: int = MIN_CYCLES + 1) -> Backtest:
    """Walk each series forward: with the first ``k`` windows as history (``k >= min_windows``),
    predict as of the day after window ``k`` ended and compare with window ``k + 1``'s start."""
    result = Backtest(min_windows=min_windows)
    for windows in series:
        windows = sorted(windows)
        for k in range(min_windows, len(windows)):
            history, actual = windows[:k], windows[k].start
            today = history[-1].end + timedelta(days=1)
            if actual <= today:
                continue  # the next promo started before a decision day; nothing to predict
            result.opportunities += 1
            est = estimate(history, today)
            if est.next_from is None or est.next_to is None:
                continue
            result.predictions += 1
            if est.next_from <= actual <= est.next_to:
                result.hits += 1
            elif actual < est.next_from:
                result.early += 1
            else:
                result.false_alarms += 1
    return result


# --- synthetic history (tests, docs) -------------------------------------------------------------


def synthetic_history(
    seed: int,
    start: date,
    end: date,
    period_days: int,
    jitter_days: int = 0,
    duration_days: int = 7,
    skip_prob: float = 0.0,
) -> list[Window]:
    """Deterministic promo windows: every ``period_days`` +- ``jitter_days``, lasting
    ``duration_days``, each cycle skipped with ``skip_prob``. Same arguments, same windows."""
    rng = random.Random(seed)
    out: list[Window] = []
    day = start
    while day <= end:
        if rng.random() >= skip_prob:
            out.append(Window(day, min(day + timedelta(days=duration_days - 1), end)))
        day += timedelta(days=max(1, period_days + rng.randint(-jitter_days, jitter_days)))
    return out


def irregular_history(
    seed: int, start: date, end: date, low: int, high: int, duration_days: int = 7
) -> list[Window]:
    """Windows with gaps drawn uniformly from [low, high] days: no rhythm to find."""
    rng = random.Random(seed)
    out: list[Window] = []
    day = start
    while day <= end:
        out.append(Window(day, min(day + timedelta(days=duration_days - 1), end)))
        day += timedelta(days=rng.randint(low, high))
    return out


def seed_promo_history(
    conn: psycopg.Connection,
    chain_id: str,
    item_ids: Sequence[int],
    windows: Sequence[Window],
    *,
    prefix: str = "SYN",
    store_id: int | None = None,
    club_only: bool = False,
    club_name: str | None = None,
    reward_type: str = "percent",
) -> list[int]:
    """Insert ``windows`` as promos of ``chain_id`` on ``item_ids`` (tests and the demo)."""
    ids = []
    for n, w in enumerate(windows):
        pid = conn.execute(
            "INSERT INTO promos (chain_id, store_id, promo_id, description, starts_at, ends_at,"
            " club_only, club_name, min_qty, reward_type, reward_value)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, 20) RETURNING id",
            (
                chain_id,
                store_id,
                f"{prefix}-{n}",
                f"מבצע {prefix} {n}",
                datetime.combine(w.start, time(6), UTC),
                datetime.combine(w.end, time(20), UTC),
                club_only,
                club_name,
                reward_type,
            ),
        ).fetchone()[0]
        for iid in item_ids:
            conn.execute("INSERT INTO promo_items (promo_id, item_id) VALUES (%s, %s)", (pid, iid))
        ids.append(pid)
    return ids


# --- from the database ---------------------------------------------------------------------------

_SPANS_SQL = """
SELECT DISTINCT p.chain_id, ch.name, ch.club_names, p.club_only, p.club_name,
       (p.starts_at AT TIME ZONE 'Asia/Jerusalem')::date AS d0,
       (p.ends_at AT TIME ZONE 'Asia/Jerusalem')::date AS d1
FROM promos AS p
JOIN promo_items AS pi ON pi.promo_id = p.id
JOIN item_canonical AS ic ON ic.item_id = pi.item_id
JOIN chains AS ch ON ch.id = p.chain_id
WHERE ic.canonical_id = %(cid)s
  AND ic.flex_level IN ('exact', 'any_brand')
  AND NOT ic.needs_review AND NOT ic.human_rejected
  AND p.reward_type <> 'other'
  AND p.starts_at IS NOT NULL
  AND (p.starts_at AT TIME ZONE 'Asia/Jerusalem')::date BETWEEN %(since)s AND %(today)s
  AND (p.file_id IS NULL
       OR EXISTS (SELECT 1 FROM file_tracking AS f WHERE f.id = p.file_id AND f.status = 'loaded'))
"""


@dataclass
class _ChainSpans:
    name: str
    spans: list[tuple[date, date | None]] = field(default_factory=list)


def load_spans(
    conn: psycopg.Connection,
    canonical_id: int,
    today: date,
    include_club: IncludeClub | None = None,
    history_days: int = HISTORY_DAYS,
) -> dict[str, _ChainSpans]:
    out: dict[str, _ChainSpans] = {}
    rows = conn.execute(
        _SPANS_SQL,
        {"cid": canonical_id, "today": today, "since": today - timedelta(days=history_days)},
    ).fetchall()
    for chain_id, name, club_names, club_only, club_name, d0, d1 in rows:
        entry = out.setdefault(chain_id, _ChainSpans(name))
        if club_only and (
            include_club is None or not include_club(club_name, name, club_names or [])
        ):
            continue
        entry.spans.append((d0, d1))
    return out


def promo_cycles(
    conn: psycopg.Connection,
    canonical_id: int,
    today: date | None = None,
    include_club: IncludeClub | None = None,
) -> list[ChainCycle]:
    """One estimate per chain that has promo history for the canonical, by chain id."""
    today = today or datetime.now(UTC).date()
    out = []
    for chain_id, entry in sorted(load_spans(conn, canonical_id, today, include_club).items()):
        windows = merge_windows(entry.spans)
        if not windows:
            continue  # only club promos the user does not have
        out.append(ChainCycle(chain_id, entry.name, estimate(windows, today), tuple(windows)))
    return out
