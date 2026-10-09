"use client";

import { Price, Tag } from "@/components/ui";
import { useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { seoMessages } from "@/i18n/messages/seo";
import { formatDate, isoDate, monthLabel, unitLabel } from "./format";
import type { BasketIndexFile, BasketMonth } from "./types";
import styles from "./seo.module.css";

/** Chain totals of one published month: chain, total, difference from the cheapest chain. */
export function BasketMonthTable({
  month,
  headingLevel = 2,
}: {
  month: BasketMonth;
  headingLevel?: 2 | 3;
}) {
  const t = useT(seoMessages);
  const r = useRich(seoMessages);
  const { locale } = useLocale();
  const monthText = monthLabel(month.month, locale);
  const ranked = month.chains.filter((c) => c.complete);
  const unranked = month.chains.filter((c) => !c.complete);
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <section className={styles.month} aria-labelledby={`month-${month.month}`}>
      <Heading id={`month-${month.month}`} className={styles.h2}>
        {monthText}
      </Heading>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <caption>
            {month.price_date
              ? r(
                  "basketCaptionDate",
                  {
                    time: (
                      <time dateTime={isoDate(month.price_date)}>
                        {formatDate(month.price_date, locale)}
                      </time>
                    ),
                  },
                  { month: monthText },
                )
              : t("basketCaption", { month: monthText })}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("colChain")}</th>
              <th scope="col">{t("basketColTotal")}</th>
              <th scope="col">{t("basketColDelta")}</th>
              <th scope="col">{t("basketColPct")}</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((c) => (
              <tr key={c.chain_id}>
                <th scope="row">
                  {c.name}
                  {c.estimated_items > 0 ? (
                    <>
                      {" "}
                      <Tag variant="estimated">{t("includesEstimates")}</Tag>
                    </>
                  ) : null}
                </th>
                <td className={styles.num}>
                  <Price amount={c.total ?? 0} fractionDigits={2} />
                </td>
                <td className={styles.num}>
                  {c.delta_vs_cheapest ? (
                    <Price amount={c.delta_vs_cheapest} fractionDigits={2} />
                  ) : (
                    t("cheapestChain")
                  )}
                </td>
                <td className={styles.num}>
                  {c.delta_pct ? <span dir="ltr">+{c.delta_pct.toFixed(1)}%</span> : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {unranked.length > 0 ? (
        <p className={styles.muted}>
          {t("unranked", {
            list: unranked
              .map((c) => t("unrankedItem", { name: c.name, count: c.missing.length }))
              .join(t("listSep")),
          })}
        </p>
      ) : null}
      <p className={styles.muted}>
        <a href={`/seo/reports/basket-index-${month.month}.md`} download>
          {t("pressReport", { month: monthText })}
        </a>
      </p>
    </section>
  );
}

/** The fixed basket (version, items and amounts), published so the index can be checked. */
export function BasketDefinition({ basket }: { basket: BasketIndexFile["basket"] }) {
  const t = useT(seoMessages);
  const { locale } = useLocale();
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption>
          {t("basketDefinitionCaption", { version: basket.version, count: basket.item_count })}
        </caption>
        <thead>
          <tr>
            <th scope="col">{t("basketColProduct")}</th>
            <th scope="col">{t("basketColAmount")}</th>
            <th scope="col">{t("basketColUnit")}</th>
          </tr>
        </thead>
        <tbody>
          {basket.items.map((item) => (
            <tr key={item.slug}>
              <th scope="row">{item.name_he}</th>
              <td>{item.label_he}</td>
              <td>{unitLabel(item.base_unit, locale)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
