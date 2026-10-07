import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrustedPrice } from "./TrustedPrice";
import { formatUpdatedAt, UpdatedAt } from "./UpdatedAt";

// 2026-10-07 12:00 Israel time.
const NOW = new Date("2026-10-07T09:00:00Z");

describe("formatUpdatedAt", () => {
  it("is relative and in Israel time", () => {
    expect(formatUpdatedAt("2026-10-07T03:40:00Z", NOW)).toBe("היום 06:40");
    expect(formatUpdatedAt("2026-10-06T15:20:00Z", NOW)).toBe("אתמול 18:20");
    // 22:30 UTC on the 6th is already the 7th in Israel.
    expect(formatUpdatedAt("2026-10-06T22:30:00Z", NOW)).toBe("היום 01:30");
    expect(formatUpdatedAt("2026-10-04T10:00:00Z", NOW)).toBe("לפני 3 ימים");
    expect(formatUpdatedAt("2026-09-12T10:00:00Z", NOW)).toMatch(/^12\.0?9\.2026$/);
  });

  it("returns null for missing or invalid input", () => {
    expect(formatUpdatedAt(null, NOW)).toBeNull();
    expect(formatUpdatedAt("not a date", NOW)).toBeNull();
  });
});

describe("UpdatedAt and TrustedPrice", () => {
  it("renders a <time> with the machine-readable timestamp", () => {
    render(<UpdatedAt iso="2026-10-07T03:40:00Z" now={NOW} />);
    const time = screen.getByText("עודכן היום 06:40");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("datetime", "2026-10-07T03:40:00Z");
  });

  it("says the time is unknown rather than hiding it", () => {
    render(<UpdatedAt iso={undefined} />);
    expect(screen.getByText("מועד העדכון לא ידוע")).toBeInTheDocument();
  });

  it("never renders a price without its update time", () => {
    const { container } = render(
      <TrustedPrice amount="5.90" updatedAt="2026-10-07T03:40:00Z" fractionDigits={2} />,
    );
    const scope = container.querySelector('[data-trust-scope="price"]')!;
    expect(scope.querySelector('span[dir="ltr"]')?.textContent).toBe("₪ 5.90");
    expect(scope.querySelector("time[datetime]")).not.toBeNull();
  });
});
