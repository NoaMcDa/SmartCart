import { API_BASE_URL, API_MOCK } from "@/api/config";
import type { components } from "@/api/types";

/**
 * First-party product events for the closed beta (issue #40, decisions D10 and D11).
 *
 * `trackEvent("results_shown", { duration_ms: 2400 })` queues an event; a batch goes to
 * `POST /events` (services/api/smartcart_api/routes/events.py) two seconds later, or when the page
 * is hidden. There is no third-party analytics and nothing leaves the browser for anyone else.
 *
 * Privacy rules enforced here and again by the API:
 *  - only the event names and property keys in `EventProps`, whose values are numbers or members of
 *    a fixed set. There is no free-text property: list items, searches and names are never sent;
 *  - the session id is a random token kept in localStorage, not derived from anything about the
 *    person; the signed-in user id is added by the API from the JWT, never sent from here;
 *  - tracking is OFF unless NEXT_PUBLIC_BETA_EVENTS=1 is set at build time, never runs against the
 *    mock API, and stops when the browser sends Do Not Track or the person opted out
 *    (`setTrackingConsent(false)`, stored as localStorage["sc-events-consent"] = "0").
 *
 * Wiring (W4b and W5, docs/beta-plan.md "Events"): call `trackEvent` from the list builder
 * (`list_pasted`), the results screen (`results_shown`, `substitutions_shown`), the substitution
 * card (`substitution_verdict`), the flexibility sheet (`flex_changed`), the split view
 * (`split_viewed`), report-a-gap (`gap_reported`) and the shell (`app_opened`, once per visit).
 * After sign-in call `setAuthTokenProvider(() => session.access_token)` so the API can attach the
 * user; without it events are anonymous. A failed send is dropped, never retried and never thrown.
 */

type FlexLevel = "exact" | "any_brand" | "close";

export type EventProps = {
  app_opened: { surface?: "web" | "pwa" };
  page_viewed: {
    page_type: "category" | "product" | "methodology" | "basket_index" | "other";
  };
  list_pasted: { item_count: number };
  /** `duration_ms` runs from the paste to the results being on screen. */
  results_shown: { duration_ms: number; item_count?: number; store_count?: number };
  /** One per results view and flexibility level that listed substitutions (the rate's denominator). */
  substitutions_shown: { flex_level: FlexLevel; count: number };
  substitution_verdict: {
    flex_level: FlexLevel;
    verdict: "not_good" | "kept_original" | "accepted";
  };
  flex_changed: { flex_level: FlexLevel };
  split_viewed: Record<string, never>;
  gap_reported: Record<string, never>;
};

export type EventName = keyof EventProps;

// Compile-time check that this file and the API contract list the same events.
type ContractName = components["schemas"]["EventIn"]["name"];
type _SameNames = [EventName] extends [ContractName]
  ? [ContractName] extends [EventName]
    ? true
    : never
  : never;
const _sameNames: _SameNames = true;
void _sameNames;

const FLUSH_DELAY_MS = 2000;
const MAX_BATCH = 50;
const SESSION_KEY = "sc-session";
const CONSENT_KEY = "sc-events-consent";

type Queued = { name: EventName; props: Record<string, number | string>; session_id: string };

let queue: Queued[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;
let listening = false;
let memorySession: string | undefined;
let tokenProvider: (() => string | null | undefined) | undefined;

function storage(): Storage | undefined {
  try {
    return typeof localStorage === "undefined" ? undefined : localStorage;
  } catch {
    return undefined; // blocked storage (private mode, site data off)
  }
}

/** Whether events are collected at all in this build and browser. */
export function isTrackingEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_BETA_EVENTS !== "1" || API_MOCK) return false;
  if (typeof navigator !== "undefined" && navigator.doNotTrack === "1") return false;
  try {
    return storage()?.getItem(CONSENT_KEY) !== "0";
  } catch {
    return true;
  }
}

/** Opt in or out for this browser. Opting out also drops anything still queued. */
export function setTrackingConsent(enabled: boolean): void {
  try {
    storage()?.setItem(CONSENT_KEY, enabled ? "1" : "0");
  } catch {
    // nothing to persist; the in-memory queue is still cleared below
  }
  if (!enabled) clearQueue();
}

/** Register how to get the signed-in user's access token (W5, after Supabase sign-in). */
export function setAuthTokenProvider(provider: (() => string | null | undefined) | undefined) {
  tokenProvider = provider;
}

function randomToken(): string {
  const c = globalThis.crypto;
  if (c?.randomUUID) return c.randomUUID().replace(/-/g, "");
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

/** The random browser session id (8 to 64 URL-safe characters), created on first use. */
export function getSessionId(): string {
  const store = storage();
  try {
    const existing = store?.getItem(SESSION_KEY);
    if (existing && /^[A-Za-z0-9_-]{8,64}$/.test(existing)) return existing;
    const fresh = randomToken();
    store?.setItem(SESSION_KEY, fresh);
    memorySession = fresh;
    return fresh;
  } catch {
    memorySession ??= randomToken();
    return memorySession;
  }
}

function listen() {
  if (listening || typeof document === "undefined") return;
  listening = true;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") void flushEvents();
  });
}

function clearQueue() {
  queue = [];
  if (timer) clearTimeout(timer);
  timer = undefined;
}

export function trackEvent<N extends EventName>(
  name: N,
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  ...[props]: {} extends EventProps[N] ? [props?: EventProps[N]] : [props: EventProps[N]]
): void {
  if (!isTrackingEnabled()) return;
  listen();
  queue.push({
    name,
    props: { ...(props ?? {}) } as Record<string, number | string>,
    session_id: getSessionId(),
  });
  if (queue.length >= MAX_BATCH) {
    void flushEvents();
  } else if (!timer) {
    timer = setTimeout(() => void flushEvents(), FLUSH_DELAY_MS);
  }
}

/** Send what is queued now. Resolves when the request settles; never rejects. */
export async function flushEvents(): Promise<void> {
  if (timer) clearTimeout(timer);
  timer = undefined;
  const batch = queue.splice(0, MAX_BATCH);
  if (batch.length === 0) return;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = tokenProvider?.();
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    await fetch(`${API_BASE_URL}/events`, {
      method: "POST",
      headers,
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });
  } catch {
    // Dropped on purpose: analytics must never break or slow the app.
  }
  if (queue.length > 0) timer = setTimeout(() => void flushEvents(), FLUSH_DELAY_MS);
}

/** Test helper: forget the queue, timers and the in-memory session. */
export function resetTrackingForTests(): void {
  clearQueue();
  memorySession = undefined;
  tokenProvider = undefined;
}
