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
import { IconCheck, IconInfo } from "@/components/ui/icons";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import { useAuth } from "@/features/auth/AuthProvider";
import { useShopper } from "@/state/shopper";
import { rememberAlertLabel } from "./alertNames";
import { parseThreshold } from "./threshold";
import { PushPanel } from "./PushPanel";
import styles from "./Alerts.module.css";

const LEVELS: ReadonlyArray<{ value: FlexLevel; label: string }> = [
  { value: "any_brand", label: "כל מותג" },
  { value: "close", label: "תחליף קרוב" },
  { value: "exact", label: "מוצר מדויק" },
];

export function alertError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "צריך להתחבר כדי לנהל התראות.";
    if (err.status === 402 || err.status === 403 || err.status === 429) {
      return "הגעת למספר ההתראות שכלול בחינם. אפשר למחוק התראה קיימת.";
    }
    return "השרת החזיר שגיאה. נסי שוב בעוד רגע.";
  }
  return "נראה שאין חיבור לשרת. בדקי את החיבור ונסי שוב.";
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
      setError("הקלידי מחיר חיובי, למשל 8.90.");
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
      setExisting((prev) => [...prev, alert]);
      setCreated(alert);
      setThreshold("");
    } catch (err) {
      setError(alertError(err));
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
      setError(alertError(err));
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
        התראה כשהמחיר יורד
      </h2>

      {needsSignIn ? (
        <div className={styles.stack}>
          <p className={styles.note}>
            <IconInfo size={15} /> התראות נשמרות בחשבון שלך, כדי שנוכל לשלוח אותן גם כשהאפליקציה
            סגורה. נשלח קוד חד-פעמי לאימייל, בלי סיסמה.
          </p>
          <Button size="sm" variant="outline" onClick={auth.openSignIn}>
            התחברות
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className={styles.stack} noValidate>
          <div className={styles.formRow}>
            <label htmlFor={inputId} className={styles.label}>
              התריעי לי מתחת ל-₪
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
              יצירת התראה
            </Button>
          </div>
          <SegmentedControl<FlexLevel>
            label="רמת התאמה להתראה"
            value={level}
            onChange={setLevel}
            options={LEVELS}
          />
          <p id={noteId} className={styles.hint}>
            המחיר הוא {unitLabel}, כדי שההשוואה תהיה הוגנת בין מותגים וגדלים. ההתראה על סוג המוצר,
            לא על ברקוד אחד, ובטווח של {shopper ? Math.round(shopper.radiusM / 100) / 10 : 5}{" "}
            ק&quot;מ ממך.
          </p>
        </form>
      )}

      <div role="status" aria-live="polite">
        {created ? (
          <p className={styles.ok} data-testid="alert-created">
            <IconCheck size={15} /> ההתראה נוצרה: נעדכן אותך כשיהיה מתחת ל-
            <Price amount={created.threshold_unit_price} fractionDigits={2} /> {unitLabel}.
          </p>
        ) : null}
      </div>
      {error ? (
        <p className={styles.error} role="alert" data-testid="alert-error">
          <IconInfo size={15} /> {error}
        </p>
      ) : null}

      {existing.length > 0 ? (
        <ul className={styles.existing} aria-label="התראות קיימות למוצר">
          {existing.map((a) => (
            <li key={a.id} data-testid="alert-existing">
              <span>
                מתחת ל-
                <Price amount={a.threshold_unit_price} fractionDigits={2} /> {unitLabel}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void remove(a)}
                aria-label={`מחיקת ההתראה מתחת ל-${a.threshold_unit_price} ש"ח`}
              >
                מחיקה
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      {existing.length > 0 ? <PushPanel /> : null}
      <p className={styles.hint}>המחיר הקובע הוא בקופה. ההתראה מבוססת על מחירי קבצי השקיפות.</p>
    </Card>
  );
}
