"use client";

import { useT } from "@/i18n/LocaleProvider";
import { uiMessages } from "@/i18n/messages/ui";
import { Tag } from "./Tag";

export type PromoConfidenceProps = {
  /** `PricedItem.promo_confidence`, 0 to 1; null or undefined when the promo was not scored. */
  confidence: number | null | undefined;
};

/** At or above this the tag reads as verified (green check); below it stays amber. */
const HIGH = 0.9;

/**
 * Trust tag for a promo (D10, issue #12): "ביטחון 96%" when the API scored how sure it is that the
 * promo was parsed correctly, "לא נבדק" when it did not. Never a made-up number, and never
 * nothing: a promo without a score says so.
 */
export function PromoConfidence({ confidence }: PromoConfidenceProps) {
  const t = useT(uiMessages);
  const known = typeof confidence === "number" && Number.isFinite(confidence);
  const percent = known ? Math.round(Math.min(1, Math.max(0, confidence)) * 100) : null;
  return (
    <span
      title={t("promoConfidenceTitle")}
      data-promo-confidence={percent === null ? "unknown" : String(percent)}
    >
      {percent === null ? (
        <Tag variant="unverified">{t("promoUnchecked")}</Tag>
      ) : (
        <Tag variant={percent >= HIGH * 100 ? "matched" : "unverified"}>
          {t("promoConfidence", { percent })}
        </Tag>
      )}
    </span>
  );
}
