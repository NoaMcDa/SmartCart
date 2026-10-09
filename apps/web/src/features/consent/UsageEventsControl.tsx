"use client";

import { useSyncExternalStore } from "react";
import { Switch } from "@/components/ui/Switch";
import { isBetaBuild, isDoNotTrack, setTrackingConsent } from "@/features/seo/track";
import controls from "@/features/profile/controls/controls.module.css";
import { useT } from "@/i18n/LocaleProvider";
import { consentMessages } from "@/i18n/messages/consent";
import { useTrackingConsent } from "./useTrackingConsent";

const noopSubscribe = () => () => {};

/**
 * Profile opt-out for the closed beta's usage events (docs/beta-plan.md section 3). Renders only in
 * a build that collects them; with Do Not Track it says that nothing is collected instead.
 * Turning it off stops events at once and drops what was queued.
 */
export function UsageEventsControl() {
  const t = useT(consentMessages);
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
        {t("dnt")}
      </p>
    );
  }

  return (
    <Switch
      label={t("switchLabel")}
      description={consent === "unset" ? t("descUnset") : t("descSet")}
      checked={consent === "granted"}
      onChange={(on) => setTrackingConsent(on)}
    />
  );
}
