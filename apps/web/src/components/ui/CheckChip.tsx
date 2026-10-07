"use client";

import type { ReactNode } from "react";
import styles from "./CheckChip.module.css";

export type CheckChipProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
};

/**
 * Pill checkbox (flexibility sheet "allow" options). A native checkbox inside its label, so it
 * reads as a checkbox to screen readers; the whole pill is the 44 px target.
 */
export function CheckChip({ checked, onChange, children, disabled, className }: CheckChipProps) {
  return (
    <label
      className={[styles.chip, checked ? styles.checked : null, className]
        .filter(Boolean)
        .join(" ")}
    >
      <input
        type="checkbox"
        className={styles.input}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{children}</span>
    </label>
  );
}
