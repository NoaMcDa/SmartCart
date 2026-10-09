"use client";

import { useId, useState, type FormEvent } from "react";
import { reportGap, type StoreResult } from "@/api/client";
import { BottomSheet, Button, Price, UpdatedAt } from "@/components/ui";
import { reportGapReported } from "@/features/consent/betaEvents";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { compareMessages } from "@/i18n/messages/compare";
import { storeLabel } from "@/lib/storeName";
import styles from "./Results.module.css";

export type ReportGapSheetProps = {
  open: boolean;
  onClose: () => void;
  stores: StoreResult[];
  /** canonical id -> name, for the item picker. */
  items: Array<{ canonical_id: number; name: string }>;
};

function toNumber(raw: string): number | null {
  const n = Number.parseFloat(raw.replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/**
 * Report-a-gap (D10): the price at the shelf or checkout differs from what we showed, or an item
 * is missing. Sends /feedback/gap with the store, item and both prices; no location.
 */
export function ReportGapSheet({ open, onClose, stores, items }: ReportGapSheetProps) {
  const t = useT(compareMessages);
  return (
    <BottomSheet open={open} onClose={onClose} title={t("gapTitle")} eyebrow={t("gapEyebrow")}>
      {open ? <GapForm key="form" stores={stores} items={items} onClose={onClose} /> : null}
    </BottomSheet>
  );
}

function GapForm({ stores, items, onClose }: Omit<ReportGapSheetProps, "open">) {
  const t = useT(compareMessages);
  const { locale } = useLocale();
  const id = useId();
  const [storeId, setStoreId] = useState<number | null>(stores[0]?.store_id ?? null);
  const [canonicalId, setCanonicalId] = useState<string>("");
  const [actual, setActual] = useState("");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  const store = stores.find((s) => s.store_id === storeId) ?? null;
  const line =
    store && canonicalId ? store.items.find((i) => i.canonical_id === Number(canonicalId)) : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (storeId === null) return;
    setStatus("sending");
    try {
      await reportGap({
        store_id: storeId,
        canonical_id: canonicalId ? Number(canonicalId) : null,
        item_id: line?.item_id ?? null,
        shown_price: line ? line.shelf_price : null,
        actual_price: toNumber(actual),
        note: note.trim() || null,
      });
      reportGapReported();
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  if (status === "sent") {
    return (
      <div className={styles.gapDone} role="status">
        <p>{t("gapThanks")}</p>
        <Button onClick={onClose}>{t("close")}</Button>
      </div>
    );
  }

  return (
    <form className={styles.gapForm} onSubmit={submit}>
      <div className={styles.field}>
        <label htmlFor={`${id}-store`}>{t("gapStore")}</label>
        <select
          id={`${id}-store`}
          value={storeId ?? ""}
          onChange={(e) => setStoreId(Number(e.target.value))}
        >
          {stores.map((s) => (
            <option key={s.store_id} value={s.store_id}>
              {storeLabel(s.store_name, locale)}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.field}>
        <label htmlFor={`${id}-item`}>{t("gapItem")}</label>
        <select
          id={`${id}-item`}
          value={canonicalId}
          onChange={(e) => setCanonicalId(e.target.value)}
        >
          <option value="">{t("gapItemGeneral")}</option>
          {items.map((i) => (
            <option key={i.canonical_id} value={i.canonical_id}>
              {i.name}
            </option>
          ))}
        </select>
        {line ? (
          <span className={styles.fieldHint}>
            {t("gapShown")} <Price amount={line.shelf_price} /> ·{" "}
            <UpdatedAt iso={line.price_valid_from} />
          </span>
        ) : null}
      </div>
      <div className={styles.field}>
        <label htmlFor={`${id}-actual`}>{t("gapActual")}</label>
        <input
          id={`${id}-actual`}
          inputMode="decimal"
          dir="ltr"
          value={actual}
          onChange={(e) => setActual(e.target.value)}
          placeholder="0.00"
        />
      </div>
      <div className={styles.field}>
        <label htmlFor={`${id}-note`}>{t("gapNote")}</label>
        <textarea
          id={`${id}-note`}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("gapNotePlaceholder")}
        />
      </div>
      {status === "error" ? (
        <p role="alert" className={styles.formError}>
          {t("gapError")}
        </p>
      ) : null}
      <div className={styles.gapActions}>
        <Button type="submit" disabled={status === "sending" || storeId === null}>
          {status === "sending" ? t("gapSending") : t("gapSend")}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
