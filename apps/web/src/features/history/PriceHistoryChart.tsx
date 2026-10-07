"use client";

import { useId, useState } from "react";
import type { PriceHistoryResponse } from "@/api/client";
import { Price } from "@/components/ui/Price";
import { formatPrice } from "@/lib/format";
import {
  findGaps,
  formatDay,
  inWindow,
  linear,
  money,
  promoRanges,
  seriesOf,
  splitSegments,
  summarize,
  valueDomain,
  windowOf,
  type Metric,
  type SeriesPoint,
} from "./series";
import styles from "./History.module.css";

const W = 640;
const H = 240;
const X0 = 26; // plot's physical left edge (the newest day: time runs in reading direction)
const X1 = W - 54; // plot's physical right edge (the oldest day); the price axis sits beyond it
const Y0 = 14;
const Y1 = H - 30;

export type PriceHistoryChartProps = {
  history: PriceHistoryResponse;
  days: number;
  metric: Metric;
  /** "ל-100 מ"ל", 'לק"ג', "ליחידה": what the numbers are per. */
  unitLabel: string;
};

/**
 * 90-day price line, no chart library. Time runs in reading direction (the oldest day at the
 * start side, which is the right in Hebrew), the price axis is at the start side, and every number
 * is a left-to-right island. Promo windows are shaded, days with no data are hatched and cut the
 * line (never interpolated), promo days carry a marker with a Hebrew tooltip. The picture is
 * decorative to assistive technology; the same numbers are in the hidden table, and the summary
 * sentence says what the chart shows.
 */
