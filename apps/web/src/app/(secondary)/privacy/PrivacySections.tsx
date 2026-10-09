"use client";

import { useT } from "@/i18n/LocaleProvider";
import { privacyMessages } from "@/i18n/messages/privacy";
import styles from "./privacy.module.css";

/** The "draft, pending legal review" mark under the page title (#30). */
export function PrivacyDraftBadge() {
  const t = useT(privacyMessages);
  return (
    <p className={styles.draft} data-testid="privacy-draft">
      <strong>{t("draft")}</strong>
      <span>{t("draftNote")}</span>
    </p>
  );
}

/**
 * Sections for first-party beta events, photos, voice, spend tracking and the online-store
 * handoff. Their wording lives in `i18n/messages/privacy.ts`; keep it in step with what those
 * features really do (docs/web.md "Privacy and deletion", docs/beta-plan.md section 3).
 */
export function PrivacySections() {
  const t = useT(privacyMessages);
  return (
    <>
      <section aria-labelledby="p-beta">
        <h2 id="p-beta">{t("betaTitle")}</h2>
        <ul>
          <li>{t("betaSent")}</li>
          <li>{t("betaNever")}</li>
          <li>{t("betaConsent")}</li>
          <li>{t("betaOptOut")}</li>
        </ul>
      </section>

      <section aria-labelledby="p-photos">
        <h2 id="p-photos">{t("photosTitle")}</h2>
        <ul>
          <li>{t("photosProcess")}</li>
          <li>{t("photosText")}</li>
          <li>{t("photosConsent")}</li>
          <li>{t("photosWithdraw")}</li>
        </ul>
      </section>

      <section aria-labelledby="p-voice">
        <h2 id="p-voice">{t("voiceTitle")}</h2>
        <ul>
          <li>{t("voiceBody")}</li>
          <li>{t("voiceBrowser")}</li>
        </ul>
      </section>

      <section aria-labelledby="p-spend">
        <h2 id="p-spend">{t("spendTitle")}</h2>
        <ul>
          <li>{t("spendStored")}</li>
          <li>{t("spendWhere")}</li>
          <li>{t("spendControl")}</li>
        </ul>
      </section>

      <section aria-labelledby="p-handoff">
        <h2 id="p-handoff">{t("handoffTitle")}</h2>
        <ul>
          <li>{t("handoffBody")}</li>
          <li>{t("handoffReferral")}</li>
        </ul>
      </section>
    </>
  );
}
