"use client";

import { useId, useState } from "react";
import type { FlexLevel } from "@/api/client";
import { BottomSheet, Button, CheckChip, FLEX_LEVELS, Switch } from "@/components/ui";
import { flexLevelLabel } from "@/components/ui/Chip";
import { reportFlexChanged } from "@/features/consent/betaEvents";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { listMessages } from "@/i18n/messages/list";
import { productName } from "@/lib/format";
import { levelCopy, lookupDefault, rememberLabel, softAttributes } from "@/state/flex";
import { listActions, type ListItem } from "@/state/list";
import styles from "./FlexibilitySheet.module.css";

const ORDER: FlexLevel[] = ["exact", "any_brand", "close"];

export type FlexibilitySheetProps = {
  item: ListItem | null;
  flexDefaults: Record<string, FlexLevel>;
  onClose: () => void;
};

/**
 * Flexibility sheet (issue #31): how strict matching is for one item. Three radio options with a
 * one-line explanation and an example, soft attributes to allow, and "remember for all <category>"
 * which writes the category default (flex_defaults by taxonomy id). Cancel discards.
 */
export function FlexibilitySheet({ item, flexDefaults, onClose }: FlexibilitySheetProps) {
  const t = useT(listMessages);
  const { locale } = useLocale();
  return (
    <BottomSheet
      open={item !== null}
      onClose={onClose}
      eyebrow={t("sheetEyebrow")}
      title={item?.canonical ? productName(item.canonical, locale) : (item?.inputText ?? "")}
      className={styles.sheet}
    >
      {item ? (
        <SheetBody key={item.id} item={item} flexDefaults={flexDefaults} onClose={onClose} />
      ) : null}
    </BottomSheet>
  );
}

function SheetBody({
  item,
  flexDefaults,
  onClose,
}: {
  item: ListItem;
  flexDefaults: Record<string, FlexLevel>;
  onClose: () => void;
}) {
  const t = useT(listMessages);
  const { locale } = useLocale();
  const taxonomy = item.canonical?.taxonomy_id ?? null;
  const [level, setLevel] = useState<FlexLevel>(item.flexLevel);
  const [allow, setAllow] = useState<string[]>(item.allow);
  const [remember, setRemember] = useState<boolean>(
    taxonomy ? flexDefaults[taxonomy] === item.flexLevel : false,
  );
  const groupId = useId();
  const attrs = softAttributes(taxonomy, locale);
  const inherited = taxonomy ? lookupDefault(taxonomy, flexDefaults) : undefined;

  function save() {
    listActions.setFlex(item.id, { level, allow, remember: remember && taxonomy !== null });
    if (level !== item.flexLevel) reportFlexChanged(level);
    onClose();
  }

  return (
    <>
      <fieldset className={styles.options}>
        <legend className="sr-only">{t("sheetLegend")}</legend>
        {ORDER.map((value) => {
          const { tone, Icon } = FLEX_LEVELS[value];
          const label = flexLevelLabel(value, locale);
          const copy = levelCopy(taxonomy, value, locale);
          const id = `${groupId}-${value}`;
          return (
            <label
              key={value}
              htmlFor={id}
              className={[styles.option, level === value ? styles.selected : null]
                .filter(Boolean)
                .join(" ")}
            >
              <input
                id={id}
                type="radio"
                name={`${groupId}-flex`}
                value={value}
                checked={level === value}
                onChange={() => setLevel(value)}
                className={styles.radio}
                aria-describedby={`${id}-desc`}
              />
              <span className={styles.optionText}>
                <span className={[styles.optionLabel, styles[`tone-${tone}`]].join(" ")}>
                  <Icon size={16} />
                  {label}
                </span>
                <span id={`${id}-desc`} className={styles.explanation}>
                  {copy.explanation} <span className={styles.example}>{copy.example}</span>
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>

      {level !== "exact" ? (
        <fieldset className={styles.soft}>
          <legend className={styles.softTitle}>{t("allowLegend")}</legend>
          <div className={styles.softList}>
            {attrs.map((a) => (
              <CheckChip
                key={a.key}
                checked={allow.includes(a.key)}
                onChange={(on) =>
                  setAllow((prev) => (on ? [...prev, a.key] : prev.filter((k) => k !== a.key)))
                }
              >
                {a.label}
              </CheckChip>
            ))}
          </div>
        </fieldset>
      ) : null}

      {taxonomy ? (
        <Switch
          checked={remember}
          onChange={setRemember}
          label={rememberLabel(item.canonical, locale)}
          description={
            inherited && !remember
              ? t("categoryDefault", { level: flexLevelLabel(inherited, locale) })
              : t("appliesTo")
          }
        />
      ) : null}

      <div className={styles.footer}>
        <Button onClick={save} className={styles.save}>
          {t("save")}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          {t("cancel")}
        </Button>
      </div>
    </>
  );
}
