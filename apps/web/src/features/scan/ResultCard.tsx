"use client";

import { useId, useState } from "react";
import type { BarcodeLookupResponse, StorePrice } from "@/api/client";
import { Button, Card, Price, Stepper, Tag, UpdatedAt } from "@/components/ui";
import { IconCheck, IconWarning } from "@/components/ui/icons";
import { ReportGapButton } from "@/features/feedback";
import { perUnit, useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { scanMessages } from "@/i18n/messages/scan";
import { formatDistance } from "@/lib/format";
import controls from "@/features/profile/controls/controls.module.css";
import { addCanonicalToList } from "./addToList";
import styles from "./Scan.module.css";

const cents = (n: number) => Math.round(n * 100) / 100;

/** Unit-price difference (D6) when both prices are per the same unit; otherwise null. */
export function unitSaving(here: StorePrice | null | undefined, other: StorePrice): number | null {
  if (!here || here.uom !== other.uom) return null;
  const diff = cents(Number(here.unit_price) - Number(other.unit_price));
  return diff > 0 ? diff : null;
}

/** The price the user typed from the shelf, as a number, or null when empty or invalid. */
export function parseShelfPrice(text: string): number | null {
  const n = Number.parseFloat(text.replace(/[^\d.,]/g, "").replace(",", "."));
  return Number.isFinite(n) && n > 0 ? cents(n) : null;
}

function PriceLine({
  testId,
  label,
  price,
  note,
  children,
}: {
  testId: string;
  label: string;
  price: StorePrice;
  note?: string;
  children?: React.ReactNode;
}) {
  const { locale } = useLocale();
  return (
    <li className={styles.line} data-testid={testId} data-trust-scope="scan-line">
      <div className={styles.lineHead}>
        <span className={styles.lineLabel}>{label}</span>
        <Price amount={price.shelf_price} size="lg" fractionDigits={2} />
      </div>
      <p className={styles.lineMeta}>
        {price.store.chain_name} · {price.store.store_name}
        {price.store.distance_m != null ? ` · ${formatDistance(price.store.distance_m)}` : ""}
      </p>
      <p className={styles.lineMeta}>
        <Price amount={price.unit_price} fractionDigits={2} /> {perUnit(price.uom, locale)}
        {note ? <> · {note}</> : null}
      </p>
      {children}
      <UpdatedAt iso={price.price_valid_from} withIcon />
    </li>
  );
}

export type ResultCardProps = {
  result: BarcodeLookupResponse;
  /** The store the shopper is in (for the gap report); null when none is known. */
  store: { storeId: number; name: string } | null;
};

/**
 * What a scan shows (Scan artboard): "here ₪14.90 · cheapest nearby ₪11.50 at Rami Levy · cheaper
 * substitute ₪8.90", each price with its update time, the substitute labeled with its reason (D10),
 * an optional shelf price to check against ours, and add to list.
 */
export function ResultCard({ result, store }: ResultCardProps) {
  const t = useT(scanMessages);
  const r = useRich(scanMessages);
  const { locale } = useLocale();
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);
  const [shelf, setShelf] = useState("");
  const shelfId = useId();
  const name = result.display_name_he ?? result.canonical?.display_name_he ?? t("scannedProduct");
  const entered = parseShelfPrice(shelf);
  const here = result.here ?? null;
  const gap = entered !== null && here ? cents(entered - Number(here.shelf_price)) : null;
  const hasGap = gap !== null && Math.abs(gap) >= 0.01;
  const substitute = result.cheaper_substitute ?? null;
  const cheapest = result.cheapest_nearby ?? null;
  const subSaving = substitute ? unitSaving(here, substitute) : null;
  const cheapestIsHere = Boolean(
    here && cheapest && cheapest.store.store_id === here.store.store_id,
  );

  return (
    <Card
      as="section"
      aria-labelledby="scan-result-title"
      variant="recommended"
      data-testid="scan-result"
    >
      <div className={styles.resultHead}>
        <h2 id="scan-result-title" className={styles.resultTitle}>
          {name}
        </h2>
        <p className={styles.lineMeta}>
          {r(
            "barcodeLine",
            { ltr: (c) => <span dir="ltr">{c}</span> },
            { barcode: result.barcode },
          )}
        </p>
      </div>

      <ul className={styles.lines}>
        {here ? (
          <PriceLine testId="scan-here" label={t("here")} price={here} />
        ) : (
          <li className={styles.line} data-testid="scan-here">
            <div className={styles.lineHead}>
              <span className={styles.lineLabel}>{t("here")}</span>
              {entered !== null ? (
                <Price amount={entered} size="lg" fractionDigits={2} />
              ) : (
                <span className={styles.lineMeta}>{t("noPriceHere")}</span>
              )}
            </div>
            <p className={styles.lineMeta}>
              {entered !== null ? t("typedFromShelf") : t("pickStoreOrType")}
            </p>
          </li>
        )}

        {cheapest ? (
          <PriceLine
            testId="scan-cheapest"
            label={t("cheapestNearby")}
            price={cheapest}
            note={cheapest.display_name_he}
          >
            {cheapestIsHere ? (
              <p className={styles.good}>
                <IconCheck size={14} /> {t("yourStoreCheapest")}
              </p>
            ) : null}
          </PriceLine>
        ) : null}

        {substitute ? (
          <PriceLine testId="scan-substitute" label={t("cheapSubstitute")} price={substitute}>
            <p className={styles.subName}>
              <Tag variant="substitute">{t("substituteTag")}</Tag>{" "}
              <span>{substitute.display_name_he}</span>
            </p>
            <p className={styles.reason} data-testid="scan-reason">
              {t("substituteReason")}
            </p>
            {subSaving !== null && here ? (
              <p className={styles.good}>
                <IconCheck size={14} />{" "}
                {r(
                  "cheaperBy",
                  { price: <Price amount={subSaving} tone="good" fractionDigits={2} /> },
                  { unit: perUnit(here.uom, locale) },
                )}
              </p>
            ) : null}
          </PriceLine>
        ) : (
          <li className={styles.line} data-testid="scan-no-substitute">
            <span className={styles.lineLabel}>{t("cheapSubstitute")}</span>
            <p className={styles.lineMeta}>{t("noSubstitute")}</p>
          </li>
        )}
      </ul>

      <div className={controls.field}>
        <label htmlFor={shelfId} className={controls.label}>
          {t("shelfLabel")}
        </label>
        <input
          id={shelfId}
          className={controls.input}
          inputMode="decimal"
          dir="ltr"
          placeholder="14.90"
          value={shelf}
          onChange={(e) => setShelf(e.target.value)}
        />
      </div>
      {hasGap && here ? (
        <div className={styles.gap} role="status" data-testid="scan-gap">
          <p>
            <IconWarning size={15} />{" "}
            {r("gapNotice", {
              typed: <Price amount={entered ?? 0} fractionDigits={2} />,
              ours: <Price amount={here.shelf_price} fractionDigits={2} />,
            })}
          </p>
          {store ? (
            <ReportGapButton
              label={t("reportGap")}
              context={{
                storeId: store.storeId,
                storeName: store.name,
                canonicalId: result.canonical?.canonical_id ?? null,
                itemId: here.item_id,
                itemName: name,
                shownPrice: here.shelf_price,
                priceUpdatedAt: here.price_valid_from,
              }}
            />
          ) : null}
        </div>
      ) : null}

      {result.canonical ? (
        <div className={styles.addRow}>
          <Stepper
            value={quantity}
            onChange={(n) => {
              setQuantity(n);
              setAdded(false);
            }}
            min={1}
            label={name}
          />
          <Button
            onClick={() => {
              if (!result.canonical) return;
              addCanonicalToList(result.canonical, result.canonical.display_name_he, quantity);
              setAdded(true);
            }}
          >
            {t("addToList")}
          </Button>
        </div>
      ) : null}
      <div role="status" aria-live="polite">
        {added ? (
          <p className={styles.good} data-testid="scan-added">
            <IconCheck size={14} /> {t("added")}
          </p>
        ) : null}
      </div>

      <p className={styles.footnote}>{result.disclaimer_he}</p>
    </Card>
  );
}
