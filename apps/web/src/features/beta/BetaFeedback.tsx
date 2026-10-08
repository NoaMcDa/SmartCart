"use client";

import { useId, useState, type FormEvent } from "react";
import { postBetaFeedback } from "@/api/client";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { IconCheck } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import controls from "@/features/profile/controls/controls.module.css";
import { useT } from "@/i18n/LocaleProvider";
import { betaMessages } from "@/i18n/messages/beta";
import styles from "./Beta.module.css";
import { useBetaMembership } from "./useBetaMembership";

export const FEEDBACK_MAX_CHARS = 1000;

type SheetState = "idle" | "sending" | "sent" | "error";

/**
 * Feedback sheet: a 1 to 5 rating and up to 1000 characters. The API stores it with the member's
 * segment and without the user id (`POST /beta/feedback`), so the sheet says not to write personal
 * details. Only the maintainer reads the text (`smartcart-catalog beta-feedback`).
 */
export function BetaFeedbackSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT(betaMessages);
  const [rating, setRating] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [state, setState] = useState<SheetState>("idle");
  const [missingRating, setMissingRating] = useState(false);
  const groupId = useId();
  const textId = useId();
  const hintId = useId();

  function close() {
    onClose();
    // Reset after the sheet is gone so the next one starts clean.
    setTimeout(() => {
      setRating(null);
      setText("");
      setState("idle");
      setMissingRating(false);
    }, 200);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (rating === null) {
      setMissingRating(true);
      return;
    }
    setState("sending");
    try {
      ensureApiAuth();
      await postBetaFeedback({ rating, text: text.trim() });
      setState("sent");
    } catch {
      setState("error");
    }
  }

  return (
    <BottomSheet
      open={open}
      onClose={close}
      eyebrow={t("fbEyebrow")}
      title={state === "sent" ? t("fbSentTitle") : t("fbTitle")}
    >
      {state === "sent" ? (
        <div className={controls.stack} data-testid="beta-feedback-sent">
          <p className={styles.status} role="status">
            <IconCheck size={18} />
            <span>{t("fbSent")}</span>
          </p>
          <Button block onClick={close}>
            {t("fbClose")}
          </Button>
        </div>
      ) : (
        <form
          onSubmit={submit}
          className={controls.stack}
          noValidate
          data-testid="beta-feedback-form"
        >
          <fieldset
            className={styles.rating}
            aria-describedby={missingRating ? `${groupId}-err` : undefined}
          >
            <legend className={styles.ratingLegend}>{t("fbRatingLegend")}</legend>
            <div className={styles.ratingRow}>
              {[1, 2, 3, 4, 5].map((n) => (
                <div key={n} className={styles.ratingOption}>
                  <input
                    type="radio"
                    className={`sr-only ${styles.ratingInput}`}
                    id={`${groupId}-${n}`}
                    name={`${groupId}-rating`}
                    value={n}
                    checked={rating === n}
                    onChange={() => {
                      setRating(n);
                      setMissingRating(false);
                    }}
                  />
                  <label htmlFor={`${groupId}-${n}`} className={styles.ratingLabel}>
                    <span className="sr-only">{t("fbRatingOption", { n })}</span>
                    <span aria-hidden="true">{n}</span>
                  </label>
                </div>
              ))}
            </div>
            <div className={styles.ratingEnds} aria-hidden="true">
              <span>{t("fbRatingLow")}</span>
              <span>{t("fbRatingHigh")}</span>
            </div>
            {missingRating ? (
              <p id={`${groupId}-err`} className={controls.error} role="alert">
                {t("fbPickRating")}
              </p>
            ) : null}
          </fieldset>

          <div className={controls.field}>
            <label htmlFor={textId} className={controls.label}>
              {t("fbTextLabel")}
            </label>
            <textarea
              id={textId}
              className={`${controls.input} ${styles.textarea}`}
              rows={5}
              maxLength={FEEDBACK_MAX_CHARS}
              value={text}
              aria-describedby={hintId}
              onChange={(e) => setText(e.target.value)}
            />
            <p id={hintId} className={controls.hint}>
              {t("fbTextHint")}{" "}
              <span className={styles.count} dir="auto">
                {t("fbCount", { n: text.length })}
              </span>
            </p>
          </div>

          {state === "error" ? (
            <p className={controls.error} role="alert">
              {t("fbError")}
            </p>
          ) : null}
          <Button type="submit" block disabled={state === "sending"}>
            {state === "sending" ? t("fbSending") : t("fbSend")}
          </Button>
        </form>
      )}
    </BottomSheet>
  );
}

/**
 * The "משוב על הבטא" entry, rendered only for beta members (nothing for everyone else, and nothing
 * until the membership is known). The app shell mounts it once, for example in the Profile screen
 * or the top bar menu; it brings its own sheet.
 */
export function BetaFeedbackEntry({ className }: { className?: string }) {
  const t = useT(betaMessages);
  const { member } = useBetaMembership();
  const [open, setOpen] = useState(false);
  if (!member) return null;
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className={className}
        onClick={() => setOpen(true)}
        data-testid="beta-feedback-entry"
      >
        {t("feedbackButton")}
      </Button>
      <BetaFeedbackSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}
