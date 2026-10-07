import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PromoConfidence } from "./PromoConfidence";

describe("PromoConfidence", () => {
  it("shows the score as a percentage when the API gives one", () => {
    render(<PromoConfidence confidence={0.96} />);
    expect(screen.getByText("ביטחון 96%")).toBeInTheDocument();
    expect(screen.queryByText("לא נבדק")).toBeNull();
  });

  it("rounds, clamps and keeps an icon next to the text", () => {
    const { container, rerender } = render(<PromoConfidence confidence={0.724} />);
    expect(container).toHaveTextContent("ביטחון 72%");
    expect(container.querySelector("svg")).not.toBeNull();
    rerender(<PromoConfidence confidence={1.4} />);
    expect(container).toHaveTextContent("ביטחון 100%");
    rerender(<PromoConfidence confidence={0} />);
    expect(container).toHaveTextContent("ביטחון 0%");
  });

  it("says not checked when there is no score, never nothing and never an invented number", () => {
    for (const confidence of [null, undefined, Number.NaN]) {
      const { container, unmount } = render(<PromoConfidence confidence={confidence} />);
      expect(container).toHaveTextContent("לא נבדק");
      expect(container.textContent).not.toMatch(/\d/);
      unmount();
    }
  });

  it("is green only at 90% and above", () => {
    const { container, rerender } = render(<PromoConfidence confidence={0.9} />);
    expect(container.querySelector("[data-variant]")).toHaveAttribute("data-variant", "matched");
    rerender(<PromoConfidence confidence={0.89} />);
    expect(container.querySelector("[data-variant]")).toHaveAttribute("data-variant", "unverified");
  });
});
