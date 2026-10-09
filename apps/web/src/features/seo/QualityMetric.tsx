"use client";

import { FlexChip } from "@/components/ui";
import type { FlexLevel } from "@/components/ui";
import { useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { seoMessages } from "@/i18n/messages/seo";
import { Kind } from "./components";
import { formatDate, isoDate, percentDown } from "./format";
import type { Quality } from "./types";
import styles from "./seo.module.css";

const LEVELS: FlexLevel[] = ["exact", "any_brand", "close"];

/**
 * The public matching-quality metric (D10, issue #21). Every number is read from `quality.json`,
 * which `export-seo` writes from the latest `evaluate` row of `match_runs`; nothing here is typed
 * by hand. The headline is the "any brand" level (the one the 98% target is about); all three
 * levels are listed with the sample each was measured on. While the evaluation set is synthetic
 * the headline says so in the same sentence.
 */
export function QualityMetric({ quality }: { quality: Quality }) {
  const t = useT(seoMessages);
  const r = useRich(seoMessages);
  const { locale } = useLocale();
  const ltr = (c: React.ReactNode) => <span dir="ltr">{c}</span>;
  const bold = (c: React.ReactNode) => <strong>{c}</strong>;
  if (!quality.available) {
    return (
      <div className={styles.metric}>
        <p className={styles.metricHeadline}>{t("qmUnavailable")}</p>
        <p className={styles.muted}>{t("qmUnavailableHint")}</p>
      </div>
    );
  }
  const headline = quality.precision.any_brand;
  const rows = LEVELS.filter((l) => quality.precision[l] !== undefined);
  return (
    <div className={styles.metric} data-testid="quality-metric">
      {headline !== undefined ? (
        <p className={styles.metricHeadline}>
          {r("qmHeadline", { ltr }, { percent: percentDown(headline) })}
          {quality.synthetic ? t("qmSynthetic") : ""}
          <Kind kind="measured" />
        </p>
      ) : null}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <caption>{t("qmCaption")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("qmColLevel")}</th>
              <th scope="col">{t("qmColCorrect")}</th>
              <th scope="col">{t("qmColSample")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((level) => (
              <tr key={level}>
                <th scope="row">
                  <FlexChip level={level} size="sm" />
                </th>
                <td className={styles.num}>
                  <span dir="ltr">{percentDown(quality.precision[level] ?? 0)}</span>
                </td>
                <td className={styles.num}>
                  <span dir="ltr">{quality.sample[level] ?? 0}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={styles.definition}>
        <p>{r("qmDefinition", { b: bold })}</p>
        <p>
          {r(
            "qmSet",
            { b: bold, ltr },
            {
              pairs: quality.gold_pairs,
              items: quality.gold_items,
              note: quality.synthetic ? t("qmSetSynthetic") : t("qmSetReal"),
            },
          )}
        </p>
        <p>
          {r("qmMeasured", {
            b: bold,
            time: (
              <time dateTime={isoDate(quality.measured_at)}>
                {formatDate(quality.measured_at, locale)}
              </time>
            ),
          })}
        </p>
        <p>
          {r(
            "qmTarget",
            { b: bold, ltr, kind: <Kind kind="target" /> },
            { percent: percentDown(quality.target_any_brand) },
          )}
        </p>
      </div>
    </div>
  );
}
