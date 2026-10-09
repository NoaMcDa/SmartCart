"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { acceptShare, ApiError } from "@/api/client";
import { Button, Card } from "@/components/ui";
import { IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { reportShareAccepted } from "@/features/consent/betaEvents";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import type { Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { shareMessages, type ShareMessageKey } from "@/i18n/messages/share";
import { rememberJoined } from "./sharedLists";
import styles from "./Share.module.css";

export function acceptError(err: unknown, locale: Locale = "he"): string {
  const t = (key: ShareMessageKey) => translate(shareMessages, locale, key);
  if (err instanceof ApiError) {
    if (err.status === 401) return t("errAcceptSignIn");
    if (err.status === 404 || err.status === 410 || err.status === 403) {
      return t("errAcceptInvalid");
    }
    return t("errServer");
  }
  return t("errOffline");
}

/**
 * `/lists/accept/<token>`: the page behind an invite link. Joining is a tap, never automatic, so
 * opening a link by accident changes nothing. Joining needs a signed-in user (the API ties the
 * membership to the account); after joining, the list opens.
 */
export function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const auth = useAuth();
  const t = useT(shareMessages);
  const { locale } = useLocale();
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
      reportShareAccepted();
      router.push(`/lists/${list.id}/share`);
    } catch (err) {
      setError(acceptError(err, locale));
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <Card as="section" aria-labelledby="accept-heading" data-testid="accept">
        <h2 id="accept-heading" className={styles.sectionTitle}>
          {t("acceptHeading")}
        </h2>
        <p>{t("acceptBody")}</p>
        {needsSignIn ? (
          <>
            <p className={styles.note}>
              <IconInfo size={15} /> {t("acceptSignInNote")}
            </p>
            <Button onClick={auth.openSignIn}>{t("signIn")}</Button>
          </>
        ) : (
          <Button onClick={() => void join()} disabled={busy || auth.status === "loading"}>
            {busy ? t("joining") : t("join")}
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
