"use client";

import { useEffect, useState } from "react";
import { useT } from "@/i18n/LocaleProvider";
import { personalMessages } from "@/i18n/messages/personal";
import styles from "./Personal.module.css";

export type Note = { text: string; undo?: () => void };

const SHOWN_MS = 12_000;

/** One note and its "undo", cleared by itself after a while. */
export function useNote(): [Note | null, (note: Note | null) => void] {
  const [note, setNote] = useState<Note | null>(null);
  useEffect(() => {
    if (!note) return;
    const timer = setTimeout(() => setNote(null), SHOWN_MS);
    return () => clearTimeout(timer);
  }, [note]);
  return [note, setNote];
}

/**
 * The status line of a suggestion card. The live region is always in the page (empty it takes no
 * room), so a screen reader hears what changed and the "undo" that goes with it.
 */
export function StatusNote({
  note,
  onClose,
  testId = "personal-status",
}: {
  note: Note | null;
  onClose: () => void;
  testId?: string;
}) {
  const t = useT(personalMessages);
  return (
    <div role="status" className={styles.status} data-testid={testId}>
      {note ? (
        <>
          <span>{note.text}</span>
          {note.undo ? (
            <button
              type="button"
              className={styles.undo}
              onClick={() => {
                // Closed first: an undo may leave a note of its own ("back to what it was").
                onClose();
                note.undo?.();
              }}
            >
              {t("undo")}
            </button>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
