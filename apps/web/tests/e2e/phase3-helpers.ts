/**
 * Helpers for the phase 3 specs (voice, budget, recipe, scan by URL). A fake `SpeechRecognition`
 * is injected on the window before the app loads, the way a browser would provide it, so the
 * voice flow runs in headless Chromium without a microphone.
 */
import type { Page } from "@playwright/test";

type Heard = { text: string; final?: boolean };

/** Defines `window.SpeechRecognition` (and counts `start()` calls in `window.__speechStarts`). */
export async function installFakeSpeech(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    w.__speechStarts = 0;
    class FakeSpeech {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        w.__speechStarts = (w.__speechStarts as number) + 1;
        w.__speech = this;
        setTimeout(() => this.onstart?.(), 0);
      }
      stop() {
        setTimeout(() => this.onend?.(), 0);
      }
      abort() {}
    }
    w.SpeechRecognition = FakeSpeech;
  });
}

/** A browser with no speech recognition at all. */
export async function removeSpeech(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    Object.defineProperty(w, "SpeechRecognition", { value: undefined, configurable: true });
    Object.defineProperty(w, "webkitSpeechRecognition", { value: undefined, configurable: true });
  });
}

/** The recognizer reports these phrases (the whole result list, like a browser in continuous mode). */
export async function hear(page: Page, ...phrases: Heard[]) {
  await page.evaluate((list) => {
    const rec = (window as unknown as { __speech: { onresult: (e: unknown) => void } }).__speech;
    const results = list.map((p) =>
      Object.assign([{ transcript: p.text, confidence: 0.9 }], { isFinal: p.final ?? true }),
    );
    rec.onresult({ resultIndex: 0, results });
  }, phrases);
}

/** The recognizer fails with a Web Speech error code, then ends. */
export async function failSpeech(page: Page, error: string) {
  await page.evaluate((code) => {
    const rec = (
      window as unknown as {
        __speech: { onerror?: ((e: unknown) => void) | null; onend?: (() => void) | null };
      }
    ).__speech;
    // Like a browser: call whatever handler is attached now (the app detaches them once settled).
    rec.onerror?.({ error: code });
    rec.onend?.();
  }, error);
}

export const speechStarts = (page: Page) =>
  page.evaluate(() => (window as unknown as { __speechStarts: number }).__speechStarts);

/** Today's date in Israel, `YYYY-MM-DD`, for seeding spend entries in the current month. */
export function israelToday(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jerusalem" });
}
