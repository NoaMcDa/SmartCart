"use client";

import { Price } from "@/components/ui/Price";
import { IconCheck, IconClose } from "@/components/ui/icons";
import { useRich } from "@/i18n/format-2";
import { useT } from "@/i18n/LocaleProvider";
import { mapMessages } from "@/i18n/messages/map";
import styles from "./Map.module.css";

export type Pin = {
  storeId: number;
  storeName: string;
  chainName: string;
  total: number;
  missingCount: number;
  /** Part of the recommended plan. */
  recommended: boolean;
  /** Lowest basket total among complete baskets. */
  cheapest: boolean;
};

/**
 * A store on the map: a button whose face is the basket total. The recommended store has the
 * accent border and the word "מומלץ"; the cheapest has the word "הכי זול" with a check; a store
 * with missing items shows the count with an x. Nothing is carried by color alone.
 */
export function PinButton({
  pin,
  selected,
  onSelect,
}: {
  pin: Pin;
  selected: boolean;
  onSelect: (storeId: number) => void;
}) {
  const t = useT(mapMessages);
  const r = useRich(mapMessages);
  const label =
    [
      t("pinBasket", { chain: pin.chainName, total: pin.total }),
      pin.recommended ? t("recommended") : null,
      pin.cheapest ? t("cheapest") : null,
      pin.missingCount > 0 ? t("pinMissingItems", { count: pin.missingCount }) : null,
    ]
      .filter(Boolean)
      .join(t("listSep")) + t("pinTap");
  return (
    <button
      type="button"
      className={styles.pin}
      data-recommended={pin.recommended}
      data-selected={selected}
      aria-label={label}
      aria-pressed={selected}
      data-testid="map-pin"
      onClick={() => onSelect(pin.storeId)}
    >
      <span className={styles.pinChain}>{pin.chainName}</span>
      <Price amount={pin.total} size="md" data-testid="pin-price" />
      <span className={styles.pinFlags}>
        {pin.recommended ? <span className={styles.flag}>{t("recommended")}</span> : null}
        {pin.cheapest ? (
          <span className={styles.flag}>
            <IconCheck size={11} /> {t("cheapest")}
          </span>
        ) : null}
        {pin.missingCount > 0 ? (
          <span className={styles.flagMissing}>
            <IconClose size={11} />{" "}
            {r(
              "flagMissing",
              { ltr: (c) => <span dir="ltr">{c}</span> },
              { count: pin.missingCount },
            )}
          </span>
        ) : null}
      </span>
    </button>
  );
}
