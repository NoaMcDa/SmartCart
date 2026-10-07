"use client";

import { useSyncExternalStore } from "react";
import {
  getTrackingConsent,
  isTrackingAvailable,
  subscribeTrackingConsent,
  type TrackingConsent,
} from "@/features/seo/track";

/** `unavailable`: no beta events in this build, or the browser sends Do Not Track. */
export type ConsentState = TrackingConsent | "unavailable";

function snapshot(): ConsentState {
  return isTrackingAvailable() ? getTrackingConsent() : "unavailable";
}

// Server and first client render agree on "unavailable", so the sheet never flashes in markup.
const serverSnapshot = (): ConsentState => "unavailable";

const subscribe = (listener: () => void) => {
  const off = subscribeTrackingConsent(listener);
  // Another tab may answer the question: the storage event carries it over.
  window.addEventListener("storage", listener);
  return () => {
    off();
    window.removeEventListener("storage", listener);
  };
};

/** The beta-events consent as React state (see `features/seo/track.ts`). */
export function useTrackingConsent(): ConsentState {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot);
}
