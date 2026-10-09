"use client";

import { useLocale, useT } from "./LocaleProvider";
import { legalMessages } from "./messages/legal";
import styles from "./LegalNotice.module.css";

/**
 * "This is a translation; the Hebrew text governs" (issue #73). Legal and consent texts in Arabic
 * carry it, visibly, until a lawyer has reviewed the Arabic. Renders nothing in Hebrew, so the
 * Hebrew screens are unchanged.
 */
export function LegalNotice({ className }: { className?: string }) {
  const { locale } = useLocale();
  const t = useT(legalMessages);
  if (locale !== "ar") return null;
  return (
    <p
      className={[styles.notice, className].filter(Boolean).join(" ")}
      lang="ar"
      data-testid="legal-translation-note"
    >
      {t("translationNotice")}
    </p>
  );
}
