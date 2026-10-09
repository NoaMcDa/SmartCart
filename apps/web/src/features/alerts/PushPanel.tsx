"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { IconBell, IconCheck, IconInfo } from "@/components/ui/icons";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { alertMessages } from "@/i18n/messages/alerts";
import {
  currentSubscription,
  disablePush,
  enablePush,
  pushMessage,
  pushPermission,
  pushSupport,
  type PushPermission,
  type PushSupport,
} from "./push";
import styles from "./Alerts.module.css";

type Info = { support: PushSupport; permission: PushPermission; subscribed: boolean };

async function readInfo(): Promise<Info> {
  const support = pushSupport();
  const permission = pushPermission();
  const subscribed =
    support === "supported" && permission === "granted" && (await currentSubscription()) !== null;
  return { support, permission, subscribed };
}

/**
 * "Notify me in the browser": explains what push needs, asks only after a tap, and says clearly
 * when it is blocked, unsupported, not configured, or needs the iOS home-screen install. Denying
 * or revoking permission never breaks alerts: they stay listed on /alerts.
 */
export function PushPanel() {
  const t = useT(alertMessages);
  const { locale } = useLocale();
  const [info, setInfo] = useState<Info | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void readInfo().then((i) => {
      if (!cancelled) setInfo(i);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const turnOn = useCallback(async () => {
    setBusy(true);
    setFailure(null);
    const result = await enablePush();
    if (!result.ok) setFailure(pushMessage(result.reason, locale));
    setInfo(await readInfo());
    setBusy(false);
  }, [locale]);

  const turnOff = useCallback(async () => {
    setBusy(true);
    await disablePush();
    setInfo(await readInfo());
    setBusy(false);
  }, []);

  if (!info) return null;

  let body;
  if (info.support !== "supported") {
    body = (
      <p className={styles.note} data-testid="push-unavailable">
        <IconInfo size={15} /> {pushMessage(info.support, locale)}
      </p>
    );
  } else if (info.permission === "denied") {
    body = (
      <p className={styles.note} data-testid="push-denied">
        <IconInfo size={15} /> {pushMessage("denied", locale)}
      </p>
    );
  } else if (info.subscribed) {
    body = (
      <div className={styles.pushRow}>
        <p className={styles.ok} data-testid="push-on">
          <IconCheck size={15} /> {t("pushOn")}
        </p>
        <Button variant="outline" size="sm" onClick={() => void turnOff()} disabled={busy}>
          {t("pushOff")}
        </Button>
      </div>
    );
  } else {
    body = (
      <div className={styles.pushRow}>
        <p className={styles.note}>{t("pushExplain")}</p>
        <Button
          size="sm"
          iconStart={<IconBell size={16} />}
          onClick={() => void turnOn()}
          disabled={busy}
        >
          {t("pushTurnOn")}
        </Button>
      </div>
    );
  }

  return (
    <div className={styles.push} data-testid="push-panel">
      {body}
      {failure ? (
        <p className={styles.note} role="alert">
          <IconInfo size={15} /> {failure}
        </p>
      ) : null}
    </div>
  );
}
