"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteAlert, listAlerts, updateAlert, type PriceAlert } from "@/api/client";
import { Button, Card, FlexChip, Price, Skeleton, Tag, UpdatedAt } from "@/components/ui";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { alertLabel } from "./alertNames";
import { alertError } from "./AlertMe";
import { alertBody, EditAlertSheet } from "./EditAlertSheet";
import { PushPanel } from "./PushPanel";
import styles from "./Alerts.module.css";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; alerts: PriceAlert[] };

async function fetchAlerts(): Promise<State> {
  try {
    ensureApiAuth();
    return { kind: "ready", alerts: await listAlerts() };
  } catch (err) {
    return { kind: "error", message: alertError(err) };
  }
}

/**
 * /alerts (issue #23): every alert of the signed-in user, with the product, the target unit price,
 * the flexibility level and the radius, edit, pause, delete, and the browser push switch. Product names come
 * from what the device remembered when the alert was created.
 */
export function AlertsScreen() {
  const auth = useAuth();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<PriceAlert | null>(null);
  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";
  const waiting = auth.configured && auth.status === "loading";

  useEffect(() => {
    if (needsSignIn || waiting) return;
    let cancelled = false;
    void fetchAlerts().then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, [needsSignIn, waiting]);

  function retry() {
    setState({ kind: "loading" });
    void fetchAlerts().then(setState);
  }

  async function remove(alert: PriceAlert) {
    setNotice(null);
    try {
      ensureApiAuth();
      await deleteAlert(alert.id);
      setState((s) =>
        s.kind === "ready"
          ? { kind: "ready", alerts: s.alerts.filter((a) => a.id !== alert.id) }
          : s,
      );
      setNotice(`ההתראה על ${alertLabel(alert.canonical_id).name} נמחקה.`);
    } catch (err) {
      setNotice(alertError(err));
    }
  }

  function replace(saved: PriceAlert) {
    setState((s) =>
      s.kind === "ready"
        ? { kind: "ready", alerts: s.alerts.map((a) => (a.id === saved.id ? saved : a)) }
        : s,
    );
  }

  async function setActive(alert: PriceAlert, active: boolean) {
    setNotice(null);
    try {
      ensureApiAuth();
      replace(await updateAlert(alert.id, alertBody(alert, { active })));
      const name = alertLabel(alert.canonical_id).name;
      setNotice(active ? `ההתראה על ${name} פעילה שוב.` : `ההתראה על ${name} הושהתה.`);
    } catch (err) {
      setNotice(alertError(err));
    }
  }

  const editingLabel = editing ? alertLabel(editing.canonical_id) : null;

  return (
    <div className={styles.page}>
      <p className={styles.hint}>
        אנחנו מתריעות על סוג מוצר, לא על ברקוד אחד: כל מותג, תחליף קרוב או מוצר מדויק, במחיר ליחידה.
        כך גם מבצעי מותג פרטי נתפסים.
      </p>

      <Card as="section" aria-labelledby="push-heading">
        <h2 id="push-heading" className={styles.title}>
          התראות בדפדפן
        </h2>
        <PushPanel />
      </Card>

      {needsSignIn ? (
        <Card data-testid="alerts-signin">
          <p>התראות נשמרות בחשבון שלך. התחברי כדי לראות ולנהל אותן.</p>
          <Button variant="outline" size="sm" onClick={auth.openSignIn}>
            התחברות
          </Button>
        </Card>
      ) : null}

      <div role="status" aria-live="polite">
        {notice ? <p className={styles.hint}>{notice}</p> : null}
      </div>

      {!needsSignIn && state.kind === "loading" ? (
        <Card aria-busy="true" aria-label="טוענת התראות">
          <Skeleton height={20} width="50%" />
          <Skeleton height={16} width="30%" />
        </Card>
      ) : null}

      {!needsSignIn && state.kind === "error" ? (
        <Card role="alert">
          <p>{state.message}</p>
          <Button variant="outline" size="sm" onClick={retry}>
            נסי שוב
          </Button>
        </Card>
      ) : null}

      {!needsSignIn && state.kind === "ready" && state.alerts.length === 0 ? (
        <Card data-testid="alerts-empty">
          <h2 className={styles.title}>אין עדיין התראות</h2>
          <p className={styles.hint}>
            פתחי מוצר מהרשימה או מההשוואה ולחצי על ״התריעי לי מתחת ל-₪״ בדף המוצר.
          </p>
          <Button href="/" variant="outline" size="sm">
            לרשימה שלי
          </Button>
        </Card>
      ) : null}

      {!needsSignIn && state.kind === "ready" && state.alerts.length > 0 ? (
        <ul className={styles.alertList} aria-label="ההתראות שלי" data-testid="alerts-list">
          {state.alerts.map((a) => {
            const label = alertLabel(a.canonical_id);
            return (
              <li key={a.id}>
                <Card className={styles.alertItem} data-testid="alert-item">
                  <div className={styles.alertMain}>
                    <Link
                      href={`/product/${a.canonical_id}?name=${encodeURIComponent(label.name)}`}
                      className={styles.alertName}
                    >
                      {label.name}
                    </Link>
                    <span className={styles.alertMeta}>
                      מתחת ל-
                      <Price amount={a.threshold_unit_price} fractionDigits={2} /> {label.unitLabel}
                    </span>
                    <span className={styles.alertMeta}>
                      <FlexChip level={a.flex_level} />
                      <span>
                        עד <span dir="ltr">{Math.round(a.radius_m / 100) / 10}</span> ק&quot;מ
                      </span>
                      {a.active ? null : <Tag variant="unverified">מושהית</Tag>}
                    </span>
                    <span className={styles.alertMeta}>
                      {a.last_fired_at ? (
                        <UpdatedAt iso={a.last_fired_at} prefix="הופעלה לאחרונה" withIcon />
                      ) : (
                        "עוד לא הופעלה"
                      )}
                    </span>
                  </div>
                  <div className={styles.alertActions}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void setActive(a, !a.active)}
                      aria-label={`${a.active ? "השהיית" : "הפעלה מחדש של"} ההתראה על ${label.name}`}
                    >
                      {a.active ? "השהיה" : "הפעלה מחדש"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditing(a)}
                      aria-label={`עריכת ההתראה על ${label.name}`}
                    >
                      עריכה
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void remove(a)}
                      aria-label={`מחיקת ההתראה על ${label.name}`}
                    >
                      מחיקה
                    </Button>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      ) : null}

      {editing && editingLabel ? (
        <EditAlertSheet
          key={editing.id}
          alert={editing}
          name={editingLabel.name}
          unitLabel={editingLabel.unitLabel}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            replace(saved);
            setEditing(null);
            setNotice(`ההתראה על ${editingLabel.name} עודכנה.`);
          }}
        />
      ) : null}

      <p className={styles.hint}>המחיר הקובע הוא בקופה. כל התראה כוללת את מועד עדכון המחיר.</p>
    </div>
  );
}
