"use client";

import { Price } from "@/components/ui/Price";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
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
  { value: "car", label: "רכב" },
  { value: "walk_transit", label: "הליכה או תחבורה" },
  { value: "delivery", label: "משלוח" },
] as const satisfies ReadonlyArray<{ value: TravelMode; label: string }>;

/** "איך את עושה קניות?" plus the value of an extra stop (0 to 50 ILS). */
export function TravelControls() {
  const profile = useProfile();
  return (
    <div className={styles.stack}>
      <div className={styles.group}>
        <p className={styles.legend}>איך את עושה קניות?</p>
        <SegmentedControl<TravelMode>
          label="אמצעי הגעה"
          options={MODES}
          value={profile.travelMode}
          onChange={(travelMode) => updateProfile({ travelMode })}
        />
      </div>
      <RangeField
        label="כמה שווה לך עצירה נוספת?"
        min={EXTRA_STOP_MIN}
        max={EXTRA_STOP_MAX}
        step={1}
        value={profile.extraStopValue}
        onChange={(extraStopValue) => updateProfile({ extraStopValue })}
        display={<Price amount={profile.extraStopValue} fractionDigits={0} />}
        valueText={`${profile.extraStopValue} שקלים`}
        minLabel={<Price amount={EXTRA_STOP_MIN} fractionDigits={0} />}
        maxLabel={<Price amount={EXTRA_STOP_MAX} fractionDigits={0} />}
      />
      <p className={styles.hint}>
        פיצול הקנייה בין שתי חנויות יוצג רק אם החיסכון נטו, אחרי נסיעה ואחרי השווי הזה, שווה את זה.
      </p>
    </div>
  );
}
