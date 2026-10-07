import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PriceHistoryResponse } from "@/api/client";
import { PriceHistoryChart } from "./PriceHistoryChart";
import { DAY_MS, promoAudience, promoConfidence, promoRanges, promoAt } from "./series";

const END = Date.parse("2026-10-07T03:40:00Z");
const day = (n: number) => new Date(END - n * DAY_MS).toISOString();

const HISTORY: PriceHistoryResponse = {
  canonical_id: 1001,
  store_id: 103,
  days: 90,
  generated_at: day(0),
  points: [3, 2, 1, 0].map((d) => ({
    date: day(d),
    unit_price: d === 2 || d === 1 ? "5.20" : "6.50",
    shelf_price: "52.00",
    promo_description: d === 2 || d === 1 ? "2 ב-15" : null,
  })),
  promos: [
    {
      description: "2 ב-15",
      starts_at: day(2),
      ends_at: day(1),
      club_only: true,
      club_name: "רמי לוי",
      confidence: 0.87,
      promo_type: "bundle",
    },
    { description: "10% הנחה", starts_at: day(40), ends_at: day(35), club_only: false },
  ],
};

describe("club promos and confidence on the chart", () => {
  it("reads club, name and confidence from the API's promo windows", () => {
    const win = { start: END - 90 * DAY_MS, end: END };
    const [open, club] = promoRanges(HISTORY.promos, win).sort((a, b) => a.from - b.from);
    expect(open).toMatchObject({ clubOnly: false, clubName: null, confidence: null });
    expect(club).toMatchObject({ clubOnly: true, clubName: "רמי לוי", confidence: 0.87 });
    expect(promoAudience(open!)).toBe("מבצע לכולם");
    expect(promoAudience(club!)).toBe("מבצע מועדון · רמי לוי");
    expect(promoAudience({ clubOnly: true, clubName: null })).toBe("מבצע מועדון");
    expect(promoConfidence(club!)).toBe("ביטחון במבצע: 87%");
    expect(promoConfidence(open!)).toBe("ביטחון במבצע: לא נבדק");
    expect(promoAt([club!], END - 2 * DAY_MS)).toBe(club);
    expect(promoAt([club!], END - 10 * DAY_MS)).toBeNull();
  });

  it("tags club-only promos with a club Tag (icon and text) and shows confidence on every promo", () => {
    render(<PriceHistoryChart history={HISTORY} days={90} metric="unit" unitLabel="ליחידה" />);
    const rows = screen.getAllByTestId("history-promo-row");
    expect(rows).toHaveLength(2);
    const club = rows.find((r) => r.textContent?.includes("2 ב-15"))!;
    const tag = club.querySelector('[data-variant="club"]');
    expect(tag).toHaveTextContent("מבצע מועדון · רמי לוי");
    expect(tag?.querySelector("svg")).not.toBeNull();
    expect(club).toHaveTextContent("ביטחון במבצע: 87%");
    const open = rows.find((r) => r.textContent?.includes("10% הנחה"))!;
    expect(open.querySelector('[data-variant="club"]')).toBeNull();
    expect(open).toHaveTextContent("ביטחון במבצע: לא נבדק");
  });

  it("puts the audience and confidence in the marker tooltip", () => {
    render(<PriceHistoryChart history={HISTORY} days={90} metric="unit" unitLabel="ליחידה" />);
    const marker = screen.getAllByTestId("history-marker")[0]!;
    expect(
      within(marker).getByText(/מבצע מועדון · רמי לוי, ביטחון במבצע: 87%/),
    ).toBeInTheDocument();
    fireEvent.pointerEnter(marker);
    expect(screen.getByTestId("history-tooltip")).toHaveTextContent("מבצע מועדון · רמי לוי");
  });
});
