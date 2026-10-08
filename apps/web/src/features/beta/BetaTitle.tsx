"use client";

import { useT } from "@/i18n/LocaleProvider";
import { betaMessages } from "@/i18n/messages/beta";
import styles from "./Beta.module.css";

/** The h1 of the beta pages (a client component so it follows the UI language). */
export function BetaTitle() {
  const t = useT(betaMessages);
  return <h1 className={styles.title}>{t("pageTitle")}</h1>;
}
