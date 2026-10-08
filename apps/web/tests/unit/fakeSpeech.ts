/**
 * A fake `SpeechRecognition` for unit tests. `install()` puts it on `window` (the way a browser
 * does), `FakeRecognizer.last()` is the instance the app created, and the helpers play what the
 * browser would do: `begin()` (the microphone is granted), `hear(...)` (results), `fail(code)`
 * (an error then the end event) and `finish()` (the end event).
 */
import type {
  SpeechRecognitionLike,
  SpeechResultEventLike,
  SpeechResultLike,
} from "@/features/voice/speech";

export type Heard = { text: string; final?: boolean };

export class FakeRecognizer implements SpeechRecognitionLike {
  static instances: FakeRecognizer[] = [];
  static last(): FakeRecognizer {
    const rec = FakeRecognizer.instances.at(-1);
    if (!rec) throw new Error("the app has not created a recognizer");
    return rec;
  }

  lang = "";
  continuous = false;
  interimResults = false;
  maxAlternatives = 1;
  onstart: (() => void) | null = null;
  onresult: ((event: SpeechResultEventLike) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = false;
  stopped = false;
  aborted = false;
  private results: SpeechResultLike[] = [];

  constructor() {
    FakeRecognizer.instances.push(this);
  }

  start() {
    this.started = true;
  }
  stop() {
    this.stopped = true;
    this.onend?.();
  }
  abort() {
    this.aborted = true;
  }

  /** The microphone was granted and the recognizer is listening. */
  begin() {
    this.onstart?.();
  }
  /** Replays the whole result list, like the browser does in continuous mode. */
  hear(...phrases: Heard[]) {
    this.results = phrases.map((p) =>
      Object.assign([{ transcript: p.text, confidence: 0.9 }], { isFinal: p.final ?? true }),
    );
    this.onresult?.({ resultIndex: 0, results: this.results });
  }
  fail(code: string) {
    this.onerror?.({ error: code });
    this.onend?.();
  }
  finish() {
    this.onend?.();
  }
}

export function installFakeSpeech(
  name: "SpeechRecognition" | "webkitSpeechRecognition" = "SpeechRecognition",
) {
  FakeRecognizer.instances = [];
  Object.defineProperty(window, name, {
    value: FakeRecognizer,
    configurable: true,
    writable: true,
  });
}

export function removeFakeSpeech() {
  for (const name of ["SpeechRecognition", "webkitSpeechRecognition"]) {
    Reflect.deleteProperty(window, name);
  }
  FakeRecognizer.instances = [];
}
