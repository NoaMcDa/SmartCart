"use client";

import { Chip } from "@/components/ui/Chip";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import { Tag } from "@/components/ui/Tag";
import styles from "./controls/controls.module.css";
import { ALLERGENS, KOSHER_OPTIONS } from "./dietOptions";
import { updateProfile, useProfile, type KosherLevel } from "./profileState";

/**
 * Diet, kosher and allergen preferences. Matching on these relies on attributes extracted from
 * product data, which are not verified by a person unless a store's item says so; the amber
 * "לא מאומת" note says so wherever they could influence a match (principle 3, D10).
 */
export function DietSection() {
  const profile = useProfile();
  const kosher: KosherLevel | "none" = profile.diet.kosherLevel ?? "none";
  return (
    <div className={styles.stack}>
      <div className={styles.statusRow}>
        <Tag variant="unverified">לא מאומת</Tag>
        <p className={styles.hint}>
          ההתאמה לפי כשרות, תזונה ואלרגנים נשענת על מידע שחולץ אוטומטית מנתוני המוצרים, ולא תמיד
          נבדק על ידי אדם. בדקי את האריזה לפני שקונים, ובמיוחד כשיש אלרגיה.
        </p>
      </div>

      <div className={styles.group}>
        <p className={styles.legend}>רמת כשרות</p>
        <SegmentedControl<KosherLevel | "none">
          label="רמת כשרות"
          options={KOSHER_OPTIONS.map((o) => ({
            value: o.value,
            label: o.value === "none" ? "ללא" : o.label,
          }))}
          value={kosher}
          onChange={(v) =>
            updateProfile((p) => ({ diet: { ...p.diet, kosherLevel: v === "none" ? null : v } }))
          }
        />
      </div>

      <Switch
        label="טבעוני"
        checked={profile.diet.vegan}
        onChange={(vegan) => updateProfile((p) => ({ diet: { ...p.diet, vegan } }))}
      />
      <Switch
        label="ללא גלוטן"
        checked={profile.diet.glutenFree}
        onChange={(glutenFree) => updateProfile((p) => ({ diet: { ...p.diet, glutenFree } }))}
      />

      <div className={styles.group} role="group" aria-labelledby="allergens-legend">
        <p id="allergens-legend" className={styles.legend}>
          אלרגנים להימנע מהם
        </p>
        <div className={styles.chips}>
          {ALLERGENS.map((a) => {
            const selected = profile.diet.allergens.includes(a.key);
            return (
              <Chip
                key={a.key}
                selected={selected}
                tone={selected ? "accent" : "neutral"}
                onClick={() =>
                  updateProfile((p) => ({
                    diet: {
                      ...p.diet,
                      allergens: selected
                        ? p.diet.allergens.filter((k) => k !== a.key)
                        : [...p.diet.allergens, a.key],
                    },
                  }))
                }
              >
                {a.label}
              </Chip>
            );
          })}
        </div>
      </div>
    </div>
  );
}
