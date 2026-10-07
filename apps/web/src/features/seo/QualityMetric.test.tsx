import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { percentDown } from "./format";
import { QualityMetric } from "./QualityMetric";
import type { Quality } from "./types";

const measured: Quality = {
  generated_at: "2026-10-07T06:00:00Z",
  available: true,
  run_id: 7,
  measured_at: "2026-10-06T12:30:05Z",
  precision: { exact: 1, any_brand: 0.9876, close: 0.95 },
  sample: { exact: 120, any_brand: 400, close: 80 },
  gold_items: 831,
  gold_pairs: 2419,
  synthetic: true,
  judge: "rule-v1",
  target_any_brand: 0.98,
};

describe("QualityMetric", () => {
  it("states the percentage of correct substitutions on the evaluation set, synthetic until real data", () => {
    render(<QualityMetric quality={measured} />);
    const headline = screen.getByTestId("quality-metric").querySelector("p")!;
    expect(headline.textContent).toContain("98.7%");
    expect(headline.textContent).toContain(
      "מההחלפות נכונות בסט ההערכה (סינתטי עד שיהיו נתונים אמיתיים)",
    );
    expect(within(headline).getByText("נמדד")).toBeInTheDocument();
  });

  it("shows precision and sample size per flexibility level, the date and the definition", () => {
    render(<QualityMetric quality={measured} />);
    const table = screen.getByRole("table", { name: "דיוק לפי רמת גמישות" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[1]!).getByText("98.7%")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("400")).toBeInTheDocument();
    expect(screen.getByText(/הגדרה\./)).toBeInTheDocument();
    expect(screen.getByText("6 באוקטובר 2026")).toHaveAttribute("datetime", "2026-10-06");
    expect(screen.getByText(/הסט נוצר מתבניות/)).toBeInTheDocument();
    // the 98% is labeled as a target, not a result
    expect(screen.getByText("יעד")).toBeInTheDocument();
  });

  it("drops the synthetic note when the evaluation set is real", () => {
    render(<QualityMetric quality={{ ...measured, synthetic: false }} />);
    expect(screen.queryByText(/סינתטי/)).not.toBeInTheDocument();
    expect(screen.getByText(/הסט תויג ידנית/)).toBeInTheDocument();
  });

  it("shows no number when nothing was measured yet", () => {
    render(<QualityMetric quality={{ generated_at: "2026-10-07T06:00:00Z", available: false }} />);
    expect(screen.getByText("איכות ההתאמה טרם נמדדה.")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("rounds down so a number is never overstated", () => {
    expect(percentDown(0.9996)).toBe("99.9%");
    expect(percentDown(1)).toBe("100.0%");
    expect(percentDown(0.9745)).toBe("97.4%");
    expect(percentDown(0.98)).toBe("98.0%");
  });
});
