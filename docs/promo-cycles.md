# Promo cycle prediction (issue #69)

Some promos come back on a rhythm. When the history shows one, SmartCart can say "this promo has
returned about every 6 weeks (confidence: medium)" and suggest waiting or buying now. It is a
hint for timing, never a promise, and it always carries its confidence and evidence (D10).

Status: **built and tested on synthetic history only.** There is no real promo history yet (the
catalog runs on synthetic fixtures until real transparency files load, see
[phase-2-status.md](phase-2-status.md)). Every threshold below is an **estimate** chosen on
synthetic data; the backtest numbers are **synthetic**, not a measured result. The roadmap's
"coffee promo returns roughly every 6 weeks" is an illustration, not a finding.

| Piece | Where |
|---|---|
| Method, synthetic generator, backtest | `services/catalog/smartcart_catalog/promo_cycles.py` |
| CLI | `smartcart-catalog promo-cycles`, `smartcart-catalog promo-backtest` (`cli_promo.py`) |
| API | `GET /promo-cycles/{canonical_id}?clubs=` (`services/api/smartcart_api/routes/promo_cycles.py`, [api.md](api.md)) |
| Tests | `services/catalog/tests/test_promo_cycles.py`, `services/api/tests/test_promo_cycles_route.py` |

## Method: a statistical baseline

Per (canonical product, chain):

1. **Promo history.** Promos of the chain (chain-wide or any of its stores) on items mapped to
   the canonical at `exact` or `any_brand` (not `needs_review`, not `human_rejected`), from loaded
   files only, with a start date in the last two years and not in the future, and a reward the
   precompute applies (`reward_type <> 'other'`). Dates are Israel-local days; a promo without an
   end lasts its start day.
2. **Windows.** Overlapping promos, or promos at most 2 days apart, are one window: the same
   promo is published per store and per item, and a renewed promo is the same window.
3. **Cycles.** `gaps` are the days from one window's start to the next. `cycles_seen` = the
   number of gaps; `median_gap_days` = their median (the median, not the mean, so one skipped
   cycle does not move it much).
4. **Confidence** = `n / (n + 1.5) x max(0, 1 - cv)`, with `n = cycles_seen` and `cv` the
   coefficient of variation of the gaps (sample standard deviation over the mean). The first
   factor grows with evidence (3 cycles 0.67, 6 cycles 0.80, 10 cycles 0.87); the second falls
   with irregularity (gaps of 38, 46, 41 and 43 days: cv 0.08). Fewer than two gaps give 0: one
   gap says nothing about regularity.
5. **Next window.** Start = last start + median gap. The window opens `tolerance` days before that
   and closes `tolerance` days after the median promo length, `tolerance = max(3, ceil(standard
   deviation of the gaps))` days.
6. **Gate.** Fewer than **3 cycles** or a confidence under **0.6** shows no prediction:
   `next_expected_from` and `next_expected_to` are null and `advice` is `unknown`, while
   `cycles_seen`, `median_gap_days`, `confidence` and `last_promo_ends` are still returned as
   evidence. A predicted window that already passed with no promo also answers `unknown`: the
   rhythm broke, and saying "wait" again would be a guess.
7. **Advice** when the gate passes:
   - `buy_now` while a promo is running (the last window covers today), or when the next window
     opens more than **14 days** from today (do not delay a purchase for a promo that far off);
   - `wait` when the next window opens within 14 days, or is open now without a promo yet.

Club-only promos count only for a club the user marked (`clubs` on the API, `--club` on the CLI),
with the same rule as /compare (`basket.club_member`); without one they are left out, so a
non-member is never told to wait for a deal they cannot get.

| Threshold | Value | Kind |
|---|---|---|
| `MIN_CYCLES` | 3 | estimate |
| `MIN_CONFIDENCE` | 0.6 | estimate |
| `COUNT_HALF` (evidence factor `n / (n + 1.5)`) | 1.5 | estimate |
| `MERGE_GAP_DAYS` | 2 | estimate |
| `MIN_TOLERANCE_DAYS` | 3 | estimate |
| `WAIT_HORIZON_DAYS` | 14 | estimate |
| `HISTORY_DAYS` | 730 | design choice |

