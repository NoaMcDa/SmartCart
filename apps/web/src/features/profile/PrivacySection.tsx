"use client";

import Link from "next/link";
import { useState } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import { useAuth } from "@/features/auth/AuthProvider";
import { UsageEventsControl } from "@/features/consent/UsageEventsControl";
import { BetaFeedbackEntry } from "@/features/beta";
import { ImageConsentToggle } from "@/features/photo/ImageConsentToggle";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import { deleteMyData, type DeleteResult } from "./deleteData";
import { loadSavings } from "./savingsHistory";
import { clearLocation, getProfile, updateProfile, useProfile } from "./profileState";
import styles from "./controls/controls.module.css";
import profileStyles from "./Profile.module.css";

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}

/** Privacy statement, consent toggles, export and "מחקי את הנתונים שלי" (issue #30). */
export function PrivacySection() {
  const t = useT(profileMessages);
  const { locale } = useLocale();
  const profile = useProfile();
  const auth = useAuth();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DeleteResult | null>(null);

  async function confirmDelete() {
    setBusy(true);
    const outcome = await deleteMyData({
      signedIn: auth.status === "signed-in",
      signOut: auth.signOut,
      locale,
    });
    setBusy(false);
    setResult(outcome);
    setConfirmOpen(false);
  }

  return (
    <div className={styles.stack}>
      <p className={styles.hint} data-testid="privacy-statement">
        {t("privacyStatement")} <Link href="/privacy">{t("privacyPolicyLink")}</Link>
      </p>

      <Switch
        label={t("locationUseLabel")}
        description={t("locationUseDescription")}
        checked={profile.consentLocation}
        onChange={(on) => {
          if (on) updateProfile({ consentLocation: true });
          else clearLocation();
        }}
      />

      <UsageEventsControl />

      <BetaFeedbackEntry />

      <ImageConsentToggle />

      <div className={profileStyles.actions}>
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            downloadJson("smartcart-my-data.json", {
              exportedAt: new Date().toISOString(),
              profile: getProfile(),
              savings: loadSavings(),
            })
          }
        >
          {t("exportData")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          tone="bad"
          onClick={() => {
            setResult(null);
            setConfirmOpen(true);
          }}
        >
          {t("deleteData")}
        </Button>
      </div>

      {result?.ok ? (
        <p className={styles.status} role="status" data-testid="delete-done">
          {result.signedIn
            ? t("deletedDeviceAndAccount", { count: result.listsDeleted })
            : t("deletedDevice")}
          {result.signedIn && !result.accountRowRemains ? t("accountDeleted") : ""}
        </p>
      ) : null}
      {result?.ok && result.accountRowRemains ? (
        <p className={styles.error} role="alert" data-testid="account-remains">
          {t("accountRemains")}
        </p>
      ) : null}
      {result && !result.ok ? (
        <p className={styles.error} role="alert">
          {result.error}
        </p>
      ) : null}

      <BottomSheet
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={t("confirmTitle")}
        eyebrow={t("confirmEyebrow")}
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {t("cancel")}
            </Button>
            <Button tone="bad" disabled={busy} onClick={confirmDelete} data-testid="confirm-delete">
              {busy ? t("deleting") : t("confirmDelete")}
            </Button>
          </>
        }
      >
        <p className={styles.hint}>{t("deviceDeleteBody")}</p>
        {auth.status === "signed-in" ? (
          <p className={styles.hint}>{t("accountDeleteBody")}</p>
        ) : null}
      </BottomSheet>
    </div>
  );
}
