/**
 * The `personalization` event (phase 3) on the wire: a kind and an action, nothing else, behind the
 * same consent gate as every other event.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushEvents, resetTrackingForTests, setTrackingConsent } from "@/features/seo/track";
import { reportPersonalization, resetBetaEventsForTests } from "./betaEvents";

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
  resetBetaEventsForTests();
  fetchMock.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("personalization events", () => {
  it("send the kind and the action and nothing else", async () => {
    setTrackingConsent(true);
    reportPersonalization("buy_again", "accepted");
    reportPersonalization("brand_default", "undone");
    reportPersonalization("value_pack", "dismissed");
    const events = await sent();
    expect(events.map((e) => [e.name, e.props])).toEqual([
      ["personalization", { kind: "buy_again", action: "accepted" }],
      ["personalization", { kind: "brand_default", action: "undone" }],
      ["personalization", { kind: "value_pack", action: "dismissed" }],
    ]);
    for (const e of events) expect(Object.keys(e.props).sort()).toEqual(["action", "kind"]);
  });

  it("`shown` is sent once per kind in a page session", async () => {
    setTrackingConsent(true);
    reportPersonalization("usual", "shown");
    reportPersonalization("usual", "shown");
    reportPersonalization("buy_again", "shown");
    reportPersonalization("usual", "accepted");
    reportPersonalization("usual", "accepted");
    const events = await sent();
    expect(events.filter((e) => e.props.action === "shown")).toHaveLength(2);
    expect(events.filter((e) => e.props.action === "accepted")).toHaveLength(2);
  });

  it("sends nothing before the person accepted the consent screen", async () => {
    reportPersonalization("usual", "shown");
    reportPersonalization("usual", "accepted");
    expect(await sent()).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
