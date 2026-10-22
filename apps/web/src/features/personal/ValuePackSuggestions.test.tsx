/**
 * Large-family value packs on the real list builder, against the mock API: off by default, a
 * suggestion with both unit prices, the store and the price times when on, a quantity change on
 * one tap that can be undone, a dismissal that holds, and no request at all while the preference
 * is off.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ListBuilder } from "@/features/list/ListBuilder";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import { server } from "@/mocks/node";
import { parseRow } from "@/mocks/parseRow";
import { clearComparisonCache } from "@/state/comparison";
import { getListState, listActions, resetListStoreForTests } from "@/state/list";
import { resetBetaEventsForTests } from "@/features/consent/betaEvents";
import {
  PERSONAL_KEY,
  getPersonal,
  personalActions,
  resetPersonalStoreForTests,
} from "./personalState";
import { clearValuePackCache } from "./valuePacks";

const events = vi.hoisted(() => ({ calls: [] as Array<[string, Record<string, unknown>]> }));
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: (name: string, props: Record<string, unknown>) => {
    events.calls.push([name, props]);
  },
}));

type CompareBody = { items: Array<{ canonical_id: number; quantity: number | string }> };
const compareBodies: CompareBody[] = [];

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
});
afterAll(() => server.close());

beforeEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  resetListStoreForTests();
  resetPersonalStoreForTests();
  resetBetaEventsForTests();
  clearComparisonCache();
  clearValuePackCache();
  events.calls.length = 0;
  compareBodies.length = 0;
  server.events.on("request:start", async ({ request }) => {
    if (request.method === "POST" && request.url.endsWith("/compare")) {
      compareBodies.push((await request.clone().json()) as CompareBody);
    }
  });
});

const familyAsked = () =>
  compareBodies.some((b) =>
    b.items.some((i) => Number(i.quantity) >= 5 && i.canonical_id === 1009),
  );

describe("prefer value packs", () => {
  it("is off by default: no card, and no family-size request is ever made", async () => {
    listActions.add([parseRow("ביצים")]);
    render(<ListBuilder />);
    await screen.findByTestId("list-row");
    await waitFor(() => expect(compareBodies.length).toBeGreaterThan(0)); // the estimate still runs
    await new Promise((r) => setTimeout(r, 150));
    expect(screen.queryByTestId("value-packs")).toBeNull();
    expect(familyAsked()).toBe(false);
  });

  it("when on, shows the larger pack with both unit prices, the store, the times and the checkout line", async () => {
    personalActions.setPrefs({ value_packs: true });
    listActions.add([parseRow("ביצים")]);
    render(<ListBuilder />);
    const card = await screen.findByTestId("value-packs");
    expect(
      within(card).getByRole("heading", { name: "אריזות גדולות שמשתלמות" }),
    ).toBeInTheDocument();
    const pack = within(card).getByTestId("value-pack");
    expect(pack).toHaveTextContent("ביצים L, 12 יחידות");
    expect(pack).toHaveTextContent("אריזה גדולה"); // the tag
    expect(pack).toHaveTextContent("עכשיו: אריזה של 12");
    expect(pack).toHaveTextContent("אריזה גדולה: 30");
    expect(pack).toHaveTextContent(/\d+% פחות ליחידה/);
    expect(pack).toHaveTextContent("חנות:");
    expect(pack).toHaveTextContent("הכמות ברשימה תעלה מ-1 ל-2.5");
    expect(pack).toHaveTextContent("המחיר הקובע הוא בקופה.");
    // Trust: every price is next to the time it was updated.
    expect(within(pack).getAllByText(/₪/).length).toBeGreaterThanOrEqual(2);
    expect(pack.querySelectorAll("time[datetime]").length).toBeGreaterThanOrEqual(2);
    expect(familyAsked()).toBe(true);
    // It is a suggestion: nothing changed yet.
    expect(getListState().items[0]!.quantity).toBe(1);
    expect(events.calls).toContainEqual([
      "personalization",
      { kind: "value_pack", action: "shown" },
    ]);
  });

  it("one tap raises the quantity so the larger pack is chosen; undo puts it back", async () => {
    const user = userEvent.setup();
    personalActions.setPrefs({ value_packs: true });
    listActions.add([parseRow("ביצים")]);
    render(<ListBuilder />);
    await user.click(await screen.findByRole("button", { name: /עברי לאריזה הגדולה של/ }));
    expect(getListState().items[0]!.quantity).toBe(2.5);
    const status = screen.getByTestId("value-pack-status");
    expect(status).toHaveTextContent("עודכנה ל-2.5");
    // At 2.5 the API's own choice is the tray, so there is nothing larger left to suggest.
    await waitFor(() => expect(screen.queryByTestId("value-pack")).toBeNull());
    await user.click(
      within(screen.getByTestId("value-pack-status")).getByRole("button", { name: "ביטול" }),
    );
    expect(getListState().items[0]!.quantity).toBe(1);
    expect(screen.getByTestId("value-pack-status")).toHaveTextContent("חזרה ל-1");
    expect(await screen.findByTestId("value-pack")).toBeInTheDocument();
    expect(events.calls.map(([, p]) => p.action)).toEqual(
      expect.arrayContaining(["accepted", "undone"]),
    );
  });

  it("'no thanks' hides it for a month, and can be undone", async () => {
    const user = userEvent.setup();
    personalActions.setPrefs({ value_packs: true });
    listActions.add([parseRow("ביצים")]);
    render(<ListBuilder />);
    await user.click(await screen.findByRole("button", { name: /לא, תודה: ביצים/ }));
    await waitFor(() => expect(screen.queryByTestId("value-pack")).toBeNull());
    expect(getPersonal().dismissals).toEqual([
      expect.objectContaining({ kind: "value_pack", key: "1009" }),
    ]);
    expect(getListState().items[0]!.quantity).toBe(1);
    await user.click(
      within(screen.getByTestId("value-pack-status")).getByRole("button", { name: "ביטול" }),
    );
    expect(getPersonal().dismissals).toEqual([]);
    expect(await screen.findByTestId("value-pack")).toBeInTheDocument();
  });

  it("suggests nothing for a product that is not counted in units, or for an exact row", async () => {
    personalActions.setPrefs({ value_packs: true });
    listActions.add([parseRow("חלב"), parseRow("ביצים")]);
    const eggs = getListState().items.find((i) => i.canonical?.canonical_id === 1009)!;
    listActions.setFlex(eggs.id, { level: "exact", allow: [], remember: false });
    render(<ListBuilder />);
    await screen.findAllByTestId("list-row");
    await new Promise((r) => setTimeout(r, 150));
    expect(screen.queryByTestId("value-packs")).toBeNull();
    expect(familyAsked()).toBe(false);
  });

  it("is a stored preference: switching it on later needs no reload", async () => {
    listActions.add([parseRow("ביצים")]);
    render(<ListBuilder />);
    await screen.findByTestId("list-row");
    expect(screen.queryByTestId("value-packs")).toBeNull();
    personalActions.setPrefs({ value_packs: true });
    expect(await screen.findByTestId("value-packs")).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PERSONAL_KEY)!).prefs.value_packs).toBe(true);
  });

  it("in Arabic", async () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    personalActions.setPrefs({ value_packs: true });
    listActions.add([parseRow("ביצים")]);
    render(
      <LocaleProvider>
        <ListBuilder />
      </LocaleProvider>,
    );
    const card = await screen.findByTestId("value-packs");
    expect(within(card).getByRole("heading")).toHaveTextContent("عبوات كبيرة أوفر");
    expect(within(card).getByTestId("value-pack")).toHaveTextContent(
      "السعر المعتمد هو السعر عند الصندوق",
    );
  });
});
