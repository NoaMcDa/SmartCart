"use client";

import { useRef, useState } from "react";
import { ApiError, revokeShare, shareList, type ShareInvite, type ShareRole } from "@/api/client";
import { BottomSheet, Button, SegmentedControl } from "@/components/ui";
import { IconCheck, IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { reportListShared } from "@/features/consent/betaEvents";
import controls from "@/features/profile/controls/controls.module.css";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import type { Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { shareMessages, type ShareMessageKey } from "@/i18n/messages/share";
import styles from "./Share.module.css";

/** Message key (`shareMessages`) of a role's label. */
export const ROLE_KEY = { editor: "roleEditor", viewer: "roleViewer" } as const satisfies Record<
  ShareRole,
  "roleEditor" | "roleViewer"
>;

/** The invite as a link the recipient can open. The API may return a path or a full address. */
export function inviteLink(invite: Pick<ShareInvite, "url">, origin: string): string {
  return /^https?:\/\//i.test(invite.url) ? invite.url : `${origin}${invite.url}`;
}

export function shareError(err: unknown, locale: Locale = "he"): string {
  const t = (key: ShareMessageKey) => translate(shareMessages, locale, key);
  if (err instanceof ApiError) {
    if (err.status === 401) return t("errShareSignIn");
    if (err.status === 402 || err.status === 403) return t("errShareForbidden");
    if (err.status === 404) return t("errShareNotFound");
    return t("errServer");
  }
  return t("errOffline");
}

/**
 * Share sheet (issue #34): pick what the invited person may do, create an invite link, copy it or
 * pass it to the phone's share menu. Members see only the list: never each other's location or
 * preferences. The owner can cancel the link (`DELETE /me/lists/{id}/share/{token}`); removing a member is on the
 * members list.
 */
export function ShareSheet(props: {
  open: boolean;
  onClose: () => void;
  listId: number;
  onInvited?: () => void;
}) {
  // Mounted only while open, so a link made in one visit is not shown in the next: it may have
  // been cancelled from the members list in between.
  return props.open ? <ShareSheetContent {...props} /> : null;
}

function ShareSheetContent({
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
  const t = useT(shareMessages);
  const { locale } = useLocale();
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
      const created = await shareList(listId, role);
      setInvite(created);
      reportListShared(created.role);
      onInvited?.();
    } catch (err) {
      setError(shareError(err, locale));
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
      setError(shareError(err, locale));
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
    if (!ok) setError(t("copyFailed"));
  }

  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={t("inviteFamily")}
      eyebrow={t("sheetEyebrow")}
    >
      <div className={controls.stack}>
        <p className={controls.hint}>{t("sheetHint")}</p>

        {needsSignIn ? (
          <>
            <p className={styles.note}>
              <IconInfo size={15} /> {t("shareSignInNote")}
            </p>
            <Button onClick={auth.openSignIn}>{t("signIn")}</Button>
          </>
        ) : (
          <>
            <SegmentedControl<ShareRole>
              label={t("permissionLabel")}
              value={role}
              onChange={(r) => {
                setRole(r);
                setInvite(null);
              }}
              options={[
                { value: "editor", label: t(ROLE_KEY.editor) },
                { value: "viewer", label: t(ROLE_KEY.viewer) },
              ]}
            />
            {invite ? (
              <div className={controls.field} data-testid="invite">
                <label htmlFor="invite-link" className={controls.label}>
                  {t("inviteLinkLabel", { role: t(ROLE_KEY[invite.role]) })}
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
                  <Button onClick={() => void copy()}>{t("copyLink")}</Button>
                  {canNativeShare ? (
                    <Button
                      variant="outline"
                      onClick={() =>
                        void navigator
                          .share({ title: t("nativeShareTitle"), url: link })
                          .catch(() => undefined)
                      }
                    >
                      {t("shareOnPhone")}
                    </Button>
                  ) : null}
                  <Button variant="ghost" onClick={() => void revoke()} disabled={busy}>
                    {t("revokeLink")}
                  </Button>
                </div>
              </div>
            ) : (
              <Button onClick={() => void create()} disabled={busy}>
                {busy ? t("creatingLink") : t("createLink")}
              </Button>
            )}
          </>
        )}

        <div role="status" aria-live="polite">
          {revoked ? (
            <p className={styles.ok} data-testid="invite-revoked">
              <IconCheck size={15} /> {t("linkRevoked")}
            </p>
          ) : null}
          {copied ? (
            <p className={styles.ok} data-testid="invite-copied">
              <IconCheck size={15} /> {t("linkCopied")}
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
