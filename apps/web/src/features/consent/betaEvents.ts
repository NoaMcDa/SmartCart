/**
 * Beta instrumentation call sites (docs/beta-plan.md section 5). Every function here forwards to
 * `trackEvent` with only the allowlisted properties: integers in the API's ranges and fixed
 * strings. No list text, product name, store or id ever reaches an event. `trackEvent` itself
 * does nothing unless the person accepted the consent screen (`features/seo/track.ts`), so these
 * helpers are safe to call unconditionally.
 */
import type { FlexLevel } from "@/api/client";
import { trackEvent } from "@/features/seo/track";

/** The API accepts durations up to ten minutes; a longer wait is not "paste to results". */
const MAX_DURATION_MS = 600_000;
const MAX_ITEMS = 200;
const MAX_STORES = 50;

const clampInt = (value: number, max: number): number =>
  Math.min(max, Math.max(0, Math.round(Number.isFinite(value) ? value : 0)));

let pastedAt: number | null = null;

/** The list builder parsed a pasted list with `itemCount` rows: starts paste-to-results. */
export function reportListPasted(itemCount: number, now: number = Date.now()): void {
  pastedAt = now;
  trackEvent("list_pasted", { item_count: clampInt(itemCount, MAX_ITEMS) });
}

/**
 * The results are on screen. Reported once per paste (the clock is cleared), and only when the
 * paste happened in this page session: a reload on /compare has no paste to measure from, and a
 * wait over ten minutes is treated as a different session of use, not a slow response.
 */
export function reportResultsShown(
  info: { itemCount: number; storeCount: number },
  now: number = Date.now(),
): void {
  if (pastedAt === null) return;
  const duration = now - pastedAt;
  pastedAt = null;
  if (duration < 0 || duration > MAX_DURATION_MS) return;
  trackEvent("results_shown", {
    duration_ms: Math.round(duration),
    item_count: clampInt(info.itemCount, MAX_ITEMS),
    store_count: clampInt(info.storeCount, MAX_STORES),
  });
}

/** One `substitutions_shown` per flexibility level that lists substitutes (the rate's denominator). */
export function reportSubstitutionsShown(counts: Partial<Record<FlexLevel, number>>): void {
  for (const level of ["exact", "any_brand", "close"] as const) {
    const count = counts[level] ?? 0;
    if (count >= 1) {
      trackEvent("substitutions_shown", { flex_level: level, count: clampInt(count, 200) });
    }
  }
}

/** The answer on a substitution card (`not_good` is the rate's numerator). */
export function reportSubstitutionVerdict(
  level: FlexLevel | null,
  verdict: "not_good" | "kept_original" | "accepted",
): void {
  if (level === null) return; // the API requires a level; never guess one
  trackEvent("substitution_verdict", { flex_level: level, verdict });
}

export function reportFlexChanged(level: FlexLevel): void {
  trackEvent("flex_changed", { flex_level: level });
}

export function reportSplitViewed(): void {
  trackEvent("split_viewed");
}

export function reportGapReported(): void {
  trackEvent("gap_reported");
}

// ---------------------------------------------------------------------------------------------
// Phase 2 surfaces (#101): scan, alerts, smart cart, shared lists. Counts and outcomes only; a
// barcode, an item id, a name or a price never goes into an event.

export type ScanEngine = "native" | "zxing" | "manual";
export type ScanOutcome = "found" | "not_found" | "no_price" | "cancelled" | "error";

/** A scan began: the camera decoder that is available, or manual entry. */
export function reportScanStarted(engine?: ScanEngine): void {
  trackEvent("scan_started", engine ? { engine } : {});
}

/** A scan ended with what the shopper saw, and how long it took from `scan_started`. */
export function reportScanCompleted(info: {
  outcome: ScanOutcome;
  durationMs?: number;
  engine?: ScanEngine;
}): void {
  trackEvent("scan_completed", {
    outcome: info.outcome,
    ...(info.durationMs !== undefined
      ? { duration_ms: clampInt(info.durationMs, MAX_DURATION_MS) }
      : {}),
    ...(info.engine ? { engine: info.engine } : {}),
  });
}

/** A price alert was created from product detail or the alerts screen. */
export function reportAlertCreated(level: FlexLevel | null, source: "product" | "alerts"): void {
  trackEvent("alert_created", { source, ...(level ? { flex_level: level } : {}) });
}

const MAX_SAVING_AGOROT = 100_000;

/** `savingIls` is in shekels; the event carries whole agorot, capped at the API's range. */
export function reportSwapApplied(level: FlexLevel | null, savingIls: number): void {
  trackEvent("swap_applied", {
    ...(level ? { flex_level: level } : {}),
    saving_agorot: clampInt(savingIls * 100, MAX_SAVING_AGOROT),
  });
}

export function reportSwapUndone(level: FlexLevel | null): void {
  trackEvent("swap_undone", level ? { flex_level: level } : {});
}

export function reportSwapDismissed(level: FlexLevel | null): void {
  trackEvent("swap_dismissed", level ? { flex_level: level } : {});
}

/** An invite link was created for a shared list. */
export function reportListShared(role: "editor" | "viewer"): void {
  trackEvent("list_shared", { role });
}

/** The person joined a shared list from an invite link. The joiner is not told the role. */
export function reportShareAccepted(): void {
  trackEvent("share_accepted");
}

// ---------------------------------------------------------------------------------------------
// Voice list input (#65). The transcript, the items and their names never go into an event.

/** parsed = the dictated list was added; empty = nothing was heard; error = denied, no microphone, failure. */
export type VoiceOutcome = "parsed" | "empty" | "cancelled" | "error";

/** The person tapped "start recording" in the voice sheet; the Web Speech API is the engine here. */
export function reportVoiceStarted(): void {
  trackEvent("voice_started", { engine: "web_speech" });
}

/** One voice attempt ended. `itemCount` is the number of rows /parse-list returned (outcome `parsed`). */
export function reportVoiceCompleted(info: {
  outcome: VoiceOutcome;
  durationMs?: number;
  itemCount?: number;
}): void {
  trackEvent("voice_completed", {
    outcome: info.outcome,
    ...(info.durationMs !== undefined
      ? { duration_ms: clampInt(info.durationMs, MAX_DURATION_MS) }
      : {}),
    ...(info.itemCount !== undefined ? { item_count: clampInt(info.itemCount, MAX_ITEMS) } : {}),
  });
}

/** Test hook: forget the paste clock. */
export function resetBetaEventsForTests(): void {
  pastedAt = null;
}
