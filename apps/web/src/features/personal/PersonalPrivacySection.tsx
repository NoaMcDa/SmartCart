"use client";

import { useT } from "@/i18n/LocaleProvider";
import { personalMessages } from "@/i18n/messages/personal";

/**
 * The privacy page's paragraph on personalization (draft, awaiting legal review like the page).
 * Keep it in step with `docs/personalization.md` and with what `personalDoc.ts` stores.
 */
export function PersonalPrivacySection() {
  const t = useT(personalMessages);
  return (
    <section aria-labelledby="p-personal">
      <h2 id="p-personal">{t("privacyTitle")}</h2>
      <ul>
        <li>{t("privacyStored")}</li>
        <li>{t("privacyWhere")}</li>
        <li>{t("privacyControl")}</li>
        <li data-testid="personal-privacy-legal">{t("privacyLegal")}</li>
      </ul>
    </section>
  );
}