A prediction with exactly 3 perfectly regular cycles has confidence 0.667 and passes; 3 cycles
with a cv above 0.1 do not. That is deliberate (precision over recall, D5): a wrong "wait" costs
the user money and trust, a missing hint costs nothing.

## Backtest (synthetic)

`backtest(series)` walks each history forward. With the first `k` windows as history (`k >= 4`,
so the gate can pass), it predicts as of the day after window `k` ended and compares with the real
start of window `k + 1`:

- **hit**: the next promo started inside the predicted window;
- **early**: it started before the window opened (a user told to wait would still have seen it
  if they checked, but the window was wrong);
- **false alarm**: the window passed with no promo starting in it;
- **coverage**: predictions made over opportunities (the gate abstains on the rest).

`hit_rate = hits / predictions`, `false_alarm_rate = false alarms / predictions`.

Measured with `uv run smartcart-catalog promo-backtest --synthetic` (540 days of history, 20
deterministic series of each kind; **synthetic, not real promo data**):

| Series kind | Opportunities | Predictions | Coverage | Hit rate | Early | False-alarm rate |
|---|---|---|---|---|---|---|
| Regular, every 28 to 49 days, jitter 0 to 2 days | 224 | 224 | 1.00 | 0.991 | 2 | 0.000 |
| Every 42 days, jitter 5 days, 10-day promos | 186 | 184 | 0.99 | 0.815 | 34 | 0.000 |
| Every 35 days, jitter 3 days, a quarter of cycles skipped | 166 | 44 | 0.27 | 0.727 | 4 | 0.182 |
| Irregular, gaps drawn from 10 to 90 days | 142 | 9 | 0.06 | 0.333 | 6 | 0.000 |
| All | 718 | 461 | 0.64 | 0.883 | 46 | 0.017 |

Reading it: on a clean rhythm the baseline is right almost every time; on jittered gaps the
3-day minimum tolerance is narrower than a 5-day jitter, so some promos come early; skipped
cycles are the main source of false alarms, and the gate keeps most of those series out; on
noise the gate abstains 94 % of the time. Minimum history used: 4 windows (3 cycles), as the gate
requires.

**Before any prediction is shown to users**, rerun `smartcart-catalog promo-backtest` (without
`--synthetic`) on at least six months of real promo history, report the hit and false-alarm rates
per chain in the PR, and retune the thresholds. Issue #69 asks for exactly this; it cannot be done
before real files load.

## Limits

- **Promo ids.** `promos` is unique on (chain, store, the chain's promo id) and the loader
  upserts. If a chain reuses a promo id for a returning promo, the earlier window is overwritten
  and the history loses cycles. To check on real files; if it happens, the loader must keep the
  history (a promo history table, or the id plus the start date as the key).
- **Store-level promos** are merged into one chain window. A promo that runs in a few stores only
  counts like a chain-wide one; per-store cycles are not modeled.
- **Expected discount** is not estimated yet (issue #69 mentions it); the response carries timing
  only.
- **Announced future promos** (a start date after today) are left out; the prediction uses the
  past only.
- **Almost permanent promos** (a promo nearly every week) produce short gaps and `buy_now` most of
  the time, which is right but not informative; not special-cased.
- **No model.** A model is only worth trying if this baseline fails the real backtest.
- **When it runs.** The API computes the estimate per request from `promos` (one query per
  canonical); it is not on the /compare or /optimize path. Precomputing it after the nightly load
  (issue #69) is not built; do it if the per-request query becomes slow on real data.

## UI wording (for the web app)

Show the hint only when `advice` is not `unknown`, always with the evidence: "המבצע חזר בערך כל
`median_gap_days` ימים (`cycles_seen` פעמים, ודאות: `confidence`)". Keep a "buy now anyway" path,
never push to delay an essential without showing the risk, and say it is a prediction, not a
promise.
