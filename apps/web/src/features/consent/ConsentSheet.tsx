"use client";

import Link from "next/link";
import { useEffect } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { setTrackingConsent, trackEvent } from "@/features/seo/track";
import { formatRich } from "@/i18n/format";
import { LegalNotice } from "@/i18n/LegalNotice";
import { useT } from "@/i18n/LocaleProvider";
import { consentMessages } from "@/i18n/messages/consent";
import { detectPlatform } from "@/lib/platform";
import styles from "./Consent.module.css";
import { useTrackingConsent } from "./useTrackingConsent";

/**
 * First-party beta usage events (issue #40, docs/beta-plan.md section 3). The wording follows the
 * proposed consent text there; it has NOT had a legal review, and the six-month retention is a
 * proposal. Answers are stored in localStorage["sc-events-consent"] ("1" accepted, "0" declined),
 * which is also what makes the sheet appear once.
 */
export function ConsentSheet({
  open,
  onAccept,
  onDecline,
}: {
  open: boolean;
  onAccept: () => void;
  onDecline: () => void;
}) {
  const t = useT(consentMessages);
  return (
    <BottomSheet
      open={open}
      onClose={onDecline}
      eyebrow={t("eyebrow")}
      title={t("title")}
      hideCloseButton
      footer={
        <>
          <Button onClick={onAccept} data-testid="consent-accept">
            {t("accept")}
          </Button>
          <Button variant="secondary" onClick={onDecline} data-testid="consent-decline">
            {t("decline")}
          </Button>
        </>
      }
    >
      <div className={styles.body} data-testid="consent-sheet">
        <p>{t("intro")}</p>
        <h3 className={styles.heading}>{t("storedHeading")}</h3>
        <ul className={styles.list}>
          <li>{t("stored1")}</li>
          <li>{t("stored2")}</li>
          <li>{t("stored3")}</li>
        </ul>
        <h3 className={styles.heading}>{t("notStoredHeading")}</h3>
        <p>{t("notStored")}</p>
        <p className={styles.muted}>
          {formatRich(t("footerNote"), {
            profile: <Link href="/profile">{t("profileLink")}</Link>,
            policy: <Link href="/privacy">{t("policyLink")}</Link>,
          })}
        </p>
        <LegalNotice />
      </div>
    </BottomSheet>
  );
}

let openedThisVisit = false;

/** Test hook: forget that `app_opened` was already reported on this page load. */
export function resetConsentGateForTests(): void {
  openedThisVisit = false;
}

/**
 * Mounted once in the app shell. Shows the consent sheet the first time (only when this build
 * collects beta events and the browser does not send Do Not Track), and reports `app_opened` once
 * per visit once the person has accepted.
 */
export function ConsentGate() {
  const consent = useTrackingConsent();

  useEffect(() => {
    if (consent !== "granted" || openedThisVisit) return;
    openedThisVisit = true;
    const standalone =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(display-mode: standalone)").matches;
    trackEvent("app_opened", { surface: standalone ? "pwa" : "web", platform: detectPlatform() });
  }, [consent]);

  return (
    <ConsentSheet
      open={consent === "unset"}
      onAccept={() => setTrackingConsent(true)}
      onDecline={() => setTrackingConsent(false)}
    />
  );
}
