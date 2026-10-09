"use client";

import type { ReactNode } from "react";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { Breadcrumbs } from "@/features/seo/components";
import { ACCESSIBILITY_PATH } from "@/features/seo/config";
import { formatDateHe, isoDate } from "@/features/seo/format";
import styles from "@/features/seo/seo.module.css";
import { formatRich } from "@/i18n/format";
import { LegalNotice } from "@/i18n/LegalNotice";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { INTL_LOCALE } from "@/i18n/locales";
import { accessibilityMessages } from "@/i18n/messages/accessibility";
import { CoordinatorLine } from "./CoordinatorLine";

/**
 * The accessibility statement (#26, standard 5568): Hebrew in the server markup, Arabic after
 * mount. The page file stays a server component (metadata, JSON-LD, the build-time contact
 * details) and passes them in; the Arabic carries the "translation, the Hebrew governs" line.
 */
export function AccessibilityBody({
  reviewed,
  contactName,
  contactEmail,
  contactPhone,
  children,
}: {
  /** ISO timestamp of the last accessibility review. */
  reviewed: string;
  contactName?: string;
  contactEmail?: string;
  contactPhone?: string;
  /** Rendered first inside the article (the page's JSON-LD). */
  children?: ReactNode;
}) {
  const t = useT(accessibilityMessages);
  const { locale } = useLocale();
  const crumbs = [
    { name: t("crumbHome"), path: "/" },
    { name: t("pageTitle"), path: ACCESSIBILITY_PATH },
  ];
  const date =
    locale === "ar"
      ? new Intl.DateTimeFormat(INTL_LOCALE.ar, {
          day: "numeric",
          month: "long",
          year: "numeric",
          timeZone: "Asia/Jerusalem",
        }).format(new Date(reviewed))
      : formatDateHe(reviewed);
  return (
    <article className={styles.page}>
      <DocumentTitle text={t("pageTitle")} />
      {children}
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{t("pageTitle")}</h1>
        <LegalNotice />
        <p className={styles.lede}>{t("lede")}</p>
        <p className={styles.muted}>
          {formatRich(t("lastChecked"), {
            date: <time dateTime={isoDate(reviewed)}>{date}</time>,
          })}
        </p>
      </header>

      <section className={styles.section} aria-labelledby="h-done">
        <h2 id="h-done" className={styles.h2}>
          {t("doneHeading")}
        </h2>
        <ul>
          <li>{t("done1")}</li>
          <li>{t("done2")}</li>
          <li>{t("done3")}</li>
          <li>{t("done4")}</li>
          <li>{t("done5")}</li>
          <li>{t("done6")}</li>
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="h-todo">
        <h2 id="h-todo" className={styles.h2}>
          {t("todoHeading")}
        </h2>
        <ul>
          <li>{t("todo1")}</li>
          <li>{t("todo2")}</li>
          <li>{t("todo3")}</li>
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="h-report">
        <h2 id="h-report" className={styles.h2}>
          {t("reportHeading")}
        </h2>
        <p>
          {t("reportBody")}
          <CoordinatorLine name={contactName} email={contactEmail} phone={contactPhone} />
        </p>
      </section>
    </article>
  );
}