export function PriceHistoryChart({ history, days, metric, unitLabel }: PriceHistoryChartProps) {
  const uid = useId().replace(/:/g, "");
  const [active, setActive] = useState<SeriesPoint | null>(null);

  const win = windowOf(history, days);
  const points = inWindow(seriesOf(history, metric), win);
  const promos = promoRanges(history.promos, win);
  const gaps = findGaps(points, win);
  const segments = splitSegments(points);
  const summary = summarize(points, promos, gaps);
  const { lo, hi } = valueDomain(points);

  const x = linear([win.start, win.end], [X1, X0]);
  const y = linear([lo, hi], [Y1, Y0]);
  const yTicks = [lo + (hi - lo) * 0.1, lo + (hi - lo) / 2, hi - (hi - lo) * 0.1];
  const xTicks = [win.start, (win.start + win.end) / 2, win.end];
  const promoPoints = points.filter((p) => p.promo);
  const last = points[points.length - 1] ?? null;
  const axisName = metric === "unit" ? "מחיר ליחידה" : "מחיר מדף";

  const describe = (p: SeriesPoint) =>
    `${formatDay(p.t)}: ${formatPrice(p.value, 2)}${metric === "unit" ? ` ${unitLabel}` : ""}${p.promo ? `. מבצע: ${p.promo}` : ""}`;

  if (points.length === 0) {
    return (
      <p className={styles.empty} data-testid="history-empty">
        אין עדיין נתוני מחיר לתקופה הזו. ההיסטוריה מתחילה מהיום שבו התחלנו לאסוף מחירים, ואין השלמה
        של ימים קודמים.
      </p>
    );
  }

  return (
    <div className={styles.chart} data-testid="history-chart">
      <p className={styles.axisName}>
        {axisName}
        {metric === "unit" ? <> ({unitLabel})</> : null}, בשקלים
      </p>
      <svg
        className={styles.svg}
        viewBox={`0 0 ${W} ${H}`}
        aria-hidden="true"
        focusable="false"
        onPointerLeave={() => setActive(null)}
      >
        <defs>
          <pattern
            id={`${uid}-hatch`}
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="6" className={styles.hatch} />
          </pattern>
        </defs>

        {yTicks.map((v) => (
          <g key={v}>
            <line x1={X0} x2={X1} y1={y(v)} y2={y(v)} className={styles.grid} />
            <text x={W - 8} y={y(v) + 4} textAnchor="end" className={styles.tick}>
              {money(v)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={H - 8} textAnchor="middle" className={styles.tick}>
            {formatDay(t)}
          </text>
        ))}

        {gaps.map((g) => (
          <rect
            key={`gap-${g.from}`}
            data-testid="history-gap"
            x={x(g.to)}
            y={Y0}
            width={Math.max(2, x(g.from) - x(g.to))}
            height={Y1 - Y0}
            fill={`url(#${uid}-hatch)`}
            className={styles.gapBand}
          />
        ))}
        {promos.map((p) => (
          <rect
            key={`promo-${p.from}`}
            data-testid="history-promo"
            x={x(p.to)}
            y={Y0}
            width={Math.max(4, x(p.from) - x(p.to))}
            height={Y1 - Y0}
            className={styles.promoBand}
          />
        ))}

        {segments.map((seg) =>
          seg.length === 1 ? (
            <circle
              key={seg[0]!.t}
              cx={x(seg[0]!.t)}
              cy={y(seg[0]!.value)}
              r={3}
              className={styles.dot}
            />
          ) : (
            <polyline
              key={seg[0]!.t}
              className={styles.line}
              points={seg.map((p) => `${x(p.t).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ")}
            />
          ),
        )}

        {promoPoints.map((p) => (
          <circle
            key={p.t}
            data-testid="history-marker"
            cx={x(p.t)}
            cy={y(p.value)}
            r={active?.t === p.t ? 7 : 5}
            className={styles.marker}
            onPointerEnter={() => setActive(p)}
            onClick={() => setActive(p)}
          >
            <title>{describe(p)}</title>
          </circle>
        ))}
        {last ? (
          <circle cx={x(last.t)} cy={y(last.value)} r={4.5} className={styles.latest} />
        ) : null}
      </svg>

      <ul className={styles.legend} aria-label="מקרא">
        <li>
          <span className={`${styles.swatch} ${styles.swatchLine}`} aria-hidden="true" /> מחיר
        </li>
        <li>
          <span className={`${styles.swatch} ${styles.swatchPromo}`} aria-hidden="true" /> תקופת
          מבצע
        </li>
        <li>
          <span className={`${styles.swatch} ${styles.swatchMarker}`} aria-hidden="true" /> יום מבצע
          (נקודה)
        </li>
        <li>
          <span className={`${styles.swatch} ${styles.swatchGap}`} aria-hidden="true" /> אין נתונים
        </li>
      </ul>

      <p className={styles.tooltip} role="status" data-testid="history-tooltip">
        {active ? describe(active) : "הצביעי על נקודת מבצע כדי לראות את פרטיה."}
      </p>

      {summary ? (
        <p className={styles.summary} data-testid="history-summary">
          ב-{days} הימים האחרונים המחיר ({axisName}) נע בין{" "}
          <Price amount={summary.min} fractionDigits={2} /> ל-
          <Price amount={summary.max} fractionDigits={2} />, והמחיר האחרון הוא{" "}
          <Price amount={summary.latest} fractionDigits={2} />.{" "}
          {promos.length > 0
            ? `היו ${promos.length} תקופות מבצע (כ-${summary.promoDays} ימים). `
            : "לא היו תקופות מבצע. "}
          {gaps.length > 0
            ? `ב-${summary.gapDays} ימים אין נתונים, והם מסומנים כרווח בלי קו.`
            : "אין ימים חסרים."}
        </p>
      ) : null}
      <p className={styles.note}>
        ימים ללא נתונים מוצגים כרווח מקוקו ולא כקו ישר: לא ממלאים מחיר שלא ראינו.
      </p>

      {promos.length > 0 ? (
        <ul className={styles.promoList} aria-label="תקופות מבצע">
          {promos.map((p) => (
            <li key={p.from}>
              <span dir="ltr">
                {formatDay(p.from)}–{formatDay(p.to)}
              </span>
              : {p.description}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="sr-only">
        <table data-testid="history-table">
          <caption>נתוני המחיר לפי תאריך, מהישן לחדש</caption>
          <thead>
            <tr>
              <th scope="col">תאריך</th>
              <th scope="col">{axisName}</th>
              <th scope="col">מבצע</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.t}>
                <th scope="row">{formatDay(p.t)}</th>
                <td>{formatPrice(p.value, 2)}</td>
                <td>{p.promo ?? "אין"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
