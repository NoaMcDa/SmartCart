"use client";

import Link from "next/link";
import { useState } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import { useAuth } from "@/features/auth/AuthProvider";
import { UsageEventsControl } from "@/features/consent/UsageEventsControl";
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
    });
    setBusy(false);
    setResult(outcome);
    setConfirmOpen(false);
  }

  return (
    <div className={styles.stack}>
      <p className={styles.hint} data-testid="privacy-statement">
        אנחנו לא מוכרים מידע על משתמשים, לא משתפים אותו עם מפרסמים ולא מציגים תוצאות ממומנות. המיקום
        נשמר רק ברמת שכונה ורק באישורך. אין בשירות כלי מעקב או פרסום של צד שלישי.{" "}
        <Link href="/privacy">למדיניות הפרטיות המלאה</Link>
      </p>

      <Switch
        label="שימוש במיקום"
        description="המיקום נשמר מעוגל לשכונה (כ-100 מטר). כיבוי מוחק את המיקום השמור."
        checked={profile.consentLocation}
        onChange={(on) => {
          if (on) updateProfile({ consentLocation: true });
          else clearLocation();
        }}
      />

      <UsageEventsControl />

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
          ייצוא הנתונים שלי
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
          מחקי את הנתונים שלי
        </Button>
      </div>

      {result?.ok ? (
        <p className={styles.status} role="status" data-testid="delete-done">
          הנתונים נמחקו מהמכשיר
          {result.signedIn
            ? `, ${result.listsDeleted} רשימות נמחקו מהחשבון ופרטי הפרופיל אופסו`
            : ""}
          .
          {result.signedIn && !result.accountRowRemains
            ? " החשבון עצמו, כולל כתובת האימייל, נמחק."
            : ""}
        </p>
      ) : null}
      {result?.ok && result.accountRowRemains ? (
        <p className={styles.error} role="alert" data-testid="account-remains">
          הנתונים נמחקו, אבל לא הצלחנו למחוק את החשבון המאוחסן עצמו (כתובת האימייל). התחברי שוב ונסי
          שוב מהפרופיל.
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
        title="למחוק את כל הנתונים שלי?"
        eyebrow="אי אפשר לבטל"
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              ביטול
            </Button>
            <Button tone="bad" disabled={busy} onClick={confirmDelete} data-testid="confirm-delete">
              {busy ? "מוחקת…" : "כן, למחוק"}
            </Button>
          </>
        }
      >
        <p className={styles.hint}>
          יימחקו מהמכשיר: המיקום, הרשת והמועדונים, העדפות הכשרות והתזונה, ברירות המחדל, תוצאת
          ההשוואה האחרונה, הקנייה הפעילה והחיסכון שנצבר.
        </p>
        {auth.status === "signed-in" ? (
          <p className={styles.hint}>
            וגם מהחשבון: כל הרשימות השמורות, פרטי הפרופיל והחשבון עצמו, כולל כתובת האימייל. בסיום
            תתנתקי.
          </p>
        ) : null}
      </BottomSheet>
    </div>
  );
}
