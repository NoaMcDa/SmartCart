"use client";

import { useId, type ReactNode } from "react";
import styles from "./Switch.module.css";

export type SwitchProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Visible label. The whole row is the 44 px target. */
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  className?: string;
};

/** On/off switch (role="switch"), e.g. "remember this for all milk". */
export function Switch({
  checked,
  onChange,
  label,
  description,
  disabled,
  className,
}: SwitchProps) {
  const id = useId();
  return (
    <div className={[styles.row, className].filter(Boolean).join(" ")}>
      <span className={styles.text}>
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
        {description ? (
          <span className={styles.description} id={`${id}-desc`}>
            {description}
          </span>
        ) : null}
      </span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${id}-desc` : undefined}
        disabled={disabled}
        className={styles.switch}
        onClick={() => onChange(!checked)}
      >
        <span className={styles.thumb} />
      </button>
    </div>
  );
}

/** Alias: the design docs call it a toggle. */
export const Toggle = Switch;
