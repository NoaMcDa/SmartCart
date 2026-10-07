"use client";

import { useId, useState, type FormEvent } from "react";
import { updateAlert, type FlexLevel, type PriceAlert } from "@/api/client";
import { BottomSheet, Button, SegmentedControl } from "@/components/ui";
import { ensureApiAuth } from "@/features/auth/apiAuth";
import controls from "@/features/profile/controls/controls.module.css";
import { alertError } from "./AlertMe";
import { parseThreshold } from "./threshold";

const LEVELS: ReadonlyArray<{ value: FlexLevel; label: string }> = [
  { value: "any_brand", label: "כל מותג" },
  { value: "close", label: "תחליף קרוב" },
  { value: "exact", label: "מוצר מדויק" },
];

/** Body of `PUT /me/alerts/{id}`: the alert as it is, with the changes applied. */
export function alertBody(alert: PriceAlert, change: Partial<PriceAlert>) {
  const next = { ...alert, ...change };
  return {
    canonical_id: next.canonical_id,
    threshold_unit_price: next.threshold_unit_price,
    flex_level: next.flex_level,
    radius_m: next.radius_m,
    active: next.active,
  };
}

/**
 * Edit an alert's target price and level (issue #23). The API re-arms an edited alert, so the next
 * qualifying price notifies again.
 */
export function EditAlertSheet({
  alert,
  name,
  unitLabel,
  onClose,
  onSaved,
}: {
  alert: PriceAlert | null;
  name: string;
  unitLabel: string;
  onClose: () => void;
  onSaved: (saved: PriceAlert) => void;
}) {
  const [price, setPrice] = useState(alert?.threshold_unit_price ?? "");
  const [level, setLevel] = useState<FlexLevel>(alert?.flex_level ?? "any_brand");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const priceId = useId();

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!alert) return;
    const value = parseThreshold(price);
    if (value === null) {
      setError("הקלידי מחיר חיובי, למשל 8.90.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      ensureApiAuth();
      const saved = await updateAlert(
        alert.id,
        alertBody(alert, { threshold_unit_price: value.toFixed(2), flex_level: level }),
      );
      onSaved(saved);
    } catch (err) {
      setError(alertError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet open={alert !== null} onClose={onClose} title={name} eyebrow="עריכת התראה">
      <form onSubmit={save} className={controls.stack} noValidate>
        <div className={controls.field}>
          <label htmlFor={priceId} className={controls.label}>
            התריעי לי מתחת ל-₪ ({unitLabel})
          </label>
          <input
            id={priceId}
            className={controls.input}
            inputMode="decimal"
            dir="ltr"
            value={price}
            onChange={(e) => {
              setPrice(e.target.value);
              setError(null);
            }}
          />
        </div>
        <SegmentedControl<FlexLevel>
          label="רמת התאמה להתראה"
          value={level}
          onChange={setLevel}
          options={LEVELS}
        />
        <p className={controls.hint}>אחרי עריכה ההתראה נבדקת מחדש מול המחירים הנוכחיים.</p>
        {error ? (
          <p className={controls.error} role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={busy}>
          {busy ? "שומרת…" : "שמירה"}
        </Button>
      </form>
    </BottomSheet>
  );
}
