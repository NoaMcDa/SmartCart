import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OptimizeResponse } from "@/api/client";
import { optimizeFixture } from "@/mocks/fixtures";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import { SubstitutionsSection } from "./SubstitutionsSection";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
});

const rows = () => screen.getAllByRole("listitem");

function renderSection(res: OptimizeResponse = optimizeFixture()) {
  return render(<SubstitutionsSection res={res} plan={res.single} />);
}

describe("substitutions list: one saving per substitute, the card's", () => {
  it("compares with the original at the substitute's own store when the API sends it", () => {
    renderSection();
    const milk = rows()[0]!;
    // The card's number: (6.50 - 5.90) x 2 = 1.20, not the home store's (6.90 - 5.90) x 2 = 2.
    expect(milk).toHaveTextContent(/₪\s1\.2/);
    expect(milk).not.toHaveTextContent(/₪\s2×/);
    expect(within(milk).getByTestId("sub-saving-basis")).toHaveTextContent(
      "בהשוואה למוצר המקורי באותו סניף",
    );
    // The original shown is the one at this store (unit price 6.50 per liter), labeled as such.
    expect(within(milk).getByTestId("sub-original-where")).toHaveTextContent("באותו סניף");
    expect(milk).toHaveTextContent("חלב טרי 3% תנובה, 1 ליטר");
    expect(milk).toHaveTextContent(/₪\s0\.65/);
    expect(milk).not.toHaveTextContent(/₪\s0\.69/);
  });

  it("falls back to the home store's original when the substitute's store does not sell it", () => {
    renderSection();
    const tomato = rows()[2]!;
    expect(tomato).toHaveTextContent(/₪\s4\.8/); // (6.90 - 4.50) x 2
    expect(within(tomato).getByTestId("sub-saving-basis")).toHaveTextContent(
      "בהשוואה למוצר המקורי בסופר שלך",
    );
    expect(within(tomato).getByTestId("sub-original-where")).toHaveTextContent("בסופר שלך");
    expect(tomato).toHaveTextContent(/₪\s2\.65/); // the home store's unit price, as before
  });

  it("a response without original_here compares with the home store, labeled so", () => {
    const res = optimizeFixture();
    for (const { store } of res.single.stores)
      for (const item of store.items) delete (item as { original_here?: unknown }).original_here;
    renderSection(res);
    const milk = rows()[0]!;
    expect(milk).toHaveTextContent(/₪\s2×/);
    expect(within(milk).getByTestId("sub-saving-basis")).toHaveTextContent("בסופר שלך");
  });

  it("without any original the row shows no saving and no basis", () => {
    renderSection(optimizeFixture({ homeStoreId: null }));
    const tomato = rows()[2]!;
    expect(tomato).toHaveTextContent("המוצר המקורי");
    expect(within(tomato).queryByTestId("sub-saving-basis")).toBeNull();
    expect(within(tomato).queryByTestId("sub-original-where")).toBeNull();
  });

  it("shows the Arabic wording", () => {
    window.localStorage.setItem(LOCALE_KEY, "ar");
    const res = optimizeFixture();
    render(
      <LocaleProvider>
        <SubstitutionsSection res={res} plan={res.single} />
      </LocaleProvider>,
    );
    expect(within(rows()[0]!).getByTestId("sub-saving-basis")).toHaveTextContent(
      "مقارنةً بالمنتج الأصلي في الفرع نفسه",
    );
    expect(within(rows()[2]!).getByTestId("sub-saving-basis")).toHaveTextContent(
      "مقارنةً بالمنتج الأصلي في سوبرماركتك",
    );
  });
});
