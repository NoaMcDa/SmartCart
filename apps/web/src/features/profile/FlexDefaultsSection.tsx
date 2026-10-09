"use client";

import { useId } from "react";
import type { FlexLevel } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { flexLevelLabel } from "@/components/ui/Chip";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import styles from "./controls/controls.module.css";
import profileStyles from "./Profile.module.css";
import { DEPARTMENTS, categoryLabel, departmentLabel, smartDefault } from "./dietOptions";
import { listActions, useFlexDefaults } from "@/state/list";

const LEVELS: ReadonlyArray<FlexLevel> = ["exact", "any_brand", "close"];

/**
 * Per-category flexibility defaults (D4). Shows every department with its smart default
 * (staples "any brand", cosmetics and personal care "exact"), plus any finer category saved from
 * the list builder by "remember this for all milk". Only changes are stored; reset empties them.
 */
export function FlexDefaultsSection() {
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const overrides = useFlexDefaults();
  const departmentIds = new Set(DEPARTMENTS.map((d) => d.id));
  const extra = Object.keys(overrides).filter((k) => !departmentIds.has(k));
  const rows = [
    ...extra.map((id) => ({ id, label: categoryLabel(id, locale) })),
    ...DEPARTMENTS.map((d) => ({ id: d.id, label: departmentLabel(d.id, locale) })),
  ];
  const changed = Object.keys(overrides).length;
  return (
    <div className={styles.stack}>
      <p className={styles.hint}>{t("flexHint")}</p>
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
          {t("flexReset")}
        </Button>
        <span className={styles.status} role="status">
          {changed === 0 ? t("flexAllDefault") : t("flexChangedCount", { count: changed })}
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
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const selectId = useId();
  return (
    <li className={profileStyles.flexRow}>
      <label htmlFor={selectId} className={profileStyles.flexLabel}>
        {label}
        {isOverride ? <span className={profileStyles.changed}>{t("flexChangedMark")}</span> : null}
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
            {flexLevelLabel(l, locale)}
          </option>
        ))}
      </select>
    </li>
  );
}
