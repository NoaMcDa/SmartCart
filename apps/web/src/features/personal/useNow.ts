"use client";

import { useEffect, useState } from "react";

/**
 * The current time for rules that count days (buy again, usual). Taken once per mount and again
 * when the tab becomes visible, so a page left open overnight does not keep yesterday's answer.
 */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible") setNow(new Date());
    };
    document.addEventListener("visibilitychange", refresh);
    return () => document.removeEventListener("visibilitychange", refresh);
  }, []);
  return now;
}
