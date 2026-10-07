"use client";

import { useId, useState, type FormEvent } from "react";
import { reportGap } from "@/api/client";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Price } from "@/components/ui/Price";
import { IconCheck, IconClock, IconWarning } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { reportGapReported } from "@/features/consent/betaEvents";
import controls from "@/features/profile/controls/controls.module.css";
import { formatTime } from "@/lib/format";
import { buildGapRequest, GAP_REASONS, type GapContext, type GapReason } from "./gapReport";
import styles from "./GapReport.module.css";

export type GapReportSheetProps = {
  open: boolean;
  onClose: () => void;
  /** What the user is looking at. Store, item, shown price and its time are captured from here. */
  context: GapContext;
};

/**
 * Report-a-gap sheet (issue #16, D10). Shared by every screen that shows a price or a substitute:
 * W4b's result cards and substitution card render `<ReportGapButton context={...} />` or this sheet
 * directly. The store, item, shown price and the time of the price are filled in from `context`,
 * so one tap plus "שליחה" is enough; the reason, the price at the shelf and a note are optional.
 */
export function GapReportSheet({ open, onClose, context }: GapReportSheetProps) {
  const [reason, setReason] = useState<GapReason | null>(null);
  const [actual, setActual] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const actualId = useId();
  const noteId = useId();

  function close() {
    onClose();
    // Reset after the sheet is gone so the next report starts clean.
    setTimeout(() => {
      setReason(null);
      setActual("");
      setNote("");
      setState("idle");
    }, 200);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setState("sending");
    try {
      ensureApiAuth();
      await reportGap(buildGapRequest(context, { reason, actualPrice: actual, note }));
      reportGapReported();
      setState("sent");
    } catch {
      setState("error");
    }
  }

  const subject = context.itemName ?? "המחיר שמוצג";
  return (
    <BottomSheet
      open={open}
      onClose={close}
      eyebrow="דיווח על פער"
      title={state === "sent" ? "תודה על הדיווח" : subject}
      hideCloseButton={false}
    >
      {state === "sent" ? (
        <div className={controls.stack} data-testid="gap-sent">
          <p className={styles.confirm} role="status">
            <IconCheck size={18} />
            <span>הדיווח התקבל ויעזור לנו לבדוק את המחיר. לא נשנה מחיר אוטומטית בלי בדיקה.</span>
          </p>
          <Button block onClick={close}>
            סגירה
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className={controls.stack} noValidate>
          <dl className={styles.facts}>
            <div>
              <dt>סניף</dt>
              <dd>{context.storeName}</dd>
            </div>
            {context.shownPrice !== undefined && context.shownPrice !== null ? (
              <div>
                <dt>המחיר שהוצג</dt>
                <dd>
                  <Price amount={context.shownPrice} />
                  {context.priceUpdatedAt ? (
                    <span className={styles.time}>
                      <IconClock size={13} /> עודכן {formatTime(context.priceUpdatedAt)}
                    </span>
                  ) : null}
                </dd>
              </div>
            ) : null}
          </dl>

          <div className={controls.group} role="group" aria-labelledby={`${noteId}-reasons`}>
            <p id={`${noteId}-reasons`} className={controls.legend}>
              מה לא מסתדר? (לא חובה)
            </p>
            <div className={styles.reasons}>
              {GAP_REASONS.map((r) => (
                <Chip
                  key={r.value}
                  onClick={() => setReason(reason === r.value ? null : r.value)}
                  selected={reason === r.value}
                  tone={reason === r.value ? "accent" : "neutral"}
                >
                  {r.label}
                </Chip>
              ))}
            </div>
          </div>

          <div className={controls.field}>
            <label htmlFor={actualId} className={controls.label}>
              המחיר במדף או בקופה (לא חובה)
            </label>
            <input
              id={actualId}
              className={controls.input}
              inputMode="decimal"
              dir="ltr"
              placeholder="₪ 0.00"
              value={actual}
              onChange={(e) => setActual(e.target.value)}
            />
          </div>

          <div className={controls.field}>
            <label htmlFor={noteId} className={controls.label}>
              הערה (לא חובה)
            </label>
            <textarea
              id={noteId}
              className={`${controls.input} ${styles.textarea}`}
              rows={3}
              maxLength={300}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          {state === "error" ? (
            <p className={controls.error} role="alert">
              לא הצלחנו לשלוח את הדיווח. בדקי את החיבור ונסי שוב.
            </p>
          ) : null}
          <Button type="submit" block disabled={state === "sending"}>
            {state === "sending" ? "שולחת…" : "שליחה"}
          </Button>
        </form>
      )}
    </BottomSheet>
  );
}

export type ReportGapButtonProps = {
  context: GapContext;
  /** Visible label; the accessible name always includes the item. */
  label?: string;
  size?: "md" | "sm";
};

/** One-tap entry point: a small ghost button that opens the sheet with the context filled in. */
export function ReportGapButton({
  context,
  label = "דווחי על פער",
  size = "sm",
}: ReportGapButtonProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="ghost"
        size={size}
        iconStart={<IconWarning size={15} />}
        onClick={() => setOpen(true)}
        aria-label={`${label}: ${context.itemName ?? context.storeName}`}
      >
        {label}
      </Button>
      <GapReportSheet open={open} onClose={() => setOpen(false)} context={context} />
    </>
  );
}
