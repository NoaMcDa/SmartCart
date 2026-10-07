import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { clearLastResultCache } from "@/features/split/lastResult";
import { shopperSeed, weeklyListState } from "@/mocks/lastResult";
import { server } from "@/mocks/node";
import { clearComparisonCache } from "@/state/comparison";
import { resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { MapScreen } from "./MapScreen";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));

// jsdom has no WebGL, so the real canvas asks for the fallback, like a device without WebGL.
vi.mock("./MapCanvas", async () => {
  const { useEffect } = await import("react");
  return {
    default: function MapCanvasStub({ onUnsupported }: { onUnsupported: () => void }) {
      useEffect(() => onUnsupported(), [onUnsupported]);
      return null;
    },
  };
});

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function seed(shopper: Record<string, unknown> = {}) {
  window.localStorage.setItem("sc-list-v1", JSON.stringify(weeklyListState()));
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify(shopperSeed(shopper)));
}

beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
  clearComparisonCache();
  clearLastResultCache();
  push.mockClear();
});

describe("map screen", () => {
  it("shows an empty state without a list", async () => {
    render(<MapScreen />);
    await screen.findByTestId("map-empty");
    expect(screen.getByRole("heading", { level: 1, name: "מפת סניפים" })).toBeInTheDocument();
    expect(screen.getByTestId("map-empty")).toHaveTextContent("אין עדיין השוואה");
  });

  describe("with a comparison", () => {
    beforeEach(() => {
      seed();
    });

    it("one pin per store, each with its basket total, with the recommended one marked in words", async () => {
      render(<MapScreen />);
      const pins = await screen.findAllByTestId("map-pin");
      expect(pins).toHaveLength(5);
      const totals = pins.map((p) =>
        within(p)
          .getByTestId("pin-price")
          .textContent?.replace(/\u00a0/g, " "),
      );
      expect(totals).toEqual(expect.arrayContaining(["₪ 389", "₪ 402", "₪ 418", "₪ 446"]));
      for (const pin of pins) {
        expect(within(pin).getByTestId("pin-price").closest('[dir="ltr"]')).not.toBeNull();
      }
      const rami = pins.find((p) => p.textContent?.includes("רמי לוי"))!;
      expect(rami).toHaveTextContent("מומלץ");
      expect(rami).toHaveAttribute("data-recommended", "true");
      // Not by color alone: the cheapest complete basket says so in text too.
      expect(screen.getAllByText("הכי זול").length).toBeGreaterThan(0);
    });

    it("tapping a pin opens a bottom sheet with the store, the total and the net saving", async () => {
      const user = userEvent.setup();
      render(<MapScreen />);
      const pins = await screen.findAllByTestId("map-pin");
      await user.click(pins.find((p) => p.textContent?.includes("רמי לוי"))!);
      const dialog = screen.getByRole("dialog", { name: "רמי לוי · מודיעין" });
      const sheet = within(dialog);
      expect(sheet.getByTestId("store-sheet")).toHaveTextContent('4.2 ק"מ');
      expect(sheet.getByTestId("store-sheet")).toHaveTextContent("₪ 389");
      expect(sheet.getByTestId("store-sheet")).toHaveTextContent("חיסכון נטו מול שופרסל");
      expect(sheet.getByTestId("store-sheet")).toHaveTextContent("₪ 57");
      expect(sheet.getByText("חסרים 1 פריטים")).toBeInTheDocument();
      expect(sheet.getByRole("link", { name: "לכרטיס בתוצאות" })).toHaveAttribute(
        "href",
        "/compare#store-101",
      );
    });

    it("the list under the map is the accessible alternative and opens the same sheet", async () => {
      const user = userEvent.setup();
      render(<MapScreen />);
      const list = within(await screen.findByTestId("map-store-list"));
      expect(list.getAllByRole("button")).toHaveLength(5);
      await user.click(list.getByRole("button", { name: /יוחננוף · מודיעין/ }));
      expect(screen.getByRole("dialog", { name: "יוחננוף · מודיעין" })).toBeInTheDocument();
    });

    it("says that store directions are approximate and links the OSM attribution and back to the list", async () => {
      render(<MapScreen />);
      expect(await screen.findByTestId("map-approx")).toHaveTextContent("מדויק");
      expect(screen.getByRole("link", { name: "תורמי OpenStreetMap" })).toHaveAttribute(
        "href",
        "https://www.openstreetmap.org/copyright",
      );
      expect(screen.getByRole("link", { name: "חזרה לתצוגת רשימה" })).toHaveAttribute(
        "href",
        "/compare",
      );
    });

    it("start shopping from the sheet begins a session for that store", async () => {
      const user = userEvent.setup();
      render(<MapScreen />);
      const pins = await screen.findAllByTestId("map-pin");
      await user.click(pins.find((p) => p.textContent?.includes("אושר עד"))!);
      await user.click(screen.getByRole("button", { name: "התחילי קנייה" }));
      expect(push).toHaveBeenCalledWith("/store-mode?store=102");
      expect(JSON.parse(window.localStorage.getItem(STORAGE_KEYS.shopping)!).storeId).toBe(102);
    });
  });
});
