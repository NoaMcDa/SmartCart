import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { optimizeFixture } from "@/mocks/fixtures";
import { findSubstitution } from "@/state/comparison";
import { SubstitutionCard, tagText } from "./SubstitutionView";

describe("substitution card", () => {
  const ctx = findSubstitution(optimizeFixture(), 10104, "single")!;

  function renderCard(
    handlers: Partial<Record<"onContinue" | "onKeep" | "onReject", () => void>> = {},
  ) {
    return render(
      <SubstitutionCard
        ctx={ctx}
        fallbackOriginalName={null}
        busy={false}
        onContinue={handlers.onContinue ?? (() => {})}
        onKeep={handlers.onKeep ?? (() => {})}
        onReject={handlers.onReject ?? (() => {})}
      />,
    );
  }

  it("shows original and substitute side by side with shelf and unit prices and their times", () => {
    renderCard();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "החלפנו את רסק עגבניות אסם, 260 ג' ב-רסק עגבניות מותג פרטי, 260 ג'",
    );
    const original = screen.getByTestId("sub-original");
    expect(original).toHaveTextContent("₪ 6.90");
    expect(original).toHaveTextContent("₪ 2.65 ל-100 ג'");
    expect(original.querySelector("time[datetime]")).not.toBeNull();
    const sub = screen.getByTestId("sub-substitute");
    expect(sub).toHaveTextContent("₪ 4.50");
    expect(sub).toHaveTextContent("₪ 1.73 ל-100 ג'");
    expect(sub).toHaveTextContent("התחליף");
    expect(sub.querySelector("time[datetime]")).not.toBeNull();
    expect(screen.getByTestId("sub-saving")).toHaveTextContent("₪ 2.40 × 2 יחידות");
    expect(screen.getByTestId("sub-saving")).toHaveTextContent("₪ 4.80");
    expect(screen.getByText(/החלפה/, { selector: "div" })).toHaveTextContent(
      "החלפה 3 מתוך 3 · רמי לוי",
    );
  });

  it("links the methodology page from the card", () => {
    renderCard();
    expect(
      within(screen.getByTestId("sub-methodology")).getByRole("link", {
        name: "איך אנחנו מחליטים מה תחליף מתאים",
      }),
    ).toHaveAttribute("href", "/methodology");
  });

  it("renders matched, unverified and differing tags, each with an icon and text", () => {
    renderCard();
    const tags = within(screen.getByRole("list", { name: "השוואת תכונות" })).getAllByRole(
      "listitem",
    );
    const variants = tags.map((t) =>
      t.querySelector("[data-variant]")!.getAttribute("data-variant"),
    );
    expect(variants).toEqual(["matched", "matched", "matched", "unverified", "differs"]);
    for (const t of tags) {
      expect(t.querySelector("svg")).not.toBeNull();
      expect(t.textContent!.trim().length).toBeGreaterThan(2);
    }
    expect(screen.getByText("מוצקים 28% · לא מאומת")).toBeInTheDocument();
    expect(screen.getByText("מותג פרטי במקום אסם")).toBeInTheDocument();
    expect(screen.getByTestId("sub-source")).toHaveTextContent("ביטחון 96%");
    expect(screen.getByTestId("sub-source").querySelector("time[datetime]")).not.toBeNull();
  });

  it("wires continue, keep the original and not a good substitute", () => {
    const onContinue = vi.fn();
    const onKeep = vi.fn();
    const onReject = vi.fn();
    renderCard({ onContinue, onKeep, onReject });
    fireEvent.click(screen.getByRole("button", { name: "בסדר, חזרה לתוצאות" }));
    fireEvent.click(screen.getByRole("button", { name: "השאירי את המקורי" }));
    fireEvent.click(screen.getByRole("button", { name: "לא תחליף טוב" }));
    expect([onContinue, onKeep, onReject].map((f) => f.mock.calls.length)).toEqual([1, 1, 1]);
  });

  it("carries the checkout disclaimer, as every substitute must", () => {
    renderCard();
    expect(screen.getByTestId("sub-disclaimer")).toHaveTextContent("המחיר הקובע הוא בקופה.");
  });

  it("shows what the real API sends in Hebrew: code keys, unit codes, folded pack size", () => {
    const real = {
      ...ctx,
      item: {
        ...ctx.item,
        uom: "100g",
        tags: [
          { key: "product_type", status: "matched" as const, value: "קמח" },
          { key: "pack_size", status: "matched" as const, value: "1000" },
          { key: "unit", status: "matched" as const, value: "g" },
          { key: "base", status: "differs" as const, value: "oat" },
          { key: "state", status: "unverified" as const, value: null },
        ],
      },
    };
    render(
      <SubstitutionCard
        ctx={real}
        fallbackOriginalName={null}
        busy={false}
        onContinue={() => {}}
        onKeep={() => {}}
        onReject={() => {}}
      />,
    );
    const tags = within(screen.getByRole("list", { name: "השוואת תכונות" }))
      .getAllByRole("listitem")
      .map((t) => t.textContent);
    expect(tags).toEqual([
      "סוג מוצר, קמח",
      "גודל אריזה, 1000 ג׳",
      "מצב · לא מאומת",
      "בסיס: שיבולת שועל",
    ]);
    expect(screen.getByTestId("sub-substitute")).toHaveTextContent("ל-100 ג׳");
    expect(screen.queryByText(/unit|, g|100g/)).toBeNull();
  });

  it("formats tags", () => {
    expect(tagText({ key: "אותו גודל", status: "matched", value: "1 ליטר" })).toBe(
      "אותו גודל, 1 ליטר",
    );
    expect(tagText({ key: "חלבון", status: "unverified", value: null })).toBe("חלבון · לא מאומת");
    expect(tagText({ key: "מותג", status: "differs", value: null })).toBe("מותג");
  });
});
