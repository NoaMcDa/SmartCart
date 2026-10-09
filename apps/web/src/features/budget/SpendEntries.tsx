"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Button, IconInfo, Price, Tag } from "@/components/ui";
import controls from "@/features/profile/controls/controls.module.css";
import { Count } from "@/features/compare/Count";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { storeLabel } from "@/lib/storeName";
import { budgetMessages } from "@/i18n/messages/budget";
import { dayLabel } from "./month";
import {
  MAX_SPEND_TOTAL,
  removeSpendRow,
  restoreSpendRow,
  type RemovedSpend,
  type SpendRow,
} from "./spendState";
import { commitSpendRemoval, correctSpend } from "./sync";
import styles from "./Budget.module.css";

/** How long "ביטול" stays available after a delete (issue #70). */
export const UNDO_MS = 5000;

type Notice = { kind: "ok" | "error"; text: string };

/**
 * This month's shops with "תיקון הסכום" and delete (issue #70). Both act on the device copy first.
 * Signed in, a correction is also sent to the account (rolled back if it fails) and a delete is
 * sent when the 5-second undo window closes (the entry comes back if the account refuses).
 * Amounts are the app's estimate until the person corrects them.
 */
export function SpendEntries({
  entries,
  signedIn,
  heading,
}: {
  entries: ReadonlyArray<SpendRow>;
  signedIn: boolean;
  /** Shown above the list while there is at least one shop. */
  heading: string;
}) {
  const t = useT(budgetMessages);
  const { locale, intl } = useLocale();
  const fieldId = useId();
  const [editing, setEditing] = useState<{
    id: string;
    draft: string;
    error: string | null;
  } | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [undo, setUndo] = useState<RemovedSpend | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);

  const pending = useRef<RemovedSpend | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const signedInRef = useRef(signedIn);
  useEffect(() => {
    signedInRef.current = signedIn;
  }, [signedIn]);

  /** Sends the delete of the entry waiting in the undo window, and reports a refusal. */
  async function flush(): Promise<void> {
    clearTimeout(timer.current);
    const removed = pending.current;
    pending.current = null;
    setUndo(null);
    if (!removed) return;
    const ok = await commitSpendRemoval(removed, signedInRef.current);
    if (!ok) setNotice({ kind: "error", text: t("removeFailed") });
  }

  // Leaving the screen inside the undo window ends it: the delete goes ahead.
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      const removed = pending.current;
      pending.current = null;
      if (removed) void commitSpendRemoval(removed, signedInRef.current);
    },
    [],
  );

  const label = (e: SpendRow) =>
    `${dayLabel(e.date)} · ${storeLabel(e.store_name, locale)}${e.plan === "split" ? t("splitMark") : ""}`;

  async function onSave(event: FormEvent, row: SpendRow) {
    event.preventDefault();
    if (!editing || busy) return;
    setBusy(true);
    const outcome = await correctSpend(row.id, editing.draft, signedIn);
    setBusy(false);
    if (outcome === "invalid") {
      setEditing({
        ...editing,
        error: t("invalidTotal", { max: MAX_SPEND_TOTAL.toLocaleString(intl) }),
      });
      return;
    }
    setEditing(null);
    setNotice(
      outcome === "failed"
        ? { kind: "error", text: t("correctFailed") }
        : outcome === "ok"
          ? { kind: "ok", text: t("saved") }
          : null,
    );
  }

  async function onConfirmRemove(row: SpendRow) {
    await flush(); // an earlier delete still in its undo window is final now
    const removed = removeSpendRow(row.id);
    setConfirmId(null);
    setNotice(null);
    if (!removed) return;
    pending.current = removed;
    setUndo(removed);
    timer.current = setTimeout(() => void flush(), UNDO_MS);
  }

  function onUndo() {
    clearTimeout(timer.current);
    const removed = pending.current;
    pending.current = null;
    setUndo(null);
    if (removed) restoreSpendRow(removed);
  }

  return (
    <>
      {entries.length > 0 ? <h3 className={styles.subTitle}>{heading}</h3> : null}
      {entries.length > 0 ? (
        <ul className={styles.entries} data-testid="spend-entries">
          {entries.map((e) => {
            const isEditing = editing?.id === e.id;
            const isConfirming = confirmId === e.id;
            return (
              <li key={e.id} data-testid="spend-entry">
                <span className={styles.entryMain}>
                  <span>
                    <span dir="ltr">{dayLabel(e.date)}</span> · {storeLabel(e.store_name, locale)}
                    {e.plan === "split" ? t("splitMark") : ""}
                    <span className={styles.muted}>
                      {" · "}
                      <Count n={e.item_count} noun="items" />
                    </span>
                  </span>
                  <Tag variant={e.corrected ? "matched" : "estimated"}>
                    {e.corrected ? t("corrected") : t("estimate")}
                  </Tag>
                </span>
                <Price amount={e.total} />

                {isEditing && editing ? (
                  <form
                    className={styles.entryForm}
                    onSubmit={(event) => void onSave(event, e)}
                    noValidate
                    data-testid="spend-edit-form"
                  >
                    <div className={controls.field}>
                      <label htmlFor={`${fieldId}-${e.id}`} className={controls.label}>
                        {t("fieldLabel")}
                      </label>
                      <input
                        id={`${fieldId}-${e.id}`}
                        className={controls.input}
                        type="text"
                        inputMode="decimal"
                        dir="ltr"
                        autoFocus
                        value={editing.draft}
                        aria-invalid={editing.error ? true : undefined}
                        aria-describedby={`${fieldId}-${e.id}-hint`}
                        onChange={(ev) =>
                          setEditing({ ...editing, draft: ev.target.value, error: null })
                        }
                      />
                      <p id={`${fieldId}-${e.id}-hint`} className={styles.note}>
                        {t("fieldHint")}
                      </p>
                    </div>
                    {editing.error ? (
                      <p className={styles.warn} role="alert">
                        <IconInfo size={16} />
                        {editing.error}
                      </p>
                    ) : null}
                    <div className={styles.actions}>
                      <Button type="submit" size="sm" disabled={busy}>
                        {t("save")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setEditing(null)}
                      >
                        {t("cancel")}
                      </Button>
                    </div>
                  </form>
                ) : isConfirming ? (
                  <div
                    className={styles.entryForm}
                    role="group"
                    aria-label={t("confirmTitle", { entry: label(e) })}
                  >
                    <p className={styles.warn}>
                      <IconInfo size={16} />
                      <span>
                        {t("confirmTitle", { entry: label(e) })} {t("confirmBody")}
                      </span>
                    </p>
                    <div className={styles.actions}>
                      <Button
                        type="button"
                        size="sm"
                        tone="bad"
                        onClick={() => void onConfirmRemove(e)}
                        data-testid="spend-delete-confirm"
                      >
                        {t("confirmYes")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        autoFocus
                        onClick={() => setConfirmId(null)}
                      >
                        {t("cancel")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.entryActions} role="group" aria-label={t("entryActions")}>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      aria-label={t("correctLabel", { entry: label(e) })}
                      onClick={() => {
                        setConfirmId(null);
                        setNotice(null);
                        setEditing({ id: e.id, draft: e.total.toFixed(2), error: null });
                      }}
                    >
                      {t("correct")}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-label={t("removeLabel", { entry: label(e) })}
                      onClick={() => {
                        setEditing(null);
                        setNotice(null);
                        setConfirmId(e.id);
                      }}
                    >
                      {t("remove")}
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      {notice ? (
        <p
          className={notice.kind === "error" ? styles.warn : styles.muted}
          role={notice.kind === "error" ? "alert" : "status"}
          data-testid="spend-notice"
        >
          {notice.kind === "error" ? <IconInfo size={16} /> : null}
          {notice.text}
        </p>
      ) : null}

      {undo ? (
        <div className={styles.snackbar} role="status" data-testid="spend-undo-bar">
          <span>{t("removed")}</span>
          <Button size="sm" variant="ghost" onClick={onUndo}>
            {t("undo")}
          </Button>
        </div>
      ) : null}
    </>
  );
}
