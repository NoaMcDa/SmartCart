/**
 * Small helpers the personalization components share: a category's name in the UI language, a
 * quantity as text, and a list row for a product from the history.
 */
import type { ReactNode } from "react";
import type { CanonicalRef, ParsedRow } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { personalMessages } from "@/i18n/messages/personal";
import { stateMessages } from "@/i18n/messages/state";
import { categoryLabel } from "@/features/profile/dietOptions";
import { categoryLeaf } from "@/state/flex";

/**
 * "חלב", "ביצים", or the department's name: the Hebrew path name of a product of the category when
 * one is known, else the profile's name for the category or for its department, else the generic
 * "other category". Arabic goes by the id (the API sends Hebrew category names only).
 */
export function categoryName(
  taxonomyId: string,
  sample: CanonicalRef | null,
  locale: Locale = DEFAULT_LOCALE,
): string {
  if (locale === DEFAULT_LOCALE) {
    const leaf = categoryLeaf(sample);
    if (leaf) return leaf;
  }
  const own = categoryLabel(taxonomyId, locale);
  if (own !== taxonomyId) return own;
  const root = taxonomyId.split(".")[0] ?? taxonomyId;
  const dept = categoryLabel(root, locale);
  return dept !== root ? dept : translate(stateMessages, locale, "otherDepartment");
}

/** A quantity as an LTR number, with the unit word for a weight ("1.5 ק״ג"). */
export function Qty({
  quantity,
  kg,
  locale = DEFAULT_LOCALE,
}: {
  quantity: number;
  kg: boolean;
  locale?: Locale;
}): ReactNode {
  return (
    <>
      <span dir="ltr">{quantity}</span>
      {kg ? ` ${translate(personalMessages, locale, "kg")}` : ""}
    </>
  );
}

/** The `/parse-list` row for a product the person already knows: a confident match, no question. */
export function parsedRowFor(ref: CanonicalRef, quantity: number): ParsedRow {
  const kg = ref.base_unit === "kg";
  return {
    input_text: ref.display_name_he,
    canonical: ref,
    confidence: 1,
    needs_confirmation: false,
    not_found: false,
    candidates: [],
    quantity: String(quantity),
    unit: kg ? "kg" : null,
    flex_level: "any_brand",
    is_weighed: kg,
  };
}
