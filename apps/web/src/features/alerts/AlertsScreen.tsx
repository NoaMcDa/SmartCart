"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteAlert, listAlerts, updateAlert, type PriceAlert } from "@/api/client";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { Button, Card, FlexChip, Price, Skeleton, Tag, UpdatedAt } from "@/components/ui";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import type { Locale } from "@/i18n/locales";
import { alertMessages } from "@/i18n/messages/alerts";
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

async function fetchAlerts(locale: Locale): Promise<State> {
  try {
    ensureApiAuth();
    return { kind: "ready", alerts: await listAlerts() };
  } catch (err) {
    return { kind: "error", message: alertError(err, locale) };
  }
}

/**
 * /alerts (issue #23): every alert of the signed-in user, with the product, the target unit price,
 * the flexibility level and the radius, edit, pause, delete, and the browser push switch. Product names come
 * from what the device remembered when the alert was created.
 */
export function AlertsScreen() {
  const t = useT(alertMessages);
  const { locale } = useLocale();
  const auth = useAuth();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<PriceAlert | null>(null);
  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";
  const waiting = auth.configured && auth.status === "loading";

  useEffect(() => {
    if (needsSignIn || waiting) return;
    let cancelled = false;
    void fetchAlerts(locale).then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, [needsSignIn, waiting, locale]);

  function retry() {
    setState({ kind: "loading" });
    void fetchAlerts(locale).then(setState);
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
      setNotice(t("noticeDeleted", { name: alertLabel(alert.canonical_id, locale).name }));
    } catch (err) {
      setNotice(alertError(err, locale));
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
      const name = alertLabel(alert.canonical_id, locale).name;
      setNotice(t(active ? "noticeResumed" : "noticePaused", { name }));
    } catch (err) {
      setNotice(alertError(err, locale));
    }
  }

  const editingLabel = editing ? alertLabel(editing.canonical_id, locale) : null;

  return (
    <div className={styles.page}>
      <DocumentTitle text={t("pageTitle")} />
      <p className={styles.hint}>{t("lead")}</p>

      <Card as="section" aria-labelledby="push-heading">
        <h2 id="push-heading" className={styles.title}>
          {t("pushHeading")}
        </h2>
        <PushPanel />
      </Card>

      {needsSignIn ? (
        <Card data-testid="alerts-signin">
          <p>{t("signinBody")}</p>
          <Button variant="outline" size="sm" onClick={auth.openSignIn}>
            {t("signIn")}
          </Button>
        </Card>
      ) : null}

      <div role="status" aria-live="polite">
        {notice ? <p className={styles.hint}>{notice}</p> : null}
      </div>

      {!needsSignIn && state.kind === "loading" ? (
        <Card aria-busy="true" aria-label={t("loadingLabel")}>
          <Skeleton height={20} width="50%" />
          <Skeleton height={16} width="30%" />
        </Card>
      ) : null}

      {!needsSignIn && state.kind === "error" ? (
        <Card role="alert">
          <p>{state.message}</p>
          <Button variant="outline" size="sm" onClick={retry}>
            {t("retry")}
          </Button>
        </Card>
      ) : null}

      {!needsSignIn && state.kind === "ready" && state.alerts.length === 0 ? (
        <Card data-testid="alerts-empty">
          <h2 className={styles.title}>{t("emptyTitle")}</h2>
          <p className={styles.hint}>{t("emptyBody")}</p>
          <Button href="/" variant="outline" size="sm">
            {t("toList")}
          </Button>
        </Card>
      ) : null}

      {!needsSignIn && state.kind === "ready" && state.alerts.length > 0 ? (
        <ul className={styles.alertList} aria-label={t("listLabel")} data-testid="alerts-list">
          {state.alerts.map((a) => {
            const label = alertLabel(a.canonical_id, locale);
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
                      {formatRich(t("below"), {
                        price: <Price amount={a.threshold_unit_price} fractionDigits={2} />,
                        unit: label.unitLabel,
                      })}
                    </span>
                    <span className={styles.alertMeta}>
                      <FlexChip level={a.flex_level} />
                      <span>
                        {formatRich(t("radius"), {
                          km: <span dir="ltr">{Math.round(a.radius_m / 100) / 10}</span>,
                        })}
                      </span>
                      {a.active ? null : <Tag variant="unverified">{t("paused")}</Tag>}
                    </span>
                    <span className={styles.alertMeta}>
                      {a.last_fired_at ? (
                        <UpdatedAt iso={a.last_fired_at} prefix={t("lastFired")} withIcon />
                      ) : (
                        t("neverFired")
                      )}
                    </span>
                  </div>
                  <div className={styles.alertActions}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void setActive(a, !a.active)}
                      aria-label={t(a.active ? "pauseLabel" : "resumeLabel", { name: label.name })}
                    >
                      {a.active ? t("pause") : t("resume")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditing(a)}
                      aria-label={t("editLabel", { name: label.name })}
                    >
                      {t("edit")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void remove(a)}
                      aria-label={t("deleteLabel", { name: label.name })}
                    >
                      {t("delete")}
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
            setNotice(t("noticeUpdated", { name: editingLabel.name }));
          }}
        />
      ) : null}

      <p className={styles.hint}>{t("footnote")}</p>
    </div>
  );
}
