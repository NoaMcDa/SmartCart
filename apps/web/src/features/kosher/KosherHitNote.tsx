"use client";

import { Tag } from "@/components/ui";
import { useT } from "@/i18n/LocaleProvider";
import { kosherMessages } from "@/i18n/messages/kosher";
import type { Schemas } from "@/api/client";

/**
 * A search hit under a kosher filter: whether the catalog has an item for it whose name states a
 * certification that meets the filter, only items that state nothing (the unknown warning), or
 * none that can be offered. A hit is a product, not an item, so it is never hidden.
 */
export function KosherHitNote({ label }: { label: Schemas["KosherHitLabel"] | null | undefined }) {
  const t = useT(kosherMessages);
  if (!label) return null;
  if (label.status === "meets") {
    return (
      <span data-testid="kosher-hit" data-kosher="meets">
        <Tag variant="matched">{t("hitMeets")}</Tag>
      </span>
    );
  }
  if (label.status === "unknown") {
    return (
      <span data-testid="kosher-hit" data-kosher="unknown">
        <Tag variant="unverified">{t("hitUnknown")}</Tag>
      </span>
    );
  }
  return (
    <span data-testid="kosher-hit" data-kosher="none">
      <Tag variant="missing">{t("hitNone")}</Tag>
    </span>
  );
}
