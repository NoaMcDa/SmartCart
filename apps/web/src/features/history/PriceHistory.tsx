"use client";

import { useEffect, useId, useState } from "react";
import { priceHistory, type PriceHistoryResponse } from "@/api/client";
import { Card, SegmentedControl, Skeleton, UpdatedAt } from "@/components/ui";
import { useT } from "@/i18n/LocaleProvider";
import { historyMessages } from "@/i18n/messages/history";
import { PriceHistoryChart } from "./PriceHistoryChart";
import { seriesOf, type Metric } from "./series";
import styles from "./History.module.css";

export type HistoryStoreOption = {
  /** Store id, or null for the chain base price. */
  storeId: number | null;
  label: string;
};

type Range = "30" | "90";

type Loaded =
  { key: string; error: true } | { key: string; error?: false; history: PriceHistoryResponse };

/**
 * The "מחיר ב-90 הימים האחרונים" block on product detail (issue #28): store selector (my store,
 * cheapest nearby, chain base price), 30 or 90 days, unit price by default (D6) or shelf price,
 * the chart, the time of the last price and the checkout disclaimer.
 */
export function PriceHistory({
  canonicalId,
  stores,
  unitLabel,
}: {
  canonicalId: number;
  stores: ReadonlyArray<HistoryStoreOption>;
  unitLabel: string;
}) {
  const t = useT(historyMessages);
  const [range, setRange] = useState<Range>("90");
  const [metric, setMetric] = useState<Metric>("unit");
  const [choice, setChoice] = useState<string>("");
  const selectId = useId();

  const selected = stores.find((s) => optionValue(s) === choice) ?? stores[0] ?? null;
  const storeId = selected ? selected.storeId : null;
  const days = Number(range);
  const key = `${canonicalId}|${storeId ?? "base"}|${days}`;

  const [loaded, setLoaded] = useState<Loaded | null>(null);
  useEffect(() => {
    let cancelled = false;
    priceHistory(canonicalId, { storeId, days }).then(
      (history) => {
        if (!cancelled) setLoaded({ key, history });
      },
      () => {
        if (!cancelled) setLoaded({ key, error: true });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [canonicalId, storeId, days, key]);

  const current = loaded && loaded.key === key ? loaded : null;
  const history = current && !current.error ? current.history : null;
  const lastPoint = history ? seriesOf(history, "unit").at(-1) : undefined;
  const lastIso = lastPoint ? new Date(lastPoint.t).toISOString() : (history?.generated_at ?? null);

  return (
    <section
      aria-labelledby={`${selectId}-title`}
      className={styles.section}
      data-testid="price-history"
    >
      <div className={styles.head}>
        <h2 id={`${selectId}-title`} className={styles.title}>
          {t("title")}
        </h2>
        <div className={styles.controls}>
          <SegmentedControl<Range>
            label={t("rangeLabel")}
            value={range}
            onChange={setRange}
            options={[
              { value: "30", label: t("range30") },
              { value: "90", label: t("range90") },
            ]}
          />
          <SegmentedControl<Metric>
            label={t("metricLabel")}
            value={metric}
            onChange={setMetric}
            options={[
              { value: "unit", label: t("metricUnit") },
              { value: "shelf", label: t("metricShelf") },
            ]}
          />
        </div>
      </div>
      {stores.length > 1 ? (
        <div className={styles.controls}>
          <label htmlFor={selectId} className={styles.state}>
            {t("storeLabel")}
          </label>
          <select
            id={selectId}
            className={styles.select}
            value={selected ? optionValue(selected) : ""}
            onChange={(e) => setChoice(e.target.value)}
            data-testid="history-store"
          >
            {stores.map((s) => (
              <option key={optionValue(s)} value={optionValue(s)}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <Card>
        {!current ? (
          <div aria-busy="true" aria-label={t("loading")}>
            <Skeleton height={160} />
          </div>
        ) : current.error ? (
          <p role="alert" className={styles.state}>
            {t("loadError")}
          </p>
        ) : (
          <PriceHistoryChart
            history={current.history}
            days={days}
            metric={metric}
            unitLabel={unitLabel}
          />
        )}
      </Card>

      <p className={styles.footer}>
        <span>
          {lastIso ? <UpdatedAt iso={lastIso} prefix={t("lastUpdated")} withIcon /> : null}
        </span>
        <span>{t("checkoutGoverns")}</span>
      </p>
    </section>
  );
}

function optionValue(s: HistoryStoreOption): string {
  return s.storeId === null ? "base" : String(s.storeId);
}
