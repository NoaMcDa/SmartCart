import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushEvents, resetTrackingForTests, setTrackingConsent } from "@/features/seo/track";
import {
  reportFlexChanged,
  reportGapReported,
  reportListPasted,
  reportResultsShown,
  reportSplitViewed,
  reportSubstitutionsShown,
  reportSubstitutionVerdict,
  resetBetaEventsForTests,
} from "./betaEvents";

const fetchMock = vi.fn(
  async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ ok: true })),
);

type Sent = { name: string; props: Record<string, unknown>; session_id: string };

async function sentEvents(): Promise<Sent[]> {
  await flushEvents();
  return fetchMock.mock.calls.flatMap(
    ([, init]) => (JSON.parse(init!.body as string) as { events: Sent[] }).events,
  );
}

/** Every call site once, with plausible values. */
function fireAll() {
  reportListPasted(9, 1_000);
  reportResultsShown({ itemCount: 9, storeCount: 5 }, 3_400);
  reportSubstitutionsShown({ exact: 1, any_brand: 2, close: 3 });
  reportSubstitutionVerdict("close", "not_good");
  reportFlexChanged("exact");
  reportSplitViewed();
  reportGapReported();
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
  localStorage.clear();
  resetTrackingForTests();
  resetBetaEventsForTests();
  fetchMock.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("beta events with consent", () => {
  beforeEach(() => setTrackingConsent(true));

  it("sends every event with only the allowlisted props", async () => {
    fireAll();
    const events = await sentEvents();
    expect(events.map((e) => [e.name, e.props])).toEqual([
      ["list_pasted", { item_count: 9 }],
      ["results_shown", { duration_ms: 2400, item_count: 9, store_count: 5 }],
      ["substitutions_shown", { flex_level: "exact", count: 1 }],
      ["substitutions_shown", { flex_level: "any_brand", count: 2 }],
      ["substitutions_shown", { flex_level: "close", count: 3 }],
      ["substitution_verdict", { flex_level: "close", verdict: "not_good" }],
      ["flex_changed", { flex_level: "exact" }],
      ["split_viewed", {}],
      ["gap_reported", {}],
    ]);
    // Integers and fixed strings only: no free text can reach an event.
    for (const e of events) {
      for (const value of Object.values(e.props)) {
        expect(
          typeof value === "number" ? Number.isInteger(value) : /^[a-z_]+$/.test(String(value)),
        ).toBe(true);
      }
    }
  });

  it("measures paste to results once per paste, and only within the same page session", async () => {
    reportResultsShown({ itemCount: 3, storeCount: 2 }, 5_000); // no paste yet: nothing to measure
    reportListPasted(3, 10_000);
    reportResultsShown({ itemCount: 3, storeCount: 2 }, 14_321);
    reportResultsShown({ itemCount: 3, storeCount: 2 }, 15_000); // already reported for this paste
    const events = await sentEvents();
    expect(events.filter((e) => e.name === "results_shown")).toHaveLength(1);
    expect(events.find((e) => e.name === "results_shown")?.props.duration_ms).toBe(4321);
  });

  it("drops a paste-to-results time over ten minutes and clamps counts to the API ranges", async () => {
    reportListPasted(999, 0);
    reportResultsShown({ itemCount: 5, storeCount: 1 }, 600_001);
    const events = await sentEvents();
    expect(events.map((e) => e.name)).toEqual(["list_pasted"]);
    expect(events[0]?.props).toEqual({ item_count: 200 });
  });

  it("skips substitutions_shown for levels with no substitutes and the verdict without a level", async () => {
    reportSubstitutionsShown({ any_brand: 0, close: 2 });
    reportSubstitutionVerdict(null, "accepted");
    const events = await sentEvents();
    expect(events.map((e) => [e.name, e.props])).toEqual([
      ["substitutions_shown", { flex_level: "close", count: 2 }],
    ]);
  });
});

describe("beta events without consent", () => {
  it("send nothing when the consent screen was declined", async () => {
    setTrackingConsent(false);
    fireAll();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(await sentEvents()).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("send nothing before the consent screen was answered", async () => {
    fireAll();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(await sentEvents()).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stop at once when consent is withdrawn, dropping what was queued", async () => {
    setTrackingConsent(true);
    reportSplitViewed();
    setTrackingConsent(false);
    reportGapReported();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("send nothing in a build without the beta flag, whatever the consent says", async () => {
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "");
    setTrackingConsent(true);
    fireAll();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
