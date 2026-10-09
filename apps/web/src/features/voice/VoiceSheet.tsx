"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { BottomSheet, Button, IconInfo, IconMic } from "@/components/ui";
import { reportVoiceCompleted, reportVoiceStarted } from "@/features/consent/betaEvents";
import type { VoiceOutcome } from "@/features/consent/betaEvents";
import { useT } from "@/i18n/LocaleProvider";
import { voiceMessages } from "@/i18n/messages/voice";
import { transcriptText, VOICE_MESSAGE_KEYS, type VoiceFailure } from "./speech";
import { useVoiceInput } from "./useVoiceInput";
import styles from "./Voice.module.css";

export type VoiceSheetProps = {
  open: boolean;
  onClose: () => void;
  /**
   * Sends the confirmed text down the same path as a pasted list (`/parse-list`). Resolves to the
   * number of rows added, or null when the request failed (the sheet keeps the text).
   */
  onAdd: (text: string) => Promise<number | null>;
};

function outcomeOf(failure: VoiceFailure): VoiceOutcome {
  return failure === "no-speech" ? "empty" : "error";
}

/**
 * Voice list input (issue #65): explanation first and the microphone prompt only after the tap on
 * "התחלת הקלטה" (the scan page's pattern), live transcript while listening, then an editable
 * confirm step. Nothing is parsed until the person presses "הוסיפי לרשימה"; the text then goes
 * through the same `/parse-list` call as a pasted list. Audio is never stored or sent by the app.
 */
export function VoiceSheet({ open, onClose, onAdd }: VoiceSheetProps) {
  const t = useT(voiceMessages);
  const voice = useVoiceInput();
  const draftId = useId();
  // The person's edits to the transcript; null = show what was heard.
  const [draft, setDraft] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [addFailed, setAddFailed] = useState(false);
  // performance.now() of the tap on "start" while an attempt is open (events: started -> completed).
  const attemptStart = useRef<number | null>(null);

  const closeAttempt = useCallback((outcome: VoiceOutcome, itemCount?: number) => {
    const startedAt = attemptStart.current;
    if (startedAt === null) return;
    attemptStart.current = null;
    reportVoiceCompleted({ outcome, durationMs: performance.now() - startedAt, itemCount });
  }, []);

  // Recognition that ended without text reports its reason; leaving the screen cancels.
  const { phase, failure } = voice;
  useEffect(() => {
    if (phase === "error" && failure) closeAttempt(outcomeOf(failure));
  }, [phase, failure, closeAttempt]);
  useEffect(() => () => closeAttempt("cancelled"), [closeAttempt]);

  function begin() {
    closeAttempt("cancelled"); // a re-record abandons the previous attempt
    attemptStart.current = performance.now();
    reportVoiceStarted();
    setDraft(null);
    setAddFailed(false);
    voice.start();
  }

  function close() {
    closeAttempt("cancelled");
    voice.reset();
    setDraft(null);
    setAddFailed(false);
    onClose();
  }

  const heard = transcriptText(voice.transcript);
  const text = draft ?? heard;

  async function add() {
    const value = text.trim();
    if (!value || adding) return;
    setAdding(true);
    setAddFailed(false);
    const count = await onAdd(value);
    setAdding(false);
    if (count === null) {
      setAddFailed(true);
      return;
    }
    closeAttempt("parsed", count);
    voice.reset();
    setDraft(null);
    onClose();
  }

  let body;
  let actions;
  if (phase === "idle") {
    body = (
      <>
        <p className={styles.lead}>{t("lead")}</p>
        <p className={styles.privacy} data-testid="voice-privacy">
          {t("privacy")}
        </p>
      </>
    );
    actions = (
      <>
        <Button variant="outline" onClick={close}>
          {t("cancel")}
        </Button>
        <Button iconStart={<IconMic size={18} />} onClick={begin} data-testid="voice-start">
          {t("startRecording")}
        </Button>
      </>
    );
  } else if (phase === "starting" || phase === "listening") {
    body = (
      <>
        <p className={styles.status} role="status" data-testid="voice-status">
          <span className={styles.dot} aria-hidden="true" />
          {phase === "starting" ? t("waitingMic") : t("listening")}
        </p>
        <div className={styles.live} data-testid="voice-live">
          {voice.transcript.finals.join("\n")}
          {voice.transcript.interim ? (
            <span className={styles.liveInterim}>
              {voice.transcript.finals.length ? "\n" : ""}
              {voice.transcript.interim}
            </span>
          ) : null}
        </div>
      </>
    );
    actions = (
      <>
        <Button variant="outline" onClick={close}>
          {t("cancel")}
        </Button>
        <Button onClick={voice.stop} disabled={phase === "starting"} data-testid="voice-stop">
          {t("doneSpeaking")}
        </Button>
      </>
    );
  } else if (phase === "review") {
    body = (
      <>
        <label htmlFor={draftId} className={styles.label}>
          {t("draftLabel")}
        </label>
        <textarea
          id={draftId}
          className={styles.draft}
          dir="auto"
          value={text}
          onChange={(e) => setDraft(e.target.value)}
          data-testid="voice-draft"
        />
        {addFailed ? (
          <p className={styles.callout} role="alert">
            <IconInfo size={16} />
            {t("addFailed")}
          </p>
        ) : null}
      </>
    );
    actions = (
      <>
        <Button variant="outline" onClick={begin} disabled={adding}>
          {t("recordAgain")}
        </Button>
        <Button
          onClick={() => void add()}
          disabled={adding || !text.trim()}
          data-testid="voice-add"
        >
          {t("addToList")}
        </Button>
      </>
    );
  } else {
    const reason = failure ?? "failed";
    body = (
      <p className={styles.callout} role="alert" data-testid="voice-error">
        <IconInfo size={16} />
        {t(VOICE_MESSAGE_KEYS[reason])}
      </p>
    );
    actions = (
      <>
        <Button variant="outline" onClick={close}>
          {t("backToTyping")}
        </Button>
        {reason === "unsupported" || reason === "language" ? null : (
          <Button onClick={begin}>{t("tryAgain")}</Button>
        )}
      </>
    );
  }

  return (
    <BottomSheet open={open} onClose={close} eyebrow={t("eyebrow")} title={t("title")}>
      <div className={styles.body}>
        {body}
        <div className={styles.footer}>{actions}</div>
      </div>
    </BottomSheet>
  );
}
