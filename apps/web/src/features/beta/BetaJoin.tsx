"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError, joinBeta, leaveBeta, type BetaSegment } from "@/api/client";
import { Button, Card } from "@/components/ui";
import { IconCheck, IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { ConsentSheet } from "@/features/consent/ConsentSheet";
import { useTrackingConsent } from "@/features/consent/useTrackingConsent";
import { setTrackingConsent } from "@/features/seo/track";
import { useT } from "@/i18n/LocaleProvider";
import { betaMessages } from "@/i18n/messages/beta";
import { BetaFeedbackSheet } from "./BetaFeedback";
import styles from "./Beta.module.css";
import { setBetaMembership } from "./betaState";
import { useBetaMembership } from "./useBetaMembership";

type Translate = ReturnType<typeof useT<keyof typeof betaMessages.he>>;
type Phase = "idle" | "consent" | "joining" | "leaving" | "left";

const SEGMENT_KEYS = {
  large_family: "seg_large_family",
  kosher: "seg_kosher",
  periphery: "seg_periphery",
  general: "seg_general",
} as const satisfies Record<BetaSegment, keyof typeof betaMessages.he>;

/** What to tell the person when joining failed (`POST /beta/join`). */
export function joinErrorMessage(err: unknown, t: Translate): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return t("errUnknown");
    if (err.status === 410) return t("errExpired");
    if (err.status === 401) return t("errSignIn");
    return t("errGeneric");
  }
  return t("errOffline");
}

/**
 * `/beta/join/<code>` and `/beta`: explains the closed beta in plain Hebrew (what is measured, the
 * usage-events consent, what is stored, how to leave), signs the person in if needed, and joins
 * with the invite code on a tap, never automatically. Joining shows the events-consent screen
 * first when it has not been answered. Members see their group, the feedback entry, and "leave the
 * beta", which deletes the member row (`DELETE /me/beta`) and turns usage events off.
 */
