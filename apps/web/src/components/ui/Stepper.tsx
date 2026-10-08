"use client";

import { useT } from "@/i18n/LocaleProvider";
import { uiMessages } from "@/i18n/messages/ui";
import { IconMinus, IconPlus } from "./icons";
import styles from "./Stepper.module.css";

export type StepperProps = {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  /** Item name, used in the accessible group label ("כמות: חלב טרי 3%"). */
  label: string;
  /** Unit suffix shown after the number for weighed goods, e.g. 'ק"ג'. */
  unit?: string;
  className?: string;
};

function round(n: number) {
  return Math.round(n * 1000) / 1000;
}

/** Quantity stepper with 44 px targets and Hebrew labels. The value is an LTR island. */
export function Stepper({
  value,
  onChange,
  min = 0,
  max = 99,
  step = 1,
  label,
  unit,
  className,
}: StepperProps) {
  const t = useT(uiMessages);
  const dec = () => onChange(Math.max(min, round(value - step)));
  const inc = () => onChange(Math.min(max, round(value + step)));
  return (
    <div
      role="group"
      aria-label={t("stepperGroup", { label })}
      className={[styles.stepper, className].filter(Boolean).join(" ")}
    >
      <button
        type="button"
        className={styles.btn}
        onClick={dec}
        disabled={value <= min}
        aria-label={t("stepperDecrease", { label })}
      >
        <IconMinus size={16} />
      </button>
      <output
        className={styles.value}
        aria-live="polite"
        aria-label={t("stepperValue", { value: `${value}${unit ? ` ${unit}` : ""}` })}
      >
        <span dir="ltr">{value}</span>
        {unit ? <span className={styles.unit}>{unit}</span> : null}
      </output>
      <button
        type="button"
        className={styles.btn}
        onClick={inc}
        disabled={value >= max}
        aria-label={t("stepperIncrease", { label })}
      >
        <IconPlus size={16} />
      </button>
    </div>
  );
}
