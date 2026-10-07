"use client";

import { useSyncExternalStore } from "react";
import { Switch } from "@/components/ui/Switch";
import { isBetaBuild, isDoNotTrack, setTrackingConsent } from "@/features/seo/track";
import controls from "@/features/profile/controls/controls.module.css";
import { useTrackingConsent } from "./useTrackingConsent";

const noopSubscribe = () => () => {};

/**
 * Profile opt-out for the closed beta's usage events (docs/beta-plan.md section 3). Renders only in
 * a build that collects them; with Do Not Track it says that nothing is collected instead.
 * Turning it off stops events at once and drops what was queued.
 */
export function UsageEventsControl() {
  const consent = useTrackingConsent();
  // Server render and first client render show nothing; the real answer arrives after hydration.
  const client = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
  if (!client || !isBetaBuild()) return null;

  if (isDoNotTrack()) {
    return (
      <p className={controls.hint} data-testid="usage-events-dnt">
        הדפדפן שלך שולח אות &quot;Do Not Track&quot;, ולכן לא נשמרים אירועי שימוש מהבטא.
      </p>
    );
  }

  return (
    <Switch
      label="אירועי שימוש לבדיקת הבטא"
      description={
        consent === "unset"
          ? "עוד לא ענית. כל עוד לא אישרת, לא נשמר דבר. נשמרים רק אירועים בסיסיים, בלי תוכן הרשימה."
          : "נשמרים רק אירועים בסיסיים, בלי תוכן הרשימה ובלי טקסט חופשי. כיבוי עוצר את השליחה מיד."
      }
      checked={consent === "granted"}
      onChange={(on) => setTrackingConsent(on)}
    />
  );
}
