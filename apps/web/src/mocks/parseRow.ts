/**
 * The mock list parser shared by `/parse-list` (handlers.ts) and `/parse-recipe`
 * (handlers.phase3.ts). Moved out of handlers.ts so the phase 3 handlers can use it without an
 * import cycle; handlers.ts still re-exports `parseRow`.
 */
import type { ParsedRow } from "@/api/client";
import { CATALOG, canonicalRef } from "./fixtures";

const HEBREW_NUMBERS: Record<string, number> = {
  אחד: 1,
  אחת: 1,
  שניים: 2,
  שתיים: 2,
  שני: 2,
  שתי: 2,
  שלוש: 3,
  שלושה: 3,
  ארבע: 4,
  ארבעה: 4,
};

/** "2 רסק עגבניות" -> { quantity: "2", name: "רסק עגבניות" }. */
function splitQuantity(raw: string): { quantity: string; name: string } {
  const text = raw.trim();
  const lead = /^(\d+(?:\.\d+)?)\s*(?:x|×)?\s+(.+)$/u.exec(text);
  if (lead?.[1] && lead[2]) return { quantity: lead[1], name: lead[2].trim() };
  const trail = /^(.+?)\s*(?:x|×)\s*(\d+(?:\.\d+)?)$/u.exec(text);
  if (trail?.[1] && trail[2]) return { quantity: trail[2], name: trail[1].trim() };
  const [first, ...rest] = text.split(/\s+/);
  if (first && HEBREW_NUMBERS[first] && rest.length)
    return { quantity: String(HEBREW_NUMBERS[first]), name: rest.join(" ") };
  return { quantity: "1", name: text };
}

export function parseRow(input: string, flexDefaults: Record<string, string> = {}): ParsedRow {
  const { quantity, name } = splitQuantity(input);
  const matches = Object.values(CATALOG).filter((c) => c.keywords.some((k) => name.includes(k)));
  // Prefer the item whose keyword is the longest match ("רסק עגבניות" over "עגבניות").
  matches.sort(
    (a, b) =>
      Math.max(...b.keywords.filter((k) => name.includes(k)).map((k) => k.length)) -
      Math.max(...a.keywords.filter((k) => name.includes(k)).map((k) => k.length)),
  );
  const best = matches[0];
  if (!best) {
    return {
      input_text: input,
      canonical: null,
      confidence: 0,
      needs_confirmation: true,
      not_found: true,
      candidates: [],
      quantity,
      flex_level: "any_brand",
      is_weighed: false,
    };
  }
  const ambiguous = matches.filter((m) => m.taxonomy_id === best.taxonomy_id);
  // "שמן זית" alone is ambiguous: ask, like the artboard's amber confirmation.
  const needsConfirmation = ambiguous.length > 1 && !/כתית|מעולה|\d/.test(name);
  const flex = flexDefaults[best.taxonomy_id];
  return {
    input_text: input,
    canonical: canonicalRef(best.canonical_id),
    confidence: needsConfirmation ? 0.62 : 0.95,
    needs_confirmation: needsConfirmation,
    not_found: false,
    candidates: needsConfirmation ? ambiguous.map((m) => canonicalRef(m.canonical_id)) : [],
    quantity,
    flex_level:
      flex === "exact" || flex === "close" || flex === "any_brand"
        ? flex
        : best.canonical_id === 1002 || best.canonical_id === 1005
          ? "exact"
          : "any_brand",
    is_weighed: Boolean(best.weighed),
  };
}
