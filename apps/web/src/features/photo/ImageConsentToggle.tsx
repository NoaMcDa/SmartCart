"use client";

import { Switch } from "@/components/ui/Switch";
import { setImageConsent, useImageConsent } from "@/features/consent/imageConsent";
import { useT } from "@/i18n/LocaleProvider";
import { photoMessages } from "@/i18n/messages/photo";

/**
 * Profile control for the photo consent (issues #61 and #68): on after the person agreed in the
 * sheet, and turning it off withdraws the consent at once. Turning it on here is the same yes as
 * the sheet's "מסכים/ה".
 */
export function ImageConsentToggle() {
  const t = useT(photoMessages);
  const granted = useImageConsent();
  return (
    <Switch
      label={t("toggleLabel")}
      description={t("toggleDescription")}
      checked={granted}
      onChange={setImageConsent}
    />
  );
}
