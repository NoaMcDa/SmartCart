"use client";

import { DocumentTitle } from "@/components/shell/PageChrome";
import { useT } from "@/i18n/LocaleProvider";
import { betaMessages } from "@/i18n/messages/beta";
import styles from "./Beta.module.css";

/**
 * The h1 of the beta pages (a client component so it follows the UI language). `join` is the
 * invite page, whose document title is "הצטרפות לבטא" rather than the page title.
 */
export function BetaTitle({ join = false }: { join?: boolean }) {
  const t = useT(betaMessages);
  return (
    <>
      <DocumentTitle text={t(join ? "joinTitle" : "pageTitle")} />
      <h1 className={styles.title}>{t("pageTitle")}</h1>
    </>
  );
}
