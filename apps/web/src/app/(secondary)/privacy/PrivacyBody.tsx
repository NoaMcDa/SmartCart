"use client";

import Link from "next/link";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { formatRich } from "@/i18n/format";
import { LegalNotice } from "@/i18n/LegalNotice";
import { useT } from "@/i18n/LocaleProvider";
import { privacyMessages } from "@/i18n/messages/privacy";
import { PrivacyDraftBadge, PrivacySections } from "./PrivacySections";
import styles from "./privacy.module.css";

/**
 * The privacy policy text (issue #30, D10, D11), Hebrew by default and Arabic after mount (the
 * route file is a server component, so the words live here). It states what the MVP actually does;
 * keep it in step with docs/web.md "Privacy and deletion". The Arabic carries a visible "this is a
 * translation, the Hebrew governs" line until a lawyer has reviewed it.
 */
export function PrivacyBody() {
  const t = useT(privacyMessages);
  const profile = <Link href="/profile">{t("profileWord")}</Link>;
  return (
    <article className={styles.page}>
      <DocumentTitle text={t("pageTitle")} />
      <h1 className={styles.title}>{t("pageTitle")}</h1>
      <PrivacyDraftBadge />
      <LegalNotice />
      <p className={styles.lead}>{t("lead")}</p>

      <section aria-labelledby="p-collect">
        <h2 id="p-collect">{t("collectTitle")}</h2>
        <ul>
          <li>
            <strong>{t("collectLocationLead")}</strong> {t("collectLocation")}
          </li>
          <li>
            <strong>{t("collectHomeLead")}</strong> {t("collectHome")}
          </li>
          <li>
            <strong>{t("collectDietLead")}</strong> {t("collectDiet")}
          </li>
          <li>
            <strong>{t("collectListsLead")}</strong> {t("collectLists")}
          </li>
          <li>
            <strong>{t("collectGapsLead")}</strong> {t("collectGaps")}
          </li>
          <li>
            <strong>{t("collectEmailLead")}</strong> {t("collectEmail")}
          </li>
        </ul>
      </section>

      <section aria-labelledby="p-nosale">
        <h2 id="p-nosale">{t("noTitle")}</h2>
        <ul>
          <li>{t("no1")}</li>
          <li>{t("no2")}</li>
          <li>{t("no3")}</li>
        </ul>
      </section>

      <section aria-labelledby="p-where">
        <h2 id="p-where">{t("whereTitle")}</h2>
        <ul>
          <li>
            <strong>{t("whereDeviceLead")}</strong> {t("whereDevice")}
          </li>
          <li>
            <strong>{t("whereAccountLead")}</strong> {t("whereAccount")}
          </li>
          <li>
            <strong>{t("whereMapLead")}</strong> {t("whereMap")}
          </li>
        </ul>
      </section>

      <PrivacySections />

      <section aria-labelledby="p-retention">
        <h2 id="p-retention">{t("retentionTitle")}</h2>
        <ul>
          <li>{t("retention1")}</li>
          <li>{formatRich(t("retention2"), { profile })}</li>
        </ul>
      </section>

      <section aria-labelledby="p-delete">
        <h2 id="p-delete">{t("deleteTitle")}</h2>
        <p>{formatRich(t("deleteBody"), { profile })}</p>
      </section>

      <p className={styles.note}>{t("note")}</p>
    </article>
  );
}
