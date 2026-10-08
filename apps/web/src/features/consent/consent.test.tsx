import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushEvents, getTrackingConsent, resetTrackingForTests } from "@/features/seo/track";
import { ConsentGate, resetConsentGateForTests } from "./ConsentSheet";
import { UsageEventsControl } from "./UsageEventsControl";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const fetchMock = vi.fn(
  async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ ok: true })),
);

function sentNames(): string[] {
  return fetchMock.mock.calls.flatMap(([, init]) =>
    (JSON.parse(init!.body as string) as { events: { name: string }[] }).events.map((e) => e.name),
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
  localStorage.clear();
  resetTrackingForTests();
  resetConsentGateForTests();
  fetchMock.mockClear();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "doNotTrack");
});

describe("consent sheet", () => {
  it("is shown on the first visit and explains what is and is not collected", async () => {
    render(<ConsentGate />);
    const dialog = await screen.findByRole("dialog", { name: "עוזרות לנו לבדוק את ההחלפות?" });
    expect(dialog).toHaveTextContent("מה נשמר");
    expect(dialog).toHaveTextContent("לא תחליף טוב");
    expect(dialog).toHaveTextContent("מה לא נשמר");
    expect(dialog).toHaveTextContent("תוכן הרשימה שלך");
    expect(dialog).toHaveTextContent("לא נמכר");
    expect(screen.getByRole("link", { name: "בפרופיל" })).toHaveAttribute("href", "/profile");
    expect(screen.getByRole("link", { name: "למדיניות הפרטיות" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    // Nothing is stored or sent until the person answers.
    expect(localStorage.getItem("sc-events-consent")).toBeNull();
    await flushEvents();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("accepting stores the answer under sc-events-consent, closes, and reports app_opened", async () => {
    const user = userEvent.setup();
    render(<ConsentGate />);
    await user.click(await screen.findByRole("button", { name: "אני מסכימה" }));
    expect(localStorage.getItem("sc-events-consent")).toBe("1");
    expect(screen.queryByRole("dialog")).toBeNull();
    await act(() => flushEvents());
    expect(sentNames()).toEqual(["app_opened"]);
  });

  it("app_opened carries the surface and the coarse platform (#56), nothing else", async () => {
    const ua =
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148";
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(ua);
    localStorage.setItem("sc-events-consent", "1");
    render(<ConsentGate />);
    await act(() => flushEvents());
    const [, init] = fetchMock.mock.calls[0]!;
    const { events } = JSON.parse(init!.body as string) as {
      events: { name: string; props: Record<string, unknown> }[];
    };
    expect(events[0]).toMatchObject({
      name: "app_opened",
      props: { surface: "web", platform: "ios" },
    });
    vi.restoreAllMocks();
  });

  it("declining stores 0, closes, and nothing is ever sent", async () => {
    const user = userEvent.setup();
    render(<ConsentGate />);
    await user.click(await screen.findByRole("button", { name: "לא, תודה" }));
    expect(localStorage.getItem("sc-events-consent")).toBe("0");
    expect(getTrackingConsent()).toBe("declined");
    expect(screen.queryByRole("dialog")).toBeNull();
    await act(() => flushEvents());
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("Escape counts as declining, so the question is asked once", async () => {
    const user = userEvent.setup();
    render(<ConsentGate />);
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
    await user.keyboard("{Escape}");
    expect(localStorage.getItem("sc-events-consent")).toBe("0");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it.each(["1", "0"])("is not shown again once answered (%s)", (answer) => {
    localStorage.setItem("sc-events-consent", answer);
    render(<ConsentGate />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("is not shown in a build without beta events, nor with Do Not Track", () => {
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "");
    const { unmount } = render(<ConsentGate />);
    expect(screen.queryByRole("dialog")).toBeNull();
    unmount();
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    render(<ConsentGate />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("reports app_opened once per visit, not on every mount", async () => {
    localStorage.setItem("sc-events-consent", "1");
    const first = render(<ConsentGate />);
    first.unmount();
    render(<ConsentGate />);
    await act(() => flushEvents());
    expect(sentNames()).toEqual(["app_opened"]);
  });
});

describe("opt-out in Profile", () => {
  it("renders nothing in a build that collects no events", () => {
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "");
    const { container } = render(<UsageEventsControl />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is a switch that mirrors the answer and stops events at once when turned off", async () => {
    const user = userEvent.setup();
    localStorage.setItem("sc-events-consent", "1");
    render(<UsageEventsControl />);
    const toggle = await screen.findByRole("switch", { name: "אירועי שימוש לבדיקת הבטא" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await user.click(toggle);
    expect(localStorage.getItem("sc-events-consent")).toBe("0");
    expect(toggle).toHaveAttribute("aria-checked", "false");
    await user.click(toggle);
    expect(localStorage.getItem("sc-events-consent")).toBe("1");
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("starts off, with an explanation, before the question was answered", async () => {
    render(<UsageEventsControl />);
    const toggle = await screen.findByRole("switch", { name: "אירועי שימוש לבדיקת הבטא" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(toggle).toHaveAccessibleDescription(/עוד לא ענית/);
  });

  it("says nothing is collected when the browser sends Do Not Track", async () => {
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    render(<UsageEventsControl />);
    expect(await screen.findByTestId("usage-events-dnt")).toHaveTextContent("Do Not Track");
    expect(screen.queryByRole("switch")).toBeNull();
  });
});
