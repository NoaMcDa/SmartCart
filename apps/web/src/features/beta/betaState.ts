import { getBetaMembership, type BetaSegment } from "@/api/client";
import { ensureApiAuth } from "@/features/auth/apiAuth";

/**
 * Whether the signed-in person is a closed beta member (issue #40), as one shared value so the
 * feedback entry, the join page and anything else the shell mounts ask the API once per page load.
 * `unknown` until the first answer; a failed lookup (signed out, offline, an API without the
 * route) counts as "not a member" and is never shown as an error: the entry just stays hidden.
 */
export type BetaState = {
  status: "unknown" | "loading" | "ready";
  member: boolean;
  segment: BetaSegment | null;
};

const UNKNOWN: BetaState = { status: "unknown", member: false, segment: null };

let state: BetaState = UNKNOWN;
let inflight: Promise<void> | null = null;
let generation = 0;
const listeners = new Set<() => void>();

function set(next: BetaState): void {
  state = next;
  for (const l of listeners) l();
}

export const getBetaState = (): BetaState => state;
export const getServerBetaState = (): BetaState => UNKNOWN;

export function subscribeBeta(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Record a membership the app just changed itself (joined or left), without another request. */
export function setBetaMembership(member: boolean, segment: BetaSegment | null): void {
  generation += 1;
  set({ status: "ready", member, segment: member ? segment : null });
}

/** Forget the answer (sign-out, another account): the next `loadBetaMembership` asks again. */
export function resetBetaState(): void {
  generation += 1;
  inflight = null;
  if (state !== UNKNOWN) set(UNKNOWN);
}

/** Ask `GET /me/beta` once; later calls reuse the answer. */
export function loadBetaMembership(): Promise<void> {
  if (state.status === "ready") return Promise.resolve();
  if (inflight) return inflight;
  const mine = generation;
  if (state.status === "unknown") set({ ...UNKNOWN, status: "loading" });
  const run = (async () => {
    ensureApiAuth();
    try {
      const res = await getBetaMembership();
      if (mine === generation)
        set({ status: "ready", member: res.member, segment: res.segment ?? null });
    } catch {
      if (mine === generation) set({ status: "ready", member: false, segment: null });
    }
  })().finally(() => {
    if (inflight === run) inflight = null;
  });
  inflight = run;
  return run;
}
