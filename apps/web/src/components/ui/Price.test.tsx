import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Price, PriceRange } from "./Price";

const NBSP = "\u00A0";

describe("Price", () => {
  it("wraps the shekel sign and digits in an LTR island inside a Hebrew sentence", () => {
    const { container } = render(
      <p dir="rtl" lang="he" data-testid="sentence">
        הסל עולה <Price amount="389.00" />, כולל 5 מבצעים.
      </p>,
    );
    const sentence = screen.getByTestId("sentence");
    const islands = container.querySelectorAll('span[dir="ltr"]');
    expect(islands).toHaveLength(1);
    const island = islands[0]!;
    // Symbol, non-breaking space, digits; no agorot for whole amounts (artboard style).
    expect(island.textContent).toBe(`₪${NBSP}389`);
    // Punctuation stays in the Hebrew run, right after the island, not inside it.
    expect(island.nextSibling?.textContent?.startsWith(",")).toBe(true);
    expect(island.previousSibling?.textContent).toBe("הסל עולה ");
    expect(sentence.textContent).toBe(`הסל עולה ₪${NBSP}389, כולל 5 מבצעים.`);
    // DOM snapshot: the NBSP serializes as &nbsp; so it is visible here.
    expect(sentence.innerHTML).toBe(
      'הסל עולה <span dir="ltr" class="price size-inherit tone-default">₪&nbsp;389</span>, כולל 5 מבצעים.',
    );
  });

  it("keeps agorot when the amount is not whole", () => {
    render(<Price amount="6.9" data-testid="p" />);
    expect(screen.getByTestId("p").textContent).toBe(`₪${NBSP}6.90`);
  });

  it("marks savings with the good tone only when asked", () => {
    render(<Price amount={57} tone="good" data-testid="p" />);
    expect(screen.getByTestId("p").className).toContain("tone-good");
  });

  it("renders a range as one LTR island", () => {
    const { container } = render(<PriceRange from={412} to={468} />);
    const island = container.querySelector('span[dir="ltr"]');
    expect(island?.textContent).toBe(`₪${NBSP}412–₪${NBSP}468`);
  });
});
