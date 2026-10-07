"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { acceptShare, ApiError } from "@/api/client";
import { Button, Card } from "@/components/ui";
import { IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { rememberJoined } from "./sharedLists";
import styles from "./Share.module.css";

export function acceptError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "צריך להתחבר כדי להצטרף לרשימה.";
    if (err.status === 404 || err.status === 410 || err.status === 403) {
      return "הקישור לא תקף: ייתכן שפג תוקפו או שהבעלים ביטלה אותו. בקשי קישור חדש.";
    }
    return "השרת החזיר שגיאה. נסי שוב בעוד רגע.";
  }
  return "נראה שאין חיבור לשרת. בדקי את החיבור ונסי שוב.";
}

/**
 * `/lists/accept/<token>`: the page behind an invite link. Joining is a tap, never automatic, so
 * opening a link by accident changes nothing. Joining needs a signed-in user (the API ties the
 * membership to the account); after joining, the list opens.
 */
export function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const auth = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";

  async function join() {
    setBusy(true);
    setError(null);
    try {
      ensureApiAuth();
      const list = await acceptShare(token);
      rememberJoined({ id: list.id, name: list.name });
      router.push(`/lists/${list.id}/share`);
    } catch (err) {
      setError(acceptError(err));
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <Card as="section" aria-labelledby="accept-heading" data-testid="accept">
        <h2 id="accept-heading" className={styles.sectionTitle}>
          הוזמנת לרשימת קניות משותפת
        </h2>
        <p>
          אחרי ההצטרפות תראי את הרשימה ואת השינויים בה בזמן אמת. מי שהזמינה אותך תראה שהצטרפת, אבל
          לא תראה את המיקום או ההעדפות שלך.
        </p>
        {needsSignIn ? (
          <>
            <p className={styles.note}>
              <IconInfo size={15} /> כדי להצטרף צריך להתחבר, כך שהרשימה נשמרת בחשבון שלך.
            </p>
            <Button onClick={auth.openSignIn}>התחברות</Button>
          </>
        ) : (
          <Button onClick={() => void join()} disabled={busy || auth.status === "loading"}>
            {busy ? "מצטרפת…" : "הצטרפות לרשימה"}
          </Button>
        )}
        {error ? (
          <p className={styles.error} role="alert" data-testid="accept-error">
            {error}
          </p>
        ) : null}
      </Card>
    </div>
  );
}
