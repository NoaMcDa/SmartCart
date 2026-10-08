import { Price } from "@/components/ui";
import { monthName } from "./month";
import type { MonthTotal } from "./spendState";
import styles from "./Budget.module.css";

const COL = 20; // viewBox units per month
const BAR = 12;
const HEIGHT = 60;
const TOP = 4; // headroom above the tallest bar

export type SpendChartProps = {
  /** Oldest first. */
  data: ReadonlyArray<MonthTotal>;
  budget: number | null;
  /** The month drawn in the accent color. */
  highlight: string;
};

/**
 * Spend per month as an SVG bar chart (no chart library), for the last six months. Time runs in
 * reading direction: the oldest month is on the right and the newest on the left, like the price
 * history. A dashed line marks the monthly budget when there is one. The drawing is decorative
 * (`aria-hidden`); the table under it carries every number for screen readers and for narrow
 * screens, where the month names under the bars are hidden.
 */
export function SpendChart({ data, budget, highlight }: SpendChartProps) {
  const n = data.length;
  const width = n * COL;
  const max = Math.max(1, budget ?? 0, ...data.map((d) => d.total));
  const scale = (HEIGHT - TOP) / max;
  const budgetY = budget === null ? null : HEIGHT - budget * scale;

  return (
    <figure className={styles.chart} data-testid="spend-chart">
      <svg
        className={styles.chartSvg}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <line className={styles.baseline} x1={0} x2={width} y1={HEIGHT - 0.5} y2={HEIGHT - 0.5} />
        {data.map((d, i) => {
          const h = d.total > 0 ? Math.max(1, d.total * scale) : 0;
          // Index 0 (oldest) is the rightmost column.
          const x = (n - 1 - i) * COL + (COL - BAR) / 2;
          return (
            <rect
              key={d.month}
              className={d.month === highlight ? styles.barNow : styles.bar}
              x={x}
              y={HEIGHT - h}
              width={BAR}
              height={h}
              data-testid="spend-bar"
              data-month={d.month}
            />
          );
        })}
        {budgetY !== null ? (
          <line
            className={styles.budgetLine}
            x1={0}
            x2={width}
            y1={budgetY}
            y2={budgetY}
            data-testid="budget-line"
          />
        ) : null}
      </svg>
      <div className={styles.axis} aria-hidden="true">
        {data.map((d) => (
          <span key={d.month}>{monthName(d.month, "short")}</span>
        ))}
      </div>
      {budget !== null ? (
        <figcaption className={styles.legend}>
          <span className={styles.swatchLine} aria-hidden="true" /> התקציב החודשי
        </figcaption>
      ) : null}
      <table className={styles.table}>
        <caption className={styles.tableCaption}>הוצאה לפי חודש, לפי המחירים שהוצגו</caption>
        <thead>
          <tr>
            <th scope="col">חודש</th>
            <th scope="col">סכום</th>
          </tr>
        </thead>
        <tbody>
          {[...data].reverse().map((d) => (
            <tr key={d.month}>
              <th scope="row">{monthName(d.month)}</th>
              <td>
                <Price amount={d.total} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
