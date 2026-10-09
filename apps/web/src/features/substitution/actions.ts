/**
 * Substitution actions shared by the substitution card and the results screen.
 * "Keep the original" and "not a good substitute" switch the list row to the exact product (with
 * the original barcode when the API gave one), which changes the /optimize request, so the
 * results recompute on the next render. Feedback goes to /feedback/substitution (D5 labeling).
 */
import { substitutionFeedback, type PricedItem } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { substitutionMessages } from "@/i18n/messages/substitution";
import { levelForCanonical } from "@/features/compare/substitutionLevels";
import { reportSubstitutionVerdict } from "@/features/consent/betaEvents";
import { getListState, listActions } from "@/state/list";
import { setFlash } from "@/state/flash";

function feedbackBody(item: PricedItem, verdict: "not_good" | "kept_original" | "accepted") {
  return {
    canonical_id: item.canonical_id,
    original_item_id: item.original_item_id ?? null,
    substitute_item_id: item.item_id,
    verdict,
  };
}

/** Beta event for the answer, with the level the user set for this product (read before it changes). */
function reportVerdict(item: PricedItem, verdict: "not_good" | "kept_original" | "accepted") {
  reportSubstitutionVerdict(levelForCanonical(getListState().items, item.canonical_id), verdict);
}

export function acceptSubstitute(item: PricedItem): void {
  reportVerdict(item, "accepted");
  substitutionFeedback(feedbackBody(item, "accepted")).catch(() => {
    // Accepting is the default; a lost signal changes nothing for the user.
  });
}

/** `locale` picks the language of the message shown afterwards (the caller's `useLocale()`). */
export function keepOriginal(
  item: PricedItem,
  originalName?: string | null,
  locale: Locale = DEFAULT_LOCALE,
): void {
  reportVerdict(item, "kept_original");
  listActions.keepOriginal(item.canonical_id, item.original_item_id ?? null);
  substitutionFeedback(feedbackBody(item, "kept_original")).catch(() => {});
  setFlash(
    translate(substitutionMessages, locale, "flashKept", {
      name: originalName ? `: ${originalName}` : "",
    }),
  );
}

/** Records "not a good substitute" and reverts to the original. Resolves to false when the
 * feedback could not be sent (the revert still happens). */
export async function rejectSubstitute(
  item: PricedItem,
  originalName?: string | null,
  locale: Locale = DEFAULT_LOCALE,
): Promise<boolean> {
  reportVerdict(item, "not_good");
  let sent = true;
  try {
    await substitutionFeedback(feedbackBody(item, "not_good"));
  } catch {
    sent = false;
  }
  listActions.keepOriginal(item.canonical_id, item.original_item_id ?? null);
  setFlash(
    sent
      ? translate(substitutionMessages, locale, "flashRejected", {
          name: originalName ? `: ${originalName}` : "",
        })
      : translate(substitutionMessages, locale, "flashRejectFailed"),
  );
  return sent;
}
