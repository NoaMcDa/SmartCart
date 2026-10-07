"use client";

import { useId, useState } from "react";
import type { FlexLevel } from "@/api/client";
import { BottomSheet, Button, CheckChip, FLEX_LEVELS, Switch } from "@/components/ui";
import { reportFlexChanged } from "@/features/consent/betaEvents";
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
  return (
    <BottomSheet
      open={item !== null}
      onClose={onClose}
      eyebrow="רמת גמישות לפריט"
      title={item?.canonical?.display_name_he ?? item?.inputText ?? ""}
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
  const taxonomy = item.canonical?.taxonomy_id ?? null;
  const [level, setLevel] = useState<FlexLevel>(item.flexLevel);
  const [allow, setAllow] = useState<string[]>(item.allow);
  const [remember, setRemember] = useState<boolean>(
    taxonomy ? flexDefaults[taxonomy] === item.flexLevel : false,
  );
  const groupId = useId();
  const attrs = softAttributes(taxonomy);
  const inherited = taxonomy ? lookupDefault(taxonomy, flexDefaults) : undefined;

  function save() {
    listActions.setFlex(item.id, { level, allow, remember: remember && taxonomy !== null });
    if (level !== item.flexLevel) reportFlexChanged(level);
    onClose();
  }

  return (
    <>
      <fieldset className={styles.options}>
        <legend className="sr-only">רמת גמישות</legend>
        {ORDER.map((value) => {
          const { label, tone, Icon } = FLEX_LEVELS[value];
          const copy = levelCopy(taxonomy, value);
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
          <legend className={styles.softTitle}>אפשר לוותר על:</legend>
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
          label={rememberLabel(item.canonical)}
          description={
            inherited && !remember
              ? `ברירת המחדל לקטגוריה: ${FLEX_LEVELS[inherited].label}`
              : "חל על פריטים חדשים ועל הפריטים מהסוג הזה ברשימה. אפשר לשנות בפרופיל."
          }
        />
      ) : null}

      <div className={styles.footer}>
        <Button onClick={save} className={styles.save}>
          שמרי
        </Button>
        <Button variant="secondary" onClick={onClose}>
          ביטול
        </Button>
      </div>
    </>
  );
}
