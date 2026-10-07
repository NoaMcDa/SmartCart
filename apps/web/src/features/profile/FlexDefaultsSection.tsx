"use client";

import { useId } from "react";
import type { FlexLevel } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { FLEX_LEVELS } from "@/components/ui/Chip";
import styles from "./controls/controls.module.css";
import profileStyles from "./Profile.module.css";
import { DEPARTMENTS, categoryLabel, smartDefault } from "./dietOptions";
import { listActions, useFlexDefaults } from "@/state/list";

const LEVELS: ReadonlyArray<FlexLevel> = ["exact", "any_brand", "close"];

/**
 * Per-category flexibility defaults (D4). Shows every department with its smart default
 * (staples "any brand", cosmetics and personal care "exact"), plus any finer category saved from
 * the list builder by "remember this for all milk". Only changes are stored; reset empties them.
 */
export function FlexDefaultsSection() {
  const overrides = useFlexDefaults();
  const departmentIds = new Set(DEPARTMENTS.map((d) => d.id));
  const extra = Object.keys(overrides).filter((k) => !departmentIds.has(k));
  const rows = [
    ...extra.map((id) => ({ id, label: categoryLabel(id) })),
    ...DEPARTMENTS.map((d) => ({ id: d.id, label: d.label })),
  ];
  const changed = Object.keys(overrides).length;
  return (
    <div className={styles.stack}>
      <p className={styles.hint}>
        הרמה שנבחרת אוטומטית לכל מוצר חדש בקטגוריה. תמיד אפשר לשנות פריט בודד ברשימה.
      </p>
      <ul className={profileStyles.flexList} data-testid="flex-defaults">
        {rows.map((row) => (
          <FlexRow
            key={row.id}
            id={row.id}
            label={row.label}
            value={overrides[row.id] ?? smartDefault(row.id)}
            isOverride={row.id in overrides}
          />
        ))}
      </ul>
      <div className={profileStyles.actions}>
        <Button
          variant="outline"
          size="sm"
          disabled={changed === 0}
          onClick={() => {
            for (const id of Object.keys(overrides)) listActions.setFlexDefault(id, null);
          }}
        >
          איפוס לברירות המחדל החכמות
        </Button>
        <span className={styles.status} role="status">
          {changed === 0 ? "כל הקטגוריות על ברירת המחדל." : `${changed} קטגוריות שונו.`}
        </span>
      </div>
    </div>
  );
}

function FlexRow({
  id,
  label,
  value,
  isOverride,
}: {
  id: string;
  label: string;
  value: FlexLevel;
  isOverride: boolean;
}) {
  const selectId = useId();
  return (
    <li className={profileStyles.flexRow}>
      <label htmlFor={selectId} className={profileStyles.flexLabel}>
        {label}
        {isOverride ? <span className={profileStyles.changed}> · שונה</span> : null}
      </label>
      <select
        id={selectId}
        className={`${styles.input} ${profileStyles.flexSelect}`}
        value={value}
        onChange={(e) => {
          const level = e.target.value as FlexLevel;
          listActions.setFlexDefault(id, level === smartDefault(id) ? null : level);
        }}
      >
        {LEVELS.map((l) => (
          <option key={l} value={l}>
            {FLEX_LEVELS[l].label}
          </option>
        ))}
      </select>
    </li>
  );
}
