"use client";

import { useId, useState } from "react";
import { FlexChip, IconClose, IconWarning, Stepper, Tag } from "@/components/ui";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { listMessages } from "@/i18n/messages/list";
import { productName } from "@/lib/format";
import { listActions, type ListItem } from "@/state/list";
import styles from "./ListBuilder.module.css";

export type ListRowProps = {
  item: ListItem;
  onOpenFlex: (id: string) => void;
};

/** One list row: name, flexibility chip, estimated tag, quantity stepper, remove; confirmation. */
export function ListRow({ item, onOpenFlex }: ListRowProps) {
  const t = useT(listMessages);
  const { locale } = useLocale();
  const name = item.canonical ? productName(item.canonical, locale) : item.inputText;
  const weighedKg = item.unit === "kg";
  return (
    <div
      className={styles.row}
      data-testid="list-row"
      data-canonical-id={item.canonical?.canonical_id}
      data-needs-confirmation={item.needsConfirmation ? "true" : undefined}
    >
      <div className={styles.rowLine}>
        <div className={styles.rowMain}>
          <div className={styles.rowName}>{name}</div>
          <div className={styles.rowMeta}>
            <FlexChip level={item.flexLevel} onClick={() => onOpenFlex(item.id)} />
            {item.isWeighed ? <Tag variant="estimated">{t("estimatedTag")}</Tag> : null}
          </div>
        </div>
        <Stepper
          value={item.quantity}
          onChange={(q) => listActions.setQuantity(item.id, q)}
          min={weighedKg ? 0.5 : 1}
          step={weighedKg ? 0.5 : 1}
          unit={weighedKg ? t("kg") : undefined}
          label={name}
          className={styles.stepper}
        />
        <button
          type="button"
          className={styles.iconButton}
          onClick={() => listActions.remove(item.id)}
          aria-label={t("removeAria", { name })}
        >
          <IconClose size={18} />
        </button>
      </div>
      {item.needsConfirmation ? <Confirmation item={item} /> : null}
    </div>
  );
}

function Confirmation({ item }: { item: ListItem }) {
  const t = useT(listMessages);
  const { locale } = useLocale();
  const [choosing, setChoosing] = useState(false);
  const listId = useId();
  const suggestion = productName(item.canonical, locale);
  const candidates = item.candidates.length
    ? item.candidates
    : item.canonical
      ? [item.canonical]
      : [];
  return (
    <div
      className={styles.confirm}
      role="group"
      aria-label={t("confirmGroup", { text: item.inputText })}
    >
      <div className={styles.confirmLine}>
        <IconWarning size={16} />
        <span className={styles.confirmText}>
          {t("confirmQuestion", { text: item.inputText, suggestion })}
        </span>
        <button
          type="button"
          className={styles.confirmYes}
          onClick={() => listActions.confirm(item.id)}
          aria-label={t("yesAria", { suggestion })}
        >
          {t("yes")}
        </button>
        <button
          type="button"
          className={styles.confirmOther}
          aria-expanded={choosing}
          aria-controls={listId}
          onClick={() => setChoosing((v) => !v)}
        >
          {t("chooseOther")}
        </button>
      </div>
      {choosing ? (
        <ul id={listId} className={styles.candidates} aria-label={t("otherOptions")}>
          {candidates.map((c) => (
            <li key={c.canonical_id}>
              <button
                type="button"
                className={styles.candidate}
                onClick={() => listActions.confirm(item.id, c)}
              >
                {productName(c, locale)}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
