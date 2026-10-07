"use client";

import { useEffect } from "react";
import { trackEvent, type EventProps } from "./track";

/** Reports one `page_viewed` event (a no-op unless beta events are switched on, see track.ts). */
export function PageViewTracker({
  pageType,
}: {
  pageType: EventProps["page_viewed"]["page_type"];
}) {
  useEffect(() => {
    trackEvent("page_viewed", { page_type: pageType });
  }, [pageType]);
  return null;
}
