/**
 * Calendar helpers for the monthly budget (issue #70). A "month" is `YYYY-MM` and a "date" is
 * `YYYY-MM-DD`, both on the Israel calendar: a shop at 00:30 on the 1st belongs to the new month
 * wherever the browser's clock says it is.
 */

const TIME_ZONE = "Asia/Jerusalem";

const dateParts = new Intl.DateTimeFormat("en-US", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** `YYYY-MM-DD` of `now` in Israel. */
export function israelDate(now: Date = new Date()): string {
  const parts = Object.fromEntries(dateParts.formatToParts(now).map((p) => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export const monthOf = (date: string): string => date.slice(0, 7);

export function currentMonth(now: Date = new Date()): string {
  return monthOf(israelDate(now));
}

export function isMonth(value: string): boolean {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

/** `count` months ending at `month` (inclusive), oldest first. */
export function monthsEndingAt(month: string, count: number): string[] {
  const [y, m] = month.split("-").map(Number) as [number, number];
  const out: string[] = [];
  for (let back = count - 1; back >= 0; back -= 1) {
    const index = y * 12 + (m - 1) - back;
    const year = Math.floor(index / 12);
    out.push(`${year}-${String((index % 12) + 1).padStart(2, "0")}`);
  }
  return out;
}

/** "אוקטובר" (long) or "אוק׳" (short) for a `YYYY-MM`. */
export function monthName(month: string, style: "long" | "short" = "long"): string {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return new Date(Date.UTC(y, m - 1, 15)).toLocaleDateString("he-IL", {
    month: style,
    timeZone: "UTC",
  });
}

/** "8.10" for a `YYYY-MM-DD`. */
export function dayLabel(date: string): string {
  const [, m, d] = date.split("-").map(Number) as [number, number, number];
  return `${d}.${m}`;
}
