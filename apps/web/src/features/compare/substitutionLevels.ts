import type { FlexLevel, Plan } from "@/api/client";
import { planSubstitutions } from "@/state/comparison";
import type { ListItem } from "@/state/list";

/**
 * The flexibility level the user set for a product, by canonical id. The API does not return the
 * level on a priced line, so the list row is the source; undefined when no row matches.
 */
export function levelForCanonical(
  items: ReadonlyArray<Pick<ListItem, "canonical" | "flexLevel">>,
  canonicalId: number,
): FlexLevel | null {
  return items.find((i) => i.canonical?.canonical_id === canonicalId)?.flexLevel ?? null;
}

/**
 * How many substitutes the plan lists per flexibility level (the `substitutions_shown`
 * denominator). A substitute whose row cannot be found is not counted: no level is invented.
 */
export function substitutionLevelCounts(
  plan: Plan,
  items: ReadonlyArray<Pick<ListItem, "canonical" | "flexLevel">>,
): Partial<Record<FlexLevel, number>> {
  const counts: Partial<Record<FlexLevel, number>> = {};
  for (const { item } of planSubstitutions(plan)) {
    const level = levelForCanonical(items, item.canonical_id);
    if (level) counts[level] = (counts[level] ?? 0) + 1;
  }
  return counts;
}
