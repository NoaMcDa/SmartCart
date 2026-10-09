"use client";

import { DataText } from "@/i18n/DataText";
import { useLocale } from "@/i18n/LocaleProvider";
import { itemProductName } from "@/lib/format";
import styles from "./ItemName.module.css";

export type ItemNameProps = {
  item: { display_name_he: string; canonical_name_ar?: string | null };
  /**
   * `product`: names the product the shopper asked for (Arabic canonical name when there is one).
   * `line`: the same, plus the chain's own item name underneath, because the brand and pack on the
   * shelf are what the person will look for. `shelf`: only the chain's item name.
   * Hebrew always shows the chain's item name, as before.
   */
  show?: "product" | "line" | "shelf";
};

/**
 * A priced item's name in the UI language. `PricedItem.display_name_he` is the chain's item name
 * ("חלב טרי 3% תנובה, 1 ליטר") and has no Arabic translation; `canonical_name_ar` names the canonical
 * product ("حليب طازج 3%"). The two are never swapped silently: the shelf name stays visible,
 * marked as Hebrew, wherever the person needs it.
 */
export function ItemName({ item, show = "product" }: ItemNameProps) {
  const { locale } = useLocale();
  if (locale !== "ar") return <>{item.display_name_he}</>;
  const ar = show === "shelf" ? "" : itemProductName(item, locale);
  const generic = ar && ar !== item.display_name_he ? ar : "";
  if (!generic) {
    return <DataText>{item.display_name_he}</DataText>;
  }
  if (show === "product") return <>{generic}</>;
  return (
    <>
      {generic}
      <span className={styles.shelf}>
        <DataText>{item.display_name_he}</DataText>
      </span>
    </>
  );
}
