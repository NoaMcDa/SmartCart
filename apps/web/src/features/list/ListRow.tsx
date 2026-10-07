"use client";

import { useId, useState } from "react";
import { FlexChip, IconClose, IconWarning, Stepper, Tag } from "@/components/ui";
import { listActions, type ListItem } from "@/state/list";
import styles from "./ListBuilder.module.css";

export type ListRowProps = {
  item: ListItem;
  onOpenFlex: (id: string) => void;
};

/** One list row: name, flexibility chip, estimated tag, quantity stepper, remove; confirmation. */
export function ListRow({ item, onOpenFlex }: ListRowProps) {
  const name = item.canonical?.display_name_he ?? item.inputText;
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
            {item.isWeighed ? <Tag variant="estimated">מחיר משוער · שקיל</Tag> : null}
          </div>
        </div>
        <Stepper
          value={item.quantity}
          onChange={(q) => listActions.setQuantity(item.id, q)}
          min={weighedKg ? 0.5 : 1}
          step={weighedKg ? 0.5 : 1}
          unit={weighedKg ? 'ק"ג' : undefined}
          label={name}
          className={styles.stepper}
        />
        <button
          type="button"
          className={styles.iconButton}
          onClick={() => listActions.remove(item.id)}
          aria-label={`הסרת ${name}`}
        >
          <IconClose size={18} />
        </button>
      </div>
      {item.needsConfirmation ? <Confirmation item={item} /> : null}
    </div>
  );
}

function Confirmation({ item }: { item: ListItem }) {
  const [choosing, setChoosing] = useState(false);
  const listId = useId();
  const suggestion = item.canonical?.display_name_he ?? "";
  const candidates = item.candidates.length
    ? item.candidates
    : item.canonical
      ? [item.canonical]
      : [];
  return (
    <div className={styles.confirm} role="group" aria-label={`אישור הפריט ${item.inputText}`}>
      <div className={styles.confirmLine}>
        <IconWarning size={16} />
        <span className={styles.confirmText}>
          כתבת &quot;{item.inputText}&quot;. התכוונת ל{suggestion}?
        </span>
        <button
          type="button"
          className={styles.confirmYes}
          onClick={() => listActions.confirm(item.id)}
          aria-label={`כן, ${suggestion}`}
        >
          כן
        </button>
        <button
          type="button"
          className={styles.confirmOther}
          aria-expanded={choosing}
          aria-controls={listId}
          onClick={() => setChoosing((v) => !v)}
        >
          בחרי אחר
        </button>
      </div>
      {choosing ? (
        <ul id={listId} className={styles.candidates} aria-label="אפשרויות אחרות">
          {candidates.map((c) => (
            <li key={c.canonical_id}>
              <button
                type="button"
                className={styles.candidate}
                onClick={() => listActions.confirm(item.id, c)}
              >
                {c.display_name_he}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
