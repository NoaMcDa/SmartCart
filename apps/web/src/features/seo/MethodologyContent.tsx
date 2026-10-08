"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { methodologyMessages } from "@/i18n/messages/methodology";
import { seoMessages } from "@/i18n/messages/seo";
import { Breadcrumbs, FlexLevelsExplained, Kind, ListBuilderCta } from "./components";
import { BASKET_INDEX_PATH, METHODOLOGY_PATH, METHODOLOGY_UPDATED } from "./config";
import { formatDate, isoDate } from "./format";
import { QualityMetric } from "./QualityMetric";
import type { Quality } from "./types";
import styles from "./seo.module.css";

const bold = (c: ReactNode) => <strong>{c}</strong>;
const ltr = (c: ReactNode) => <span dir="ltr">{c}</span>;

/**
 * Body of `/methodology` (#21). A client component so it can switch to Arabic after hydration,
 * but the server render is Hebrew (what search engines index); the page keeps the metadata and
 * the JSON-LD. Only the text is translated: the numbers come from the same data.
 */
export function MethodologyContent({
  productCount,
  quality,
}: {
  productCount: number;
  quality: Quality;
}) {
  const t = useT(methodologyMessages);
  const r = useRich(methodologyMessages);
  const seo = useT(seoMessages);
  const { locale } = useLocale();
  const title = t("title");
  const kinds = {
    measured: <Kind kind="measured" />,
    estimate: <Kind kind="estimate" />,
    target: <Kind kind="target" />,
    law: <Kind kind="law" />,
  };
  const checkout = seo("checkoutGoverns");
  return (
    <>
      <Breadcrumbs
        crumbs={[
          { name: seo("home"), path: "/" },
          { name: title, path: METHODOLOGY_PATH },
        ]}
      />
      <header className={styles.section}>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.lede}>{r("lede", kinds)}</p>
        <p className={styles.muted}>
          {t("updatedLast")}{" "}
          <time dateTime={isoDate(METHODOLOGY_UPDATED)}>
            {formatDate(METHODOLOGY_UPDATED, locale)}
          </time>
        </p>
      </header>

      <section id="sources" className={styles.section} aria-labelledby="h-sources">
        <h2 id="h-sources" className={styles.h2}>
          {t("sourcesH")}
        </h2>
        <p>{t("sourcesP")}</p>
        <ul>
          <li>{r("sourcesLi1", kinds)}</li>
          <li>{t("sourcesLi2")}</li>
          <li>{t("sourcesLi3")}</li>
          <li>{r("sourcesLi4", { b: bold }, { checkout })}</li>
        </ul>
      </section>

      <section id="matching" className={styles.section} aria-labelledby="h-matching">
        <h2 id="h-matching" className={styles.h2}>
          {t("matchingH")}
        </h2>
        <p>{t("matchingP")}</p>
        <FlexLevelsExplained />
        <ul>
          <li>{r("matchingLi1", { b: bold })}</li>
          <li>{r("matchingLi2", { b: bold })}</li>
          <li>{r("matchingLi3", { b: bold })}</li>
          <li>{t("matchingLi4")}</li>
        </ul>
        <p className={styles.muted}>
          {r("catalogCount", { ...kinds, ltr }, { count: productCount })}
        </p>
      </section>

      <section id="saving" className={styles.section} aria-labelledby="h-saving">
        <h2 id="h-saving" className={styles.h2}>
          {t("savingH")}
        </h2>
        <p>{r("savingP", { b: bold })}</p>
        <p>{r("savingFormula", { b: bold })}</p>
        <ul>
          <li>{t("savingLi1")}</li>
          <li>{t("savingLi2")}</li>
          <li>{t("savingLi3")}</li>
        </ul>
      </section>

      <section id="neutrality" className={styles.section} aria-labelledby="h-neutrality">
        <h2 id="h-neutrality" className={styles.h2}>
          {t("neutralityH")}
        </h2>
        <ul>
          <li>{t("neutralityLi1")}</li>
          <li>{t("neutralityLi2")}</li>
          <li>{t("neutralityLi3")}</li>
          <li>{t("neutralityLi4")}</li>
        </ul>
      </section>

      <section id="quality" className={styles.section} aria-labelledby="h-quality">
        <h2 id="h-quality" className={styles.h2}>
          {t("qualityH")}
        </h2>
        <p>{t("qualityP")}</p>
        <QualityMetric quality={quality} />
      </section>

      <section id="basket-index" className={styles.section} aria-labelledby="h-basket">
        <h2 id="h-basket" className={styles.h2}>
          {t("basketH")}
        </h2>
        <p>{r("basketP", { link: (c) => <Link href={BASKET_INDEX_PATH}>{c}</Link> })}</p>
      </section>

      <section id="privacy" className={styles.section} aria-labelledby="h-privacy">
        <h2 id="h-privacy" className={styles.h2}>
          {t("privacyH")}
        </h2>
        <ul>
          <li>{t("privacyLi1")}</li>
          <li>{t("privacyLi2")}</li>
          <li>{t("privacyLi3")}</li>
          <li>{t("privacyLi4")}</li>
          <li>{t("privacyLi5")}</li>
        </ul>
      </section>

      <ListBuilderCta variant="methodology" />
    </>
  );
}
