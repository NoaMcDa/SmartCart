/** A target price typed by the shopper: "8.9", "8,90", "₪ 9". Positive, at most 9,999, or null. */
export function parseThreshold(text: string): number | null {
  if (/^\s*[-\u2212]/.test(text)) return null;
  const cleaned = text.replace(/[^\d.,]/g, "").replace(",", ".");
  if (cleaned === "") return null;
  const n = Number.parseFloat(cleaned);
  if (!Number.isFinite(n) || n <= 0 || n > 9999) return null;
  return Math.round(n * 100) / 100;
}
