/**
 * One-shot status message carried across a client navigation ("we kept the original, the basket
 * was recomputed"). The next screen shows it in a polite live region and clears it.
 */
import { useSyncExternalStore } from "react";

let message: string | null = null;
const listeners = new Set<() => void>();

export function setFlash(text: string | null) {
  message = text;
  listeners.forEach((l) => l());
}

export function useFlash(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    () => message,
    () => null,
  );
}
