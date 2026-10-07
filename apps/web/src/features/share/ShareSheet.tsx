"use client";

import { useRef, useState } from "react";
import { ApiError, revokeShare, shareList, type ShareInvite, type ShareRole } from "@/api/client";
import { BottomSheet, Button, SegmentedControl } from "@/components/ui";
import { IconCheck, IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import controls from "@/features/profile/controls/controls.module.css";
import styles from "./Share.module.css";

export const ROLE_LABEL: Record<ShareRole, string> = {
  editor: "עריכה",
  viewer: "צפייה בלבד",
};

/** The invite as a link the recipient can open. The API may return a path or a full address. */
export function inviteLink(invite: Pick<ShareInvite, "url">, origin: string): string {
  return /^https?:\/\//i.test(invite.url) ? invite.url : `${origin}${invite.url}`;
}

export function shareError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "צריך להתחבר כדי לשתף רשימה.";
    if (err.status === 402 || err.status === 403) {
      return "שיתוף משפחתי הוא חלק מהמנוי, או שהרשימה הזו לא שלך.";
    }
    if (err.status === 404) return "הרשימה לא נמצאה.";
    return "השרת החזיר שגיאה. נסי שוב בעוד רגע.";
  }
  return "נראה שאין חיבור לשרת. בדקי את החיבור ונסי שוב.";
}

/**
 * Share sheet (issue #34): pick what the invited person may do, create an invite link, copy it or
 * pass it to the phone's share menu. Members see only the list: never each other's location or
 * preferences. The owner can cancel the link (`DELETE /me/lists/{id}/share/{token}`); removing a member is on the
 * members list.
 */
export function ShareSheet({
  open,
  onClose,
  listId,
  onInvited,
}: {
  open: boolean;
  onClose: () => void;
  listId: number;
  onInvited?: () => void;
}) {
  const auth = useAuth();
  const [role, setRole] = useState<ShareRole>("editor");
  const [invite, setInvite] = useState<ShareInvite | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revoked, setRevoked] = useState(false);
  const linkRef = useRef<HTMLInputElement>(null);
  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";
  const link =
    invite && typeof window !== "undefined" ? inviteLink(invite, window.location.origin) : "";

  async function create() {
    setBusy(true);
    setError(null);
    setCopied(false);
    setRevoked(false);
    try {
      ensureApiAuth();
      setInvite(await shareList(listId, role));
      onInvited?.();
    } catch (err) {
      setError(shareError(err));
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (!invite) return;
    setBusy(true);
    setError(null);
    try {
      ensureApiAuth();
      await revokeShare(listId, invite.token);
      setInvite(null);
      setCopied(false);
      setRevoked(true);
      onInvited?.();
    } catch (err) {
      setError(shareError(err));
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    let ok = false;
    try {
      await navigator.clipboard.writeText(link);
      ok = true;
    } catch {
      // Clipboard API refused (permissions, insecure context): select the field and let the user copy.
      const el = linkRef.current;
      if (el) {
        el.focus();
        el.select();
        try {
          ok = document.execCommand("copy");
        } catch {
          ok = false;
        }
      }
    }
    setCopied(ok);
    if (!ok) setError("לא הצלחנו להעתיק אוטומטית. סימנו את הקישור, אפשר להעתיק אותו ידנית.");
  }

  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  return (
    <BottomSheet open={open} onClose={onClose} title="הזמנת בני משפחה" eyebrow="שיתוף הרשימה">
      <div className={controls.stack}>
        <p className={controls.hint}>
          מי שתקבל את הקישור תתחבר, תצטרף ותראה את הרשימה ואת השינויים בה בזמן אמת. היא לא רואה את
          המיקום או ההעדפות שלך.
        </p>

        {needsSignIn ? (
          <>
            <p className={styles.note}>
              <IconInfo size={15} /> כדי לשתף צריך להתחבר, כך שרק מי שהוזמנה תגיע לרשימה.
            </p>
            <Button onClick={auth.openSignIn}>התחברות</Button>
          </>
        ) : (
          <>
            <SegmentedControl<ShareRole>
              label="הרשאה למוזמנת"
              value={role}
              onChange={(r) => {
                setRole(r);
                setInvite(null);
              }}
              options={[
                { value: "editor", label: ROLE_LABEL.editor },
                { value: "viewer", label: ROLE_LABEL.viewer },
              ]}
            />
            {invite ? (
              <div className={controls.field} data-testid="invite">
                <label htmlFor="invite-link" className={controls.label}>
                  קישור הזמנה ({ROLE_LABEL[invite.role]})
                </label>
                <input
                  id="invite-link"
                  ref={linkRef}
                  className={controls.input}
                  readOnly
                  dir="ltr"
                  value={link}
                  onFocus={(e) => e.currentTarget.select()}
                />
                <div className={styles.row}>
                  <Button onClick={() => void copy()}>העתקת הקישור</Button>
                  {canNativeShare ? (
                    <Button
                      variant="outline"
                      onClick={() =>
                        void navigator
                          .share({ title: "רשימת קניות ב-SmartCart", url: link })
                          .catch(() => undefined)
                      }
                    >
                      שיתוף בטלפון
                    </Button>
                  ) : null}
                  <Button variant="ghost" onClick={() => void revoke()} disabled={busy}>
                    ביטול הקישור
                  </Button>
                </div>
              </div>
            ) : (
              <Button onClick={() => void create()} disabled={busy}>
                {busy ? "יוצרת קישור…" : "יצירת קישור הזמנה"}
              </Button>
            )}
          </>
        )}

        <div role="status" aria-live="polite">
          {revoked ? (
            <p className={styles.ok} data-testid="invite-revoked">
              <IconCheck size={15} /> הקישור בוטל. מי שקיבלה אותו לא תוכל להצטרף, ומי שכבר הצטרפה
              איבדה גישה.
            </p>
          ) : null}
          {copied ? (
            <p className={styles.ok} data-testid="invite-copied">
              <IconCheck size={15} /> הקישור הועתק.
            </p>
          ) : null}
        </div>
        {error ? (
          <p className={controls.error} role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </BottomSheet>
  );
}
