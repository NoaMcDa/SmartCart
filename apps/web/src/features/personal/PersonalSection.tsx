"use client";

import { useState } from "react";
import { putPersonal, type PersonalData } from "@/api/client";
import { Button, Card, Switch } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useT } from "@/i18n/LocaleProvider";
import { personalMessages } from "@/i18n/messages/personal";
import profileStyles from "@/features/profile/Profile.module.css";
import controls from "@/features/profile/controls/controls.module.css";
import { getPersonal, personalActions, usePersonal } from "./personalState";

/**
 * Profile: "התאמה אישית". Two switches (learn from my shopping, on by default; prefer value packs,
 * off by default), what is kept and where, and "clear what was learned". Learning off stops new
 * records but keeps what exists until it is cleared, and says so.
 */
export function PersonalSection({ className }: { className?: string }) {
  const t = useT(personalMessages);
  const auth = useAuth();
  const { doc } = usePersonal();
  const [status, setStatus] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const signedIn = auth.status === "signed-in";

  async function clear() {
    personalActions.clearLearned();
    setFailed(false);
    setStatus(t("cleared"));
    if (!signedIn) return;
    try {
      ensureApiAuth();
      await putPersonal(getPersonal() as PersonalData);
    } catch {
      setFailed(true);
      setStatus(t("clearFailed"));
    }
  }

  const empty = doc.trips.length === 0 && doc.signals.length === 0 && doc.dismissals.length === 0;

  return (
    <Card as="section" aria-labelledby="personal-heading" className={className}>
      <h2 id="personal-heading" className={profileStyles.sectionTitle}>
        {t("sectionTitle")}
      </h2>
      <div className={controls.stack}>
        <Switch
          label={t("learnLabel")}
          description={t("learnDescription")}
          checked={doc.prefs.learn}
          onChange={(on) => personalActions.setPrefs({ learn: on })}
        />
        {!doc.prefs.learn ? (
          <p className={controls.hint} data-testid="learn-off-note">
            {t("learnOffNote")}
          </p>
        ) : null}
        <Switch
          label={t("packsLabel")}
          description={t("packsDescription")}
          checked={doc.prefs.value_packs}
          onChange={(on) => personalActions.setPrefs({ value_packs: on })}
        />
        <p className={controls.hint} data-testid="personal-stats">
          {t("statsLine", { trips: doc.trips.length, signals: doc.signals.length })}
        </p>
        <p className={controls.hint}>{signedIn ? t("accountNote") : t("localNote")}</p>
        <div className={profileStyles.actions}>
          <Button
            variant="outline"
            size="sm"
            disabled={empty}
            onClick={() => void clear()}
            data-testid="personal-clear"
          >
            {t("clearLearned")}
          </Button>
          <span className={failed ? controls.error : controls.status} role="status">
            {status}
          </span>
        </div>
      </div>
    </Card>
  );
}
