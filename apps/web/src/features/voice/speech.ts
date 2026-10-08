/**
 * Browser speech recognition for the voice list (issue #65), behind a thin typed seam.
 *
 * The Web Speech API is `SpeechRecognition` (Chrome, Edge, Safari 14.1+ unprefixed on recent
 * versions) or `webkitSpeechRecognition`. Whether it works for `he-IL` (or `ar-IL`) depends on the browser and
 * the OS and has not been verified here, so nothing assumes it: `getRecognizerCtor()` is a runtime
 * check, the list builder hides the microphone without it, and every failure the recognizer can
 * report has a Hebrew message that points back to typing.
 *
 * Where the audio goes is the browser's business: in Chrome the recognizer sends it to Google's
 * speech service. SmartCart never records, stores or uploads audio; the copy in the voice sheet
 * says both things.
 */

import type { Locale } from "@/i18n/locales";
import { voiceMessages, type VoiceMessageKey } from "@/i18n/messages/voice";

/** The parts of `SpeechRecognition` this app uses (the DOM lib has no type for it). */
export interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: SpeechResultEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type SpeechAlternativeLike = { transcript: string; confidence?: number };
export type SpeechResultLike = ArrayLike<SpeechAlternativeLike> & { isFinal: boolean };
export type SpeechResultEventLike = {
  resultIndex?: number;
  results: ArrayLike<SpeechResultLike>;
};

export type RecognizerCtor = new () => SpeechRecognitionLike;

export const VOICE_LANG = "he-IL";

/**
 * Recognition languages to try for a UI locale, in order. Arabic asks for the Israeli variant
 * first and falls back to plain `ar` when the browser reports `language-not-supported` for it.
 * Whether a given browser recognizes Arabic has not been verified here; the same feature
 * detection and failure messages apply as for Hebrew.
 */
export function voiceLangs(locale: Locale): readonly string[] {
  return locale === "ar" ? ["ar-IL", "ar"] : [VOICE_LANG];
}

type SpeechWindow = {
  SpeechRecognition?: RecognizerCtor;
  webkitSpeechRecognition?: RecognizerCtor;
};

/** The recognizer constructor of this browser, or null when it has none (also on the server). */
export function getRecognizerCtor(): RecognizerCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as SpeechWindow;
  const ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  return typeof ctor === "function" ? ctor : null;
}

export type VoiceFailure =
  "denied" | "no-speech" | "no-mic" | "network" | "language" | "unsupported" | "failed";

/**
 * Maps `SpeechRecognitionErrorEvent.error` to a failure. `aborted` is what `abort()` and a second
 * `start()` produce, so it is not a failure (null).
 */
export function classifyVoiceError(code: string): VoiceFailure | null {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "denied";
    case "no-speech":
      return "no-speech";
    case "audio-capture":
      return "no-mic";
    case "network":
      return "network";
    case "language-not-supported":
      return "language";
    case "aborted":
      return null;
    default:
      return "failed";
  }
}

/** Message key (`voiceMessages`) per failure; the sheet translates it. */
export const VOICE_MESSAGE_KEYS = {
  denied: "failDenied",
  "no-speech": "failNoSpeech",
  "no-mic": "failNoMic",
  network: "failNetwork",
  language: "failLanguage",
  unsupported: "failUnsupported",
  failed: "failFailed",
} as const satisfies Record<VoiceFailure, VoiceMessageKey>;

/** The failure texts in Hebrew (the default locale), for code that has no locale at hand. */
export const VOICE_MESSAGES: Record<VoiceFailure, string> = Object.fromEntries(
  (Object.keys(VOICE_MESSAGE_KEYS) as VoiceFailure[]).map((f) => [
    f,
    voiceMessages.he[VOICE_MESSAGE_KEYS[f]],
  ]),
) as Record<VoiceFailure, string>;

export type Transcript = {
  /** Finished phrases, one per pause the recognizer detected. */
  finals: string[];
  /** The phrase still being recognized (may change); empty when none. */
  interim: string;
};

const clean = (s: string) => s.replace(/\s+/gu, " ").trim();

/**
 * Rebuilds the whole transcript from the recognizer's result list (in continuous mode the list
 * only grows, so reading it from the start is correct and immune to repeated events).
 */
export function readTranscript(results: ArrayLike<SpeechResultLike>): Transcript {
  const finals: string[] = [];
  let interim = "";
  for (let i = 0; i < results.length; i += 1) {
    const result = results[i];
    const text = clean(result?.[0]?.transcript ?? "");
    if (!text) continue;
    if (result?.isFinal) finals.push(text);
    else interim = interim ? `${interim} ${text}` : text;
  }
  return { finals, interim };
}

/**
 * The text that goes to the editable confirm step: one phrase per line. A pause between two items
 * is where the recognizer ends a phrase, and `/parse-list` splits on new lines like on commas.
 */
export function transcriptText(t: Transcript): string {
  return [...t.finals, ...(t.interim ? [t.interim] : [])].join("\n");
}
