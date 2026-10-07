"use client";

import Link from "next/link";
import { useEffect } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { setTrackingConsent, trackEvent } from "@/features/seo/track";
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
  return (
    <BottomSheet
      open={open}
      onClose={onDecline}
      eyebrow="בטא סגורה"
      title="עוזרות לנו לבדוק את ההחלפות?"
      hideCloseButton
      footer={
        <>
          <Button onClick={onAccept} data-testid="consent-accept">
            אני מסכימה
          </Button>
          <Button variant="secondary" onClick={onDecline} data-testid="consent-decline">
            לא, תודה
          </Button>
        </>
      }
    >
      <div className={styles.body} data-testid="consent-sheet">
        <p>
          כדי לבדוק אם ההחלפות שהמערכת מציעה טובות, נשמרים אצלנו אירועי שימוש בסיסיים בלבד.
          האפליקציה עובדת אותו דבר גם אם תסרבי.
        </p>
        <h3 className={styles.heading}>מה נשמר</h3>
        <ul className={styles.list}>
          <li>מתי נפתחה האפליקציה וכמה זמן לקח להגיע לתוצאות.</li>
          <li>
            כמה החלפות הוצגו, כמה סימנת כ&quot;לא תחליף טוב&quot; ועל איזה זוג מוצרים, ואיזו רמת
            גמישות בחרת.
          </li>
          <li>מזהה אקראי של הדפדפן, ומזהה המשתמש שלך אם התחברת.</li>
        </ul>
        <h3 className={styles.heading}>מה לא נשמר</h3>
        <p>תוכן הרשימה שלך, טקסט חופשי, שם, כתובת, טלפון, מיקום מדויק, קבלות או מזהי מכשיר.</p>
        <p className={styles.muted}>
          המידע נשמר בשרתים של SmartCart בלבד, לא נמכר ולא מועבר לרשתות או לאחרים, ויימחק או יהפוך
          לסטטיסטיקה אנונימית עד שישה חודשים אחרי סוף הבטא. אפשר לצאת בכל רגע{" "}
          <Link href="/profile">בפרופיל</Link> ולבקש למחוק את כל הנתונים.{" "}
          <Link href="/privacy">למדיניות הפרטיות</Link>
        </p>
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
    trackEvent("app_opened", { surface: standalone ? "pwa" : "web" });
  }, [consent]);

  return (
    <ConsentSheet
      open={consent === "unset"}
      onAccept={() => setTrackingConsent(true)}
      onDecline={() => setTrackingConsent(false)}
    />
  );
}
