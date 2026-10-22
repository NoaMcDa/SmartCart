"use client";

import { useId } from "react";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import controls from "@/features/profile/controls/controls.module.css";
import { updateProfile, useProfile } from "@/features/profile/profileState";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { kosherMessages } from "@/i18n/messages/kosher";
import {
  GENERAL_LEVELS,
  SPECIFIC_LEVELS,
  generalLevelOf,
  isKosherLevel,
  isSpecificLevel,
  levelLabel,
  type KosherLevel,
} from "./kosher";

type Segment = "none" | (typeof GENERAL_LEVELS)[number];

/**
 * The kosher setting (Profile, and onboarding for the kosher beta segment): a level, optionally one
 * named hechsher, "only items whose name states it", and kosher for Passover as a filter of its
 * own. The level is what the API's `kosher.level` filters by; see docs/matching.md, "Kosher".
 * The profile stores it locally and mirrors it to the shopper context every request reads.
 */
export function KosherControls() {
  const t = useT(kosherMessages);
  const { locale } = useLocale();
  const { diet } = useProfile();
  const selectId = useId();
  const level = diet.kosherLevel;
  const segment: Segment = level ? generalLevelOf(level) : "none";
  const set = (next: Partial<typeof diet>) =>
    updateProfile((p) => ({ diet: { ...p.diet, ...next } }));
  const active = level !== null || diet.kosherPassover;

  return (
    <div className={controls.stack} data-testid="kosher-controls">
      <div className={controls.group}>
        <p className={controls.legend}>{t("levelLegend")}</p>
        <SegmentedControl<Segment>
          label={t("levelLegend")}
          options={[
            { value: "none", label: t("levelNone") },
            ...GENERAL_LEVELS.map((l) => ({ value: l, label: levelLabel(l, locale) })),
          ]}
          value={segment}
          onChange={(v) => set({ kosherLevel: v === "none" ? null : v })}
        />
      </div>

      {level ? (
        <div className={controls.field}>
          <label htmlFor={selectId} className={controls.label}>
            {t("specificLabel")}
          </label>
          <select
            id={selectId}
            className={controls.input}
            value={isSpecificLevel(level) ? level : ""}
            onChange={(e) => {
              const v = e.target.value;
              set({ kosherLevel: isKosherLevel(v) ? (v as KosherLevel) : generalLevelOf(level) });
            }}
          >
            <option value="">{t("specificAny")}</option>
            {SPECIFIC_LEVELS.map((l) => (
              <option key={l} value={l}>
                {levelLabel(l, locale)}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <Switch
        label={t("passover")}
        description={t("passoverHint")}
        checked={diet.kosherPassover}
        onChange={(kosherPassover) => set({ kosherPassover })}
      />

      {active ? (
        <Switch
          label={t("onlyStated")}
          description={t("onlyStatedHint")}
          checked={diet.kosherOnlyStated}
          onChange={(kosherOnlyStated) => set({ kosherOnlyStated })}
        />
      ) : null}

      <p className={controls.hint} data-testid="kosher-notice">
        {t("notice")}
      </p>
    </div>
  );
}