export function BetaJoin({ code }: { code?: string }) {
  const t = useT(betaMessages);
  const auth = useAuth();
  const beta = useBetaMembership();
  const consent = useTrackingConsent();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";
  const waiting = phase === "idle" && !beta.member && !needsSignIn && beta.status !== "ready";

  async function join() {
    if (!code) return;
    setPhase("joining");
    setError(null);
    try {
      ensureApiAuth();
      const res = await joinBeta(code);
      setBetaMembership(res.member, res.segment ?? null);
      setPhase("idle");
    } catch (err) {
      setError(joinErrorMessage(err, t));
      setPhase("idle");
    }
  }

  function onJoinClick() {
    // The usage-events question is part of joining: ask it first when it was not answered yet.
    if (consent === "unset") setPhase("consent");
    else void join();
  }

  async function leave() {
    setPhase("leaving");
    setError(null);
    try {
      ensureApiAuth();
      await leaveBeta();
      setTrackingConsent(false);
      setBetaMembership(false, null);
      setConfirmLeave(false);
      setPhase("left");
    } catch {
      setError(t("errLeave"));
      setPhase("idle");
    }
  }

  const segmentName = beta.segment ? t(SEGMENT_KEYS[beta.segment]) : "";

  return (
    <div className={styles.page}>
      <Card as="section" aria-labelledby="beta-state" data-testid="beta-state">
        <div className={styles.section}>
          {phase === "left" ? (
            <>
              <h2 id="beta-state" className={styles.heading}>
                {t("leftTitle")}
              </h2>
              <p role="status" data-testid="beta-left">
                {t("leftBody")}
              </p>
              <Link href="/profile">{t("profileLink")}</Link>
            </>
          ) : beta.member ? (
            <>
              <h2 id="beta-state" className={styles.heading}>
                {t("memberTitle")}
              </h2>
              <p data-testid="beta-member">{t("memberBody", { segment: segmentName })}</p>
              {consent !== "unavailable" ? (
                <p className={styles.note}>
                  <IconInfo size={15} />
                  <span>{consent === "granted" ? t("memberEventsOn") : t("memberEventsOff")}</span>
                </p>
              ) : null}
              <div className={styles.actions}>
                <Button onClick={() => setFeedbackOpen(true)} data-testid="beta-open-feedback">
                  {t("feedbackButton")}
                </Button>
                {confirmLeave ? null : (
                  <Button
                    variant="outline"
                    tone="bad"
                    onClick={() => setConfirmLeave(true)}
                    data-testid="beta-leave"
                  >
                    {t("leaveButton")}
                  </Button>
                )}
              </div>
              {confirmLeave ? (
                <div className={styles.confirm} role="group" aria-label={t("leaveButton")}>
                  <p>{t("leaveConfirm")}</p>
                  <div className={styles.actions}>
                    <Button
                      variant="outline"
                      tone="bad"
                      disabled={phase === "leaving"}
                      onClick={() => void leave()}
                      data-testid="beta-leave-confirm"
                    >
                      {phase === "leaving" ? t("leaving") : t("leaveYes")}
                    </Button>
                    <Button variant="outline" onClick={() => setConfirmLeave(false)}>
                      {t("leaveCancel")}
                    </Button>
                  </div>
                </div>
              ) : null}
            </>
          ) : waiting ? (
            <>
              <h2 id="beta-state" className={styles.heading}>
                {t("joinTitle")}
              </h2>
              <p role="status">{t("loading")}</p>
            </>
          ) : code ? (
            <>
              <h2 id="beta-state" className={styles.heading}>
                {t("joinTitle")}
              </h2>
              {needsSignIn ? (
                <>
                  <p className={styles.note}>
                    <IconInfo size={15} />
                    <span>{t("signInNote")}</span>
                  </p>
                  <Button onClick={auth.openSignIn} data-testid="beta-sign-in">
                    {t("signInButton")}
                  </Button>
                </>
              ) : (
                <Button
                  onClick={onJoinClick}
                  disabled={phase === "joining" || auth.status === "loading"}
                  data-testid="beta-join"
                  iconStart={<IconCheck size={16} />}
                >
                  {phase === "joining" ? t("joining") : t("joinButton")}
                </Button>
              )}
            </>
          ) : (
            <>
              <h2 id="beta-state" className={styles.heading}>
                {t("noInviteTitle")}
              </h2>
              <p data-testid="beta-no-invite">{t("noInvite")}</p>
            </>
          )}
          {error ? (
            <p className={styles.error} role="alert" data-testid="beta-error">
              {error}
            </p>
          ) : null}
        </div>
      </Card>

      <Card as="section" aria-labelledby="beta-about">
        <div className={styles.section}>
          <h2 id="beta-about" className={styles.heading}>
            {t("introTitle")}
          </h2>
          <p>{t("intro")}</p>
          <h3 className={styles.heading}>{t("measuredTitle")}</h3>
          <ul className={styles.list}>
            <li>{t("measured1")}</li>
            <li>{t("measured2")}</li>
            <li>{t("measured3")}</li>
          </ul>
        </div>
      </Card>

      <Card as="section" aria-labelledby="beta-privacy">
        <div className={styles.section}>
          <h2 id="beta-privacy" className={styles.heading}>
            {t("eventsTitle")}
          </h2>
          <p>{t("events")}</p>
          <h3 className={styles.heading}>{t("storedTitle")}</h3>
          <p>{t("stored")}</p>
          <h3 className={styles.heading}>{t("feedbackNoteTitle")}</h3>
          <p>{t("feedbackNote")}</p>
          <h3 className={styles.heading}>{t("leaveInfoTitle")}</h3>
          <p>{t("leaveInfo")}</p>
          <p className={styles.links}>
            <Link href="/profile">{t("profileLink")}</Link>
            <Link href="/privacy">{t("privacyLink")}</Link>
          </p>
        </div>
      </Card>

      <ConsentSheet
        open={phase === "consent"}
        onAccept={() => {
          setTrackingConsent(true);
          void join();
        }}
        onDecline={() => {
          setTrackingConsent(false);
          void join();
        }}
      />
      <BetaFeedbackSheet open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </div>
  );
}
