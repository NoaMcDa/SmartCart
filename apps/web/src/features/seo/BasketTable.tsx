import { Price, Tag } from "@/components/ui";
import { formatDateHe, isoDate, monthLabelHe, UNIT_LABEL } from "./format";
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
  const ranked = month.chains.filter((c) => c.complete);
  const unranked = month.chains.filter((c) => !c.complete);
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <section className={styles.month} aria-labelledby={`month-${month.month}`}>
      <Heading id={`month-${month.month}`} className={styles.h2}>
        {monthLabelHe(month.month)}
      </Heading>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <caption>
            סך הסל הקבוע בכל רשת, {monthLabelHe(month.month)}
            {month.price_date ? (
              <>
                {" "}
                (מחירים נכונים לתאריך{" "}
                <time dateTime={isoDate(month.price_date)}>{formatDateHe(month.price_date)}</time>)
              </>
            ) : null}
          </caption>
          <thead>
            <tr>
              <th scope="col">רשת</th>
              <th scope="col">סך הסל</th>
              <th scope="col">הפרש מהזולה</th>
              <th scope="col">הפרש באחוזים</th>
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
                      <Tag variant="estimated">כולל מחירי הערכה</Tag>
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
                    "הזולה ביותר"
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
          לא מדורגות, כי חסרים להן מחירים לחלק מהסל:{" "}
          {unranked.map((c) => `${c.name} (${c.missing.length} פריטים)`).join(", ")}.
        </p>
      ) : null}
      <p className={styles.muted}>
        <a href={`/seo/reports/basket-index-${month.month}.md`} download>
          הדוח התמציתי לעיתונות, {monthLabelHe(month.month)}
        </a>
      </p>
    </section>
  );
}

/** The fixed basket (version, items and amounts), published so the index can be checked. */
export function BasketDefinition({ basket }: { basket: BasketIndexFile["basket"] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption>
          הסל הקבוע, גרסה {basket.version}: {basket.item_count} מוצרים
        </caption>
        <thead>
          <tr>
            <th scope="col">מוצר</th>
            <th scope="col">כמות בסל</th>
            <th scope="col">מחיר נמדד ל</th>
          </tr>
        </thead>
        <tbody>
          {basket.items.map((item) => (
            <tr key={item.slug}>
              <th scope="row">{item.name_he}</th>
              <td>{item.label_he}</td>
              <td>{UNIT_LABEL[item.base_unit]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
