import { describe, expect, it } from "vitest";
import { validBudget } from "@/features/budget/budgetState";
import { validSpendTotal } from "@/features/budget/spendState";
import { parseThreshold } from "@/features/alerts/threshold";
import { buildGapRequest } from "@/features/feedback/gapReport";
import { parseShelfPrice } from "@/features/scan/ResultCard";
import { normalizeNumberInput } from "./numberInput";

describe("normalizeNumberInput", () => {
  it("turns Arabic-Indic and Persian digits and separators into Latin ones", () => {
    expect(normalizeNumberInput("٩٫٩٠")).toBe("9.90");
    expect(normalizeNumberInput("۱۲٬۵")).toBe("12,5");
    expect(normalizeNumberInput("٣٫٥")).toBe("3.5");
  });

  it("drops bidi marks and spaces, leaves everything else alone", () => {
    expect(normalizeNumberInput("\u200f\u20aa\u00a09.90\u200e ")).toBe("\u20aa 9.90");
    expect(normalizeNumberInput("abc")).toBe("abc");
  });
});

describe("amounts typed on an Arabic keyboard are read, not reported invalid", () => {
  it("alert threshold", () => {
    expect(parseThreshold("٨٫٩٠")).toBe(8.9);
    expect(parseThreshold("٩")).toBe(9);
    expect(parseThreshold("−٩")).toBeNull();
    expect(parseThreshold("0")).toBeNull();
  });

  it("shelf price on the scan card", () => {
    expect(parseShelfPrice("١٤٫٩٠")).toBe(14.9);
  });

  it("corrected spend total", () => {
    expect(validSpendTotal("٣٧١٫٤٠")).toBe(371.4);
    expect(validSpendTotal("₪ ٣٧١")).toBe(371);
    expect(validSpendTotal("٣٧١٫٤٠٠")).toBeNull();
  });

  it("monthly budget, which also takes a thousands separator", () => {
    expect(validBudget("٢٥٠٠")).toBe(2500);
    expect(validBudget("2,500")).toBe(2500);
    expect(validBudget("₪ 2,500")).toBe(2500);
    expect(validBudget("12,5")).toBeNull();
    expect(validBudget("")).toBeNull();
  });

  it("the price at the shelf in a gap report keeps the number the person typed", () => {
    const body = buildGapRequest(
      { storeId: 1, storeName: "x" },
      { reason: null, actualPrice: "١٢٫٥٠", note: "" },
    );
    expect(body.actual_price).toBe(12.5);
  });
});
