"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import {
  ApiError,
  createAlert,
  deleteAlert,
  listAlerts,
  type FlexLevel,
  type PriceAlert,
} from "@/api/client";
import { Button, Card, Price, SegmentedControl } from "@/components/ui";
import { flexLevelLabel } from "@/components/ui/Chip";
import { IconCheck, IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { reportAlertCreated } from "@/features/consent/betaEvents";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { alertMessages } from "@/i18n/messages/alerts";
import { useShopper } from "@/state/shopper";
import { rememberAlertLabel } from "./alertNames";
import { parseThreshold } from "./threshold";
import { PushPanel } from "./PushPanel";
import styles from "./Alerts.module.css";

const LEVEL_VALUES: ReadonlyArray<FlexLevel> = ["any_brand", "close", "exact"];

/** The three match levels as segmented-control options, labeled in `locale`. */
export function alertLevels(
  locale: Locale = DEFAULT_LOCALE,
): ReadonlyArray<{ value: FlexLevel; label: string }> {
  return LEVEL_VALUES.map((value) => ({ value, label: flexLevelLabel(value, locale) }));
}

export function alertError(err: unknown, locale: Locale = DEFAULT_LOCALE): string {
  const t = (key: "errSignIn" | "errLimit" | "errServer" | "errOffline") =>
    translate(alertMessages, locale, key);
  if (err instanceof ApiError) {
    if (err.status === 401) return t("errSignIn");
    if (err.status === 402 || err.status === 403 || err.status === 429) return t("errLimit");
    return t("errServer");
  }
  return t("errOffline");
}

/**
 * "התריעי לי מתחת ל-₪__" on product detail (issue #23): a target unit price (D6) at one of the
 * three flexibility levels, within the shopper's radius. The alert is on the canonical product, so
 * it survives brand and pack changes. Alerts are per user: when Supabase is configured and nobody
 * is signed in, the form asks for sign-in instead of failing.
 */
export function AlertMe({
  canonicalId,
  name,
  unitLabel,
}: {
  canonicalId: number;
  name: string;
  unitLabel: string;
}) {
  const t = useT(alertMessages);
  const { locale } = useLocale();
  const auth = useAuth();
  const shopper = useShopper();
  const [threshold, setThreshold] = useState("");
  const [level, setLevel] = useState<FlexLevel>("any_brand");
  const [existing, setExisting] = useState<PriceAlert[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<PriceAlert | null>(null);
  const [busy, setBusy] = useState(false);
  const inputId = useId();
  const noteId = useId();

  const needsSignIn = auth.configured && auth.status !== "loading" && auth.status !== "signed-in";
  const waiting = auth.configured && auth.status === "loading";

  useEffect(() => {
    if (needsSignIn || waiting) return;
    let cancelled = false;
    ensureApiAuth();
    listAlerts().then(
      (all) => {
        if (!cancelled) setExisting(all.filter((a) => a.canonical_id === canonicalId));
      },
      () => {
        // The list is a convenience; creating still works and reports its own errors.
      },
    );
    return () => {
      cancelled = true;
    };
  }, [canonicalId, needsSignIn, waiting]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = parseThreshold(threshold);
    if (value === null) {
      setError(t("thresholdInvalid"));
      return;
    }
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      ensureApiAuth();
      const alert = await createAlert({
        canonical_id: canonicalId,
        threshold_unit_price: value.toFixed(2),
        flex_level: level,
        radius_m: shopper?.radiusM,
      });
      rememberAlertLabel(canonicalId, { name, unitLabel });
      reportAlertCreated(level, "product");
      setExisting((prev) => [...prev, alert]);
      setCreated(alert);
      setThreshold("");
    } catch (err) {
      setError(alertError(err, locale));
    } finally {
      setBusy(false);
    }
  }

  async function remove(alert: PriceAlert) {
    setError(null);
    try {
      ensureApiAuth();
      await deleteAlert(alert.id);
      setExisting((prev) => prev.filter((a) => a.id !== alert.id));
      setCreated((c) => (c?.id === alert.id ? null : c));
    } catch (err) {
      setError(alertError(err, locale));
    }
  }

  return (
    <Card
      as="section"
      aria-labelledby="alert-heading"
      className={styles.card}
      data-testid="alert-me"
    >
      <h2 id="alert-heading" className={styles.title}>
        {t("cardTitle")}
      </h2>

      {needsSignIn ? (
        <div className={styles.stack}>
          <p className={styles.note}>
            <IconInfo size={15} /> {t("signInNote")}
          </p>
          <Button size="sm" variant="outline" onClick={auth.openSignIn}>
            {t("signIn")}
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className={styles.stack} noValidate>
          <div className={styles.formRow}>
            <label htmlFor={inputId} className={styles.label}>
              {t("thresholdLabel")}
            </label>
            <input
              id={inputId}
              className={styles.input}
              inputMode="decimal"
              dir="ltr"
              placeholder="__"
              autoComplete="off"
              value={threshold}
              aria-describedby={noteId}
              aria-invalid={error && parseThreshold(threshold) === null ? true : undefined}
              onChange={(e) => {
                setThreshold(e.target.value);
                setError(null);
              }}
            />
            <Button type="submit" size="sm" disabled={busy || waiting}>
              {t("create")}
            </Button>
          </div>
          <SegmentedControl<FlexLevel>
            label={t("levelLegend")}
            value={level}
            onChange={setLevel}
            options={alertLevels(locale)}
          />
          <p id={noteId} className={styles.hint}>
            {t("cardHint", {
              unit: unitLabel,
              km: shopper ? Math.round(shopper.radiusM / 100) / 10 : 5,
            })}
          </p>
        </form>
      )}

      <div role="status" aria-live="polite">
        {created ? (
          <p className={styles.ok} data-testid="alert-created">
            <IconCheck size={15} />{" "}
            {formatRich(t("created"), {
              price: <Price amount={created.threshold_unit_price} fractionDigits={2} />,
              unit: unitLabel,
            })}
          </p>
        ) : null}
      </div>
      {error ? (
        <p className={styles.error} role="alert" data-testid="alert-error">
          <IconInfo size={15} /> {error}
        </p>
      ) : null}

      {existing.length > 0 ? (
        <ul className={styles.existing} aria-label={t("existingLabel")}>
          {existing.map((a) => (
            <li key={a.id} data-testid="alert-existing">
              <span>
                {formatRich(t("below"), {
                  price: <Price amount={a.threshold_unit_price} fractionDigits={2} />,
                  unit: unitLabel,
                })}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void remove(a)}
                aria-label={t("deleteBelowLabel", { price: a.threshold_unit_price })}
              >
                {t("delete")}
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      {existing.length > 0 ? <PushPanel /> : null}
      <p className={styles.hint}>{t("finePrint")}</p>
    </Card>
  );
}
