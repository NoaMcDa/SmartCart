import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PrivacyBody } from "@/app/(secondary)/privacy/PrivacyBody";
import { ResultsContent } from "@/features/compare/ResultsView";
import { ListRow } from "@/features/list/ListRow";
import { chainLabel, storeLabel } from "@/lib/storeName";
import { itemProductName, productName } from "@/lib/format";
import { optimizeFixture, canonicalRef } from "@/mocks/fixtures";
import { itemFromRow } from "@/state/list";
import { LegalNotice } from "./LegalNotice";
import { LocaleProvider } from "./LocaleProvider";
import { LOCALE_KEY } from "./locales";
import { translate } from "./messages";
import { legalMessages } from "./messages/legal";
import { pluralForm, translatePlural } from "./plural";
import { countMessages } from "./messages/counts";

/** Workstream AR-4 (#73): list, compare, split, budget, consent, alerts, store, privacy pages. */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const HEBREW = /[֐-׿]/;

/** The text of a node without the runs marked `lang="he"` (data that exists only in Hebrew). */
function visibleText(root: HTMLElement): string {
  const copy = root.cloneNode(true) as HTMLElement;
  for (const el of copy.querySelectorAll('[lang="he"]')) el.remove();
  return copy.textContent ?? "";
}

function inArabic(ui: React.ReactElement) {
  document.cookie = `${LOCALE_KEY}=ar; path=/`;
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
});

describe("plural forms", () => {
  it("keeps Hebrew at two forms", () => {
    expect([0, 1, 2, 3, 11].map((n) => pluralForm(n, "he"))).toEqual([
      "many",
      "one",
      "many",
      "many",
      "many",
    ]);
  });

  it("uses the four Arabic forms", () => {
    expect([0, 1, 2, 3, 10, 11, 99, 100].map((n) => pluralForm(n, "ar"))).toEqual([
      "few",
      "one",
      "two",
      "few",
      "few",
      "many",
      "many",
      "few",
    ]);
    expect(translatePlural(countMessages, "ar", "item", 4)).toBe("أصناف");
    expect(translatePlural(countMessages, "ar", "item", 12)).toBe("صنفًا");
    expect(translatePlural(countMessages, "he", "item", 1)).toBe("פריט");
    expect(translatePlural(countMessages, "he", "items", 1)).toBe("פריטים");
  });
});

describe("product and store names", () => {
  const milk = canonicalRef(1001);

  it("shows the Arabic canonical name in Arabic and falls back to Hebrew", () => {
    expect(productName(milk, "ar")).toBe("حليب طازج 3%");
    expect(productName(milk, "he")).toBe(milk.display_name_he);
    expect(productName(canonicalRef(1010), "ar")).toBe(canonicalRef(1010).display_name_he);
    expect(productName(null, "ar")).toBe("");
  });

  it("names a priced item by its canonical, never by swapping the shelf name", () => {
    const item = { display_name_he: "חלב טרי 3% תנובה, 1 ליטר", canonical_name_ar: "حليب طازج 3%" };
    expect(itemProductName(item, "ar")).toBe("حليب طازج 3%");
    expect(itemProductName(item, "he")).toBe("חלב טרי 3% תנובה, 1 ליטר");
    expect(itemProductName({ display_name_he: "פסטה" }, "ar")).toBe("פסטה");
  });

  it("writes chains in Latin and cities in Arabic, and leaves Hebrew alone", () => {
    expect(chainLabel("שופרסל דיל", "ar")).toBe("Shufersal Deal");
    expect(chainLabel("רמי לוי", "ar")).toBe("Rami Levy");
    expect(storeLabel("רמי לוי · מודיעין", "ar")).toBe("Rami Levy · موديعين");
    expect(storeLabel("מודיעין", "ar")).toBe("موديعين");
    expect(storeLabel("חנות לא מוכרת", "ar")).toBe("חנות לא מוכרת");
    expect(storeLabel("רמי לוי · מודיעין", "he")).toBe("רמי לוי · מודיעין");
  });
});

describe("legal notice", () => {
  it("shows the translation line in Arabic only", () => {
    const he = render(
      <LocaleProvider>
        <LegalNotice />
      </LocaleProvider>,
    );
    expect(he.container).toBeEmptyDOMElement();
    he.unmount();
    inArabic(<LegalNotice />);
    expect(screen.getByTestId("legal-translation-note")).toHaveTextContent(
      "هذه ترجمة، والنص العبري هو الملزم",
    );
    expect(translate(legalMessages, "ar", "translationNotice")).toBe(
      "هذه ترجمة، والنص العبري هو الملزم",
    );
  });

  it("is on the Arabic privacy page, which has no Hebrew letters", () => {
    const { container } = inArabic(<PrivacyBody />);
    expect(screen.getByTestId("legal-translation-note")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("سياسة الخصوصية");
    expect(HEBREW.test(visibleText(container))).toBe(false);
  });
});

describe("Arabic screens", () => {
  it("renders the comparison results with Latin chain names and no Hebrew outside data runs", () => {
    const names = new Map([[1002, productName(canonicalRef(1002), "ar")]]);
    const { container } = inArabic(
      <ResultsContent res={optimizeFixture()} names={names} onReportGap={() => {}} />,
    );
    const single = screen.getByTestId("plan-single");
    expect(single).toHaveTextContent("موصى به");
    expect(single).toHaveTextContent("توفير");
    expect(single).toHaveTextContent("Rami Levy");
    expect(screen.getByTestId("disclaimer")).toHaveTextContent(
      "السعر المعتمد هو السعر عند الصندوق",
    );
    expect(visibleText(container).match(/[^\s]*[\u0590-\u05FF]+[^\s]*/g) ?? []).toEqual([]);
  });

  it("shows a list row with the Arabic product name and Arabic labels", () => {
    const row = {
      input_text: "حليب",
      quantity: 2,
      unit: null,
      is_weighed: false,
      canonical: canonicalRef(1001),
      candidates: [],
      flex_level: "any_brand" as const,
      needs_confirmation: false,
      not_found: false,
      confidence: 1,
    };
    const item = itemFromRow(row as never, {});
    const { container } = inArabic(<ListRow item={item} onOpenFlex={() => {}} />);
    const line = within(screen.getByTestId("list-row"));
    expect(line.getByText("حليب طازج 3%")).toBeInTheDocument();
    expect(line.getByRole("button", { name: "إزالة حليب طازج 3%" })).toBeInTheDocument();
    expect(HEBREW.test(container.textContent ?? "")).toBe(false);
  });
});
