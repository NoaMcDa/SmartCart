/**
 * The voice list events (issue #65) on the wire: `voice_started` and `voice_completed` with only a
 * fixed outcome and integers, behind the same consent gate as every other event. The API's
 * allowlist must list both names (the lead updates `services/api` and regenerates the types).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushEvents, resetTrackingForTests, setTrackingConsent } from "@/features/seo/track";
import { reportVoiceCompleted, reportVoiceStarted } from "./betaEvents";

const fetchMock = vi.fn(
  async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ ok: true })),
);

type Sent = { name: string; props: Record<string, unknown> };

async function sent(): Promise<Sent[]> {
  await flushEvents();
  return fetchMock.mock.calls.flatMap(
    ([, init]) => (JSON.parse(init!.body as string) as { events: Sent[] }).events,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
  localStorage.clear();
  resetTrackingForTests();
  fetchMock.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("voice events", () => {
  it("send the outcome, the duration and the item count, rounded to integers", async () => {
    setTrackingConsent(true);
    reportVoiceStarted();
    reportVoiceCompleted({ outcome: "added", durationMs: 8421.7, itemCount: 4 });
    reportVoiceCompleted({ outcome: "denied", durationMs: 120 });
    reportVoiceCompleted({ outcome: "cancelled" });
    expect((await sent()).map((e) => [e.name, e.props])).toEqual([
      ["voice_started", {}],
      ["voice_completed", { outcome: "added", duration_ms: 8422, item_count: 4 }],
      ["voice_completed", { outcome: "denied", duration_ms: 120 }],
      ["voice_completed", { outcome: "cancelled" }],
    ]);
  });

  it("cap the numbers at the API's ranges", async () => {
    setTrackingConsent(true);
    reportVoiceCompleted({ outcome: "added", durationMs: 9_999_999, itemCount: 5_000 });
    const [event] = await sent();
    expect(event!.props).toEqual({ outcome: "added", duration_ms: 600_000, item_count: 200 });
  });

  it("send nothing without consent", async () => {
    setTrackingConsent(false);
    reportVoiceStarted();
    reportVoiceCompleted({ outcome: "added", durationMs: 1, itemCount: 1 });
    expect(await sent()).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
