/**
 * MSW handlers for the closed beta routes (#40), following services/api `routes/beta.py`:
 *
 *   POST   /beta/join      { code }                -> 200 { member, segment } | 404 unknown | 410 expired or full
 *   GET    /me/beta                                -> { member, segment }
 *   DELETE /me/beta                                -> { ok }
 *   POST   /beta/feedback  { rating, text? }       -> 201 { ok } | 403 when not a member
 *
 * Codes the mock knows (case does not matter): BETA-KOSHER, BETA-FAMILY, BETA-PERIPHERY and
 * BETA-GENERAL join that segment; BETA-EXPIRED answers 410 "expired", BETA-FULL answers 410 "used
 * up"; anything else is 404. Membership and feedback live in memory (`resetBetaMock()` clears them).
 */
import { delay, http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type { BetaMembership, BetaSegment } from "@/api/client";

const url = (path: string) => `${API_BASE_URL}${path}`;
const latency = () => delay(process.env.NODE_ENV === "test" ? 0 : 250);

type StoredFeedback = { rating: number; text: string; segment: BetaSegment };

const CODES: Record<string, BetaSegment> = {
  "BETA-KOSHER": "kosher",
  "BETA-FAMILY": "large_family",
  "BETA-PERIPHERY": "periphery",
  "BETA-GENERAL": "general",
};

let membership: BetaMembership = { member: false, segment: null };
let feedback: StoredFeedback[] = [];

/** Test hook: back to "not a member, no feedback". */
export function resetBetaMock(): void {
  membership = { member: false, segment: null };
  feedback = [];
}

/** Test hook: start as a member of `segment`. */
export function setBetaMockMember(segment: BetaSegment): void {
  membership = { member: true, segment };
}

/** Test hook: the feedback `POST /beta/feedback` stored (no user, only the segment). */
export function mockBetaFeedback(): readonly StoredFeedback[] {
  return feedback;
}

export const betaHandlers = [
  http.post(url("/beta/join"), async ({ request }) => {
    const { code } = (await request.json()) as { code?: string };
    await latency();
    const key = (code ?? "").trim().toUpperCase();
    if (membership.member) return HttpResponse.json(membership);
    if (key === "BETA-EXPIRED") {
      return HttpResponse.json({ detail: "this invite code has expired" }, { status: 410 });
    }
    if (key === "BETA-FULL") {
      return HttpResponse.json({ detail: "this invite code has been used up" }, { status: 410 });
    }
    const segment = CODES[key];
    if (!segment) return HttpResponse.json({ detail: "unknown invite code" }, { status: 404 });
    membership = { member: true, segment };
    return HttpResponse.json(membership);
  }),

  http.get(url("/me/beta"), async () => {
    await latency();
    return HttpResponse.json(membership);
  }),

  http.delete(url("/me/beta"), async () => {
    await latency();
    membership = { member: false, segment: null };
    return HttpResponse.json({ ok: true, id: null });
  }),

  http.post(url("/beta/feedback"), async ({ request }) => {
    const body = (await request.json()) as { rating?: number; text?: string };
    await latency();
    if (!membership.member || !membership.segment) {
      return HttpResponse.json({ detail: "beta members only" }, { status: 403 });
    }
    const rating = Number(body.rating);
    const text = (body.text ?? "").trim();
    if (!Number.isInteger(rating) || rating < 1 || rating > 5 || text.length > 1000) {
      return HttpResponse.json({ detail: "invalid feedback" }, { status: 422 });
    }
    feedback.push({ rating, text, segment: membership.segment });
    return HttpResponse.json({ ok: true, id: null }, { status: 201 });
  }),
];
