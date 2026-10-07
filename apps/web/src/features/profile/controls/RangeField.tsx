"use client";

import { useId, type ReactNode } from "react";
import styles from "./controls.module.css";

export type RangeFieldProps = {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
  /** Visible value, e.g. a Price or "5 ק"מ". Wrap numbers in dir="ltr" yourself or use `unit`. */
  display: ReactNode;
  /** Spoken value for screen readers ("5 קילומטרים"). */
  valueText: string;
  minLabel: ReactNode;
  maxLabel: ReactNode;
};

/**
 * Labelled native range input. Native sliders are keyboard operable (arrows, Home, End), flip
 * with the document direction, and announce `aria-valuetext`. The 44 px target is the input height.
 */
export function RangeField({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  display,
  valueText,
  minLabel,
  maxLabel,
}: RangeFieldProps) {
  const id = useId();
  return (
    <div className={styles.field}>
      <div className={styles.sliderHead}>
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
        <output htmlFor={id} className={styles.sliderValue}>
          {display}
        </output>
      </div>
      <input
        id={id}
        type="range"
        className={styles.slider}
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={valueText}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className={styles.sliderScale} aria-hidden="true">
        <span>{minLabel}</span>
        <span>{maxLabel}</span>
      </div>
    </div>
  );
}
