"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { IconBell, IconCheck, IconInfo } from "@/components/ui/icons";
import {
  currentSubscription,
  disablePush,
  enablePush,
  PUSH_MESSAGES,
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
    if (!result.ok) setFailure(PUSH_MESSAGES[result.reason]);
    setInfo(await readInfo());
    setBusy(false);
  }, []);

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
        <IconInfo size={15} /> {PUSH_MESSAGES[info.support]}
      </p>
    );
  } else if (info.permission === "denied") {
    body = (
      <p className={styles.note} data-testid="push-denied">
        <IconInfo size={15} /> {PUSH_MESSAGES.denied}
      </p>
    );
  } else if (info.subscribed) {
    body = (
      <div className={styles.pushRow}>
        <p className={styles.ok} data-testid="push-on">
          <IconCheck size={15} /> התראות בדפדפן פעילות במכשיר הזה.
        </p>
        <Button variant="outline" size="sm" onClick={() => void turnOff()} disabled={busy}>
          כיבוי במכשיר הזה
        </Button>
      </div>
    );
  } else {
    body = (
      <div className={styles.pushRow}>
        <p className={styles.note}>
          נשלח התראה למכשיר כשמוצר יורד מתחת למחיר שקבעת. הדפדפן יבקש אישור כשתלחצי על הכפתור.
        </p>
        <Button
          size="sm"
          iconStart={<IconBell size={16} />}
          onClick={() => void turnOn()}
          disabled={busy}
        >
          הפעלת התראות בדפדפן
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
