"use client";

import { Price } from "@/components/ui/Price";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import {
  EXTRA_STOP_MAX,
  EXTRA_STOP_MIN,
  updateProfile,
  useProfile,
  type TravelMode,
} from "../profileState";
import { RangeField } from "./RangeField";
import styles from "./controls.module.css";

const MODES = [
  { value: "car", labelKey: "modeCar" },
  { value: "walk_transit", labelKey: "modeWalkTransit" },
  { value: "delivery", labelKey: "modeDelivery" },
] as const satisfies ReadonlyArray<{
  value: TravelMode;
  labelKey: "modeCar" | "modeWalkTransit" | "modeDelivery";
}>;

/** "איך את עושה קניות?" plus the value of an extra stop (0 to 50 ILS). */
export function TravelControls() {
  const t = useT(profileMessages);
  const profile = useProfile();
  return (
    <div className={styles.stack}>
      <div className={styles.group}>
        <p className={styles.legend}>{t("howShop")}</p>
        <SegmentedControl<TravelMode>
          label={t("travelModeLabel")}
          options={MODES.map(({ value, labelKey }) => ({ value, label: t(labelKey) }))}
          value={profile.travelMode}
          onChange={(travelMode) => updateProfile({ travelMode })}
        />
      </div>
      <RangeField
        label={t("extraStop")}
        min={EXTRA_STOP_MIN}
        max={EXTRA_STOP_MAX}
        step={1}
        value={profile.extraStopValue}
        onChange={(extraStopValue) => updateProfile({ extraStopValue })}
        display={<Price amount={profile.extraStopValue} fractionDigits={0} />}
        valueText={t("extraStopSpoken", { n: profile.extraStopValue })}
        minLabel={<Price amount={EXTRA_STOP_MIN} fractionDigits={0} />}
        maxLabel={<Price amount={EXTRA_STOP_MAX} fractionDigits={0} />}
      />
      <p className={styles.hint}>{t("splitHint")}</p>
    </div>
  );
}
