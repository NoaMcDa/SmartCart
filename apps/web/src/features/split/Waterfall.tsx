import { Price } from "@/components/ui/Price";
import { IconCheck } from "@/components/ui/icons";
import { useT } from "@/i18n/LocaleProvider";
import { splitMessages } from "@/i18n/messages/split";
import type { Waterfall as WaterfallData } from "./savings";
import styles from "./Split.module.css";

type Step = {
  key: string;
  label: string;
  value: number;
  /** "cost" steps are neutral; "saving" steps are green only when positive (D7 color rules). */
  kind: "saving" | "cost";
};

/** Signed value in one LTR island: "+₪ 12" or "−₪ 9". */
function Signed({ value }: { value: number }) {
  const sign = value > 0 ? "+" : "";
  return (
    <span dir="ltr" className={styles.signed}>
      {sign}
      <Price amount={value} fractionDigits="auto" />
    </span>
  );
}

/**
 * Where the net saving comes from, versus the user's own store (D7): the home store's price is
 * the starting point, then chain switch, brand swaps and promos (savings), then travel and the
 * extra stop (costs). The steps sum exactly to the net saving, which is the last row. Every step
 * is text and a number; the bars are decorative and green appears only on positive savings.
 */
export function Waterfall({ data, homeName }: { data: WaterfallData; homeName: string }) {
  const t = useT(splitMessages);
  const steps: Step[] = [
    { key: "chain", label: t("wfChain"), value: data.chainSwitch, kind: "saving" },
    { key: "brand", label: t("wfBrand"), value: data.brandSwaps, kind: "saving" },
    { key: "promo", label: t("wfPromos"), value: data.promos, kind: "saving" },
    { key: "travel", label: t("wfTravel"), value: -data.travel, kind: "cost" },
    ...(data.extraStop > 0
      ? [{ key: "stop", label: t("wfExtraStop"), value: -data.extraStop, kind: "cost" } as Step]
      : []),
  ];
  const scale = Math.max(1, ...steps.map((s) => Math.abs(s.value)), Math.abs(data.net));
  return (
    <section
      aria-labelledby="waterfall-heading"
      className={styles.waterfall}
      data-testid="waterfall"
    >
      <h2 id="waterfall-heading" className={styles.sectionTitle}>
        {t("wfHeading")}
      </h2>
      <ol className={styles.steps}>
        <li className={styles.step} data-step="base">
          <span className={styles.stepLabel}>{t("wfBase", { home: homeName })}</span>
          <span className={styles.stepValue}>
            <Price amount={data.base} />
          </span>
        </li>
        {steps.map((s) => (
          <li key={s.key} className={styles.step} data-step={s.key}>
            <span className={styles.stepLabel}>{s.label}</span>
            <span className={styles.bar} aria-hidden="true">
              <span
                className={styles.barFill}
                data-tone={s.value > 0 && s.kind === "saving" ? "good" : "neutral"}
                style={{ inlineSize: `${(Math.abs(s.value) / scale) * 100}%` }}
              />
            </span>
            <span className={styles.stepValue}>
              <Signed value={s.value} />
            </span>
          </li>
        ))}
        <li className={`${styles.step} ${styles.net}`} data-step="net">
          <span className={styles.stepLabel}>
            {data.net > 0 ? <IconCheck size={15} /> : null} {t("wfNet")}
          </span>
          <span className={styles.stepValue}>
            <Price amount={data.net} size="lg" tone={data.net > 0 ? "good" : "default"} />
          </span>
        </li>
      </ol>
    </section>
  );
}
