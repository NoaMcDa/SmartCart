import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import { compareFixture, optimizeFixture } from "@/mocks/fixtures";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { clearLastResultCache } from "@/features/split/lastResult";
import { shopperSeed, weeklyListState } from "@/mocks/lastResult";
import { server } from "@/mocks/node";
import { clearComparisonCache } from "@/state/comparison";
import { resetListStoreForTests } from "@/state/list";
import { PROFILE_KEY } from "@/state/shopper";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
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

    describe("store coordinates from the API (StoreResult.lat and lon)", () => {
      /** Adds real coordinates to every store in a response, except those in `skip`. */
      function withCoords(value: unknown, skip: number[] = []): unknown {
        if (Array.isArray(value)) return value.map((v) => withCoords(v, skip));
        if (value && typeof value === "object") {
          const obj = Object.fromEntries(
            Object.entries(value).map(([k, v]) => [k, withCoords(v, skip)]),
          );
          if ("store_id" in obj && "distance_m" in obj && "items" in obj) {
            const id = obj.store_id as number;
            return skip.includes(id)
              ? { ...obj, lat: null, lon: null }
              : { ...obj, lat: 31.9 + (id - 100) * 0.002, lon: 35.01 + (id - 100) * 0.003 };
          }
          return obj;
        }
        return value;
      }

      function serve(skip: number[] = []) {
        server.use(
          http.post(`${API_BASE_URL}/compare`, () =>
            HttpResponse.json(withCoords(compareFixture(), skip) as object),
          ),
          http.post(`${API_BASE_URL}/optimize`, () =>
            HttpResponse.json(withCoords(optimizeFixture(), skip) as object),
          ),
        );
      }

      it("uses them for the pins and drops the approximation note when every store has them", async () => {
        serve();
        render(<MapScreen />);
        expect(await screen.findAllByTestId("map-pin")).toHaveLength(5);
        expect(screen.queryByTestId("map-approx")).toBeNull();
      });

      it("keeps the note only while a store has null coordinates", async () => {
        serve([102]);
        render(<MapScreen />);
        expect(await screen.findAllByTestId("map-pin")).toHaveLength(5);
        expect(screen.getByTestId("map-approx")).toHaveTextContent("מדויק");
      });
    });

    describe("a store placed only at its town centre (distance_approximate)", () => {
      it("is a hollow marker with the words, never an exact pin; the others stay solid", async () => {
        render(<MapScreen />);
        const pins = await screen.findAllByTestId("map-pin");
        const approximate = pins.filter((p) => p.getAttribute("data-approximate") === "true");
        expect(approximate).toHaveLength(1);
        expect(approximate[0]).toHaveTextContent("יוחננוף");
        expect(approximate[0]).toHaveTextContent("מיקום משוער");
        expect(approximate[0]).toHaveAccessibleName(/מיקום משוער/);
        for (const pin of pins.filter((p) => p !== approximate[0])) {
          expect(pin).toHaveAttribute("data-approximate", "false");
          expect(pin).not.toHaveTextContent("מיקום משוער");
        }
      });

      it("has a legend that explains the hollow marker, and no legend without such a store", async () => {
        const { unmount } = render(<MapScreen />);
        expect(await screen.findByTestId("map-legend")).toHaveTextContent("חלול ומקווקו");
        expect(screen.getByTestId("map-legend")).toHaveTextContent("המרחק אליו הוא הערכה");
        unmount();
        // Same comparison with every store at address precision.
        function exact(value: unknown): unknown {
          if (Array.isArray(value)) return value.map(exact);
          if (value && typeof value === "object") {
            const obj = Object.fromEntries(Object.entries(value).map(([k, v]) => [k, exact(v)]));
            return "distance_approximate" in obj
              ? { ...obj, distance_approximate: false, geo_precision: "address" }
              : obj;
          }
          return value;
        }
        server.use(
          http.post(`${API_BASE_URL}/compare`, () =>
            HttpResponse.json(exact(compareFixture()) as object),
          ),
          http.post(`${API_BASE_URL}/optimize`, () =>
            HttpResponse.json(exact(optimizeFixture()) as object),
          ),
        );
        clearComparisonCache();
        clearLastResultCache();
        render(<MapScreen />);
        await screen.findAllByTestId("map-pin");
        expect(screen.queryByTestId("map-legend")).toBeNull();
        for (const pin of screen.getAllByTestId("map-pin")) {
          expect(pin).toHaveAttribute("data-approximate", "false");
        }
      });

      it("the list shows the distance as approximate and exact ones as before", async () => {
        render(<MapScreen />);
        const rows = await screen.findAllByTestId("map-row-distance");
        const byStore = (name: string) =>
          rows.find((r) => r.closest("button")?.textContent?.includes(name))!;
        expect(byStore("יוחננוף").textContent).toBe('כ־3.6 ק"מ · מיקום משוער');
        expect(byStore("יוחננוף")).toHaveAttribute("data-approximate", "true");
        expect(byStore("רמי לוי").textContent).toBe('4.2 ק"מ');
        expect(
          screen.getByRole("button", { name: /יוחננוף · מודיעין, כ־3.6 ק"מ · מיקום משוער/ }),
        ).toBeInTheDocument();
      });

      it("the store sheet says why the distance is only an estimate", async () => {
        const user = userEvent.setup();
        render(<MapScreen />);
        const pins = await screen.findAllByTestId("map-pin");
        await user.click(pins.find((p) => p.textContent?.includes("יוחננוף"))!);
        const distance = screen.getByTestId("sheet-distance");
        expect(distance).toHaveTextContent('כ־3.6 ק"מ · מיקום משוער');
        expect(distance).toHaveTextContent("מרכז היישוב");
      });
    });

    describe("in Arabic", () => {
      afterEach(() => {
        document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
        document.documentElement.lang = "he";
      });

      it("writes chains in Latin, cities in Arabic, units and the approximate words in Arabic", async () => {
        document.cookie = `${LOCALE_KEY}=ar; path=/`;
        render(
          <LocaleProvider>
            <MapScreen />
          </LocaleProvider>,
        );
        const list = await screen.findByTestId("map-store-list");
        expect(list.textContent).toContain("Rami Levy");
        expect(list.textContent).not.toMatch(/[֐-׿]/);
        const approx = within(list)
          .getAllByTestId("map-row-distance")
          .find((r) => r.getAttribute("data-approximate") === "true")!;
        expect(approx.textContent).toBe("نحو 3.6 كم · الموقع تقريبي");
        for (const pin of screen.getAllByTestId("map-pin")) {
          expect(pin.textContent).not.toMatch(/[֐-׿]/);
        }
        expect(screen.getByTestId("map-legend")).toHaveTextContent("موقع تقريبي");
      });
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
