"use client";

import { Chip } from "@/components/ui/Chip";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import { Tag } from "@/components/ui/Tag";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import styles from "./controls/controls.module.css";
import { ALLERGENS, KOSHER_OPTIONS, allergenLabel, kosherLabel } from "./dietOptions";
import { updateProfile, useProfile, type KosherLevel } from "./profileState";

/**
 * Diet, kosher and allergen preferences. Matching on these relies on attributes extracted from
 * product data, which are not verified by a person unless a store's item says so; the amber
 * "לא מאומת" note says so wherever they could influence a match (principle 3, D10).
 */
export function DietSection() {
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const profile = useProfile();
  const kosher: KosherLevel | "none" = profile.diet.kosherLevel ?? "none";
  return (
    <div className={styles.stack}>
      <div className={styles.statusRow}>
        <Tag variant="unverified">{t("unverified")}</Tag>
        <p className={styles.hint}>{t("dietNotice")}</p>
      </div>

      <div className={styles.group}>
        <p className={styles.legend}>{t("kosherLegend")}</p>
        <SegmentedControl<KosherLevel | "none">
          label={t("kosherLegend")}
          options={KOSHER_OPTIONS.map((o) => ({
            value: o.value,
            label: o.value === "none" ? t("kosherNoneShort") : kosherLabel(o.value, locale),
          }))}
          value={kosher}
          onChange={(v) =>
            updateProfile((p) => ({ diet: { ...p.diet, kosherLevel: v === "none" ? null : v } }))
          }
        />
      </div>

      <Switch
        label={t("vegan")}
        checked={profile.diet.vegan}
        onChange={(vegan) => updateProfile((p) => ({ diet: { ...p.diet, vegan } }))}
      />
      <Switch
        label={t("glutenFree")}
        checked={profile.diet.glutenFree}
        onChange={(glutenFree) => updateProfile((p) => ({ diet: { ...p.diet, glutenFree } }))}
      />

      <div className={styles.group} role="group" aria-labelledby="allergens-legend">
        <p id="allergens-legend" className={styles.legend}>
          {t("allergensLegend")}
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
                {allergenLabel(a.key, locale)}
              </Chip>
            );
          })}
        </div>
      </div>
    </div>
  );
}
