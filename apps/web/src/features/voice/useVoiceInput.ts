"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useLocale } from "@/i18n/LocaleProvider";
import {
  classifyVoiceError,
  getRecognizerCtor,
  readTranscript,
  transcriptText,
  voiceLangs,
  type SpeechRecognitionLike,
  type Transcript,
  type VoiceFailure,
} from "./speech";

export type VoicePhase =
  /** Nothing running; the sheet explains what will happen. */
  | "idle"
  /** `start()` was called, the browser may be asking for the microphone. */
  | "starting"
  | "listening"
  /** Recognition ended with text to confirm. */
  | "review"
  | "error";

export type VoiceInput = {
  phase: VoicePhase;
  failure: VoiceFailure | null;
  transcript: Transcript;
  /** Starts listening. The microphone permission is asked by the browser at this moment. */
  start: () => void;
  /** Ends the recording; what was heard is kept for the confirm step. */
  stop: () => void;
  /** Throws away the attempt and returns to `idle`. */
  reset: () => void;
};

const EMPTY: Transcript = { finals: [], interim: "" };
const subscribeNothing = () => () => {};

/**
 * Whether this browser has a speech recognizer: `null` until the client has hydrated (so the
 * server and first client render agree), then true or false.
 */
export function useVoiceSupported(): boolean | null {
  return useSyncExternalStore(
    subscribeNothing,
    () => Boolean(getRecognizerCtor()),
    () => null,
  );
}

/**
 * Drives one `SpeechRecognition` (`he-IL`, or `ar-IL` then `ar` in Arabic; continuous, interim results). Every outcome ends in
 * `review` (with the text, even after a late error) or `error` (with a reason); nothing throws.
 * Leaving the screen aborts the recognizer.
 */
export function useVoiceInput(): VoiceInput {
  const { locale } = useLocale();
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [failure, setFailure] = useState<VoiceFailure | null>(null);
  const [transcript, setTranscript] = useState<Transcript>(EMPTY);
  const current = useRef<SpeechRecognitionLike | null>(null);

  /** Detaches and aborts the running recognizer so none of its late events reach the state. */
  const dispose = useCallback(() => {
    const rec = current.current;
    current.current = null;
    if (!rec) return;
    rec.onstart = rec.onresult = rec.onerror = rec.onend = null;
    try {
      rec.abort();
    } catch {
      // already stopped
    }
  }, []);

  useEffect(() => dispose, [dispose]);

  const start = useCallback(() => {
    dispose();
    setTranscript(EMPTY);
    setFailure(null);
    const Ctor = getRecognizerCtor();
    if (!Ctor) {
      setFailure("unsupported");
      setPhase("error");
      return;
    }
    const langs = voiceLangs(locale);

    // One recognizer for `langs[langIndex]`. A browser that does not know a regional variant
    // (`ar-IL`) reports `language-not-supported`; the next candidate (`ar`) is tried before the
    // person is told the language is unsupported.
    const launch = (langIndex: number) => {
      const rec = new Ctor();
      rec.lang = langs[langIndex] ?? langs[0] ?? "he-IL";
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      current.current = rec;
      let heard: Transcript = EMPTY;
      let reason: VoiceFailure | null = null;

      // Ends the attempt once: with the text if there is any, otherwise with the reason.
      const settle = () => {
        if (current.current !== rec) return;
        current.current = null;
        rec.onstart = rec.onresult = rec.onerror = rec.onend = null;
        try {
          rec.abort();
        } catch {
          // already stopped
        }
        if (transcriptText(heard)) {
          setTranscript(heard);
          setFailure(null);
          setPhase("review");
        } else {
          setFailure(reason ?? "no-speech");
          setPhase("error");
        }
      };

      rec.onstart = () => {
        if (current.current === rec) setPhase("listening");
      };
      rec.onresult = (event) => {
        if (current.current !== rec) return;
        heard = readTranscript(event.results);
        setTranscript(heard);
      };
      rec.onerror = (event) => {
        if (current.current !== rec) return;
        const kind = classifyVoiceError(event.error);
        if (!kind) return;
        if (kind === "language" && langIndex + 1 < langs.length) {
          dispose();
          launch(langIndex + 1);
          return;
        }
        reason = kind;
        // Some browsers never fire `end` after a permission or microphone error.
        if (kind === "denied" || kind === "no-mic" || kind === "language") settle();
      };
      rec.onend = settle;

      setPhase("starting");
      try {
        rec.start();
      } catch {
        reason = "failed";
        settle();
      }
    };
    launch(0);
  }, [dispose, locale]);

  const stop = useCallback(() => {
    const rec = current.current;
    if (!rec) return;
    try {
      rec.stop(); // final results arrive, then `end`
    } catch {
      rec.onend?.();
    }
  }, []);

  const reset = useCallback(() => {
    dispose();
    setTranscript(EMPTY);
    setFailure(null);
    setPhase("idle");
  }, [dispose]);

  return { phase, failure, transcript, start, stop, reset };
}
