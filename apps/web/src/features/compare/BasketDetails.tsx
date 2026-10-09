"use client";

import Link from "next/link";
import type { Plan } from "@/api/client";
import { PromoConfidence, Tag, TrustedPrice } from "@/components/ui";
import { ItemName } from "@/components/ui/ItemName";
import { DataText } from "@/i18n/DataText";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { compareMessages } from "@/i18n/messages/compare";
import { chainLabel, storeLabel } from "@/lib/storeName";
import styles from "./Results.module.css";

/**
 * Line-by-line prices of a plan, collapsed by default. Every line carries its own update time,
 * substitutes are labeled and link to their card, weighed goods are marked estimated and club
 * promos are tagged (issue #12).
 */
export function BasketDetails({
  plan,
  names,
}: {
  plan: Plan;
  /** canonical id -> the list's name for it, used as the product page's `name`. */
  names?: Map<number, string>;
}) {
  const t = useT(compareMessages);
  const { locale } = useLocale();
  return (
    <details className={styles.details} data-testid="basket-details">
      <summary className={styles.detailsSummary}>
        {t("basketIn", {
          chains: plan.stores
            .map((s) => chainLabel(s.store.chain_name, locale))
            .join(t("chainsJoiner")),
        })}
      </summary>
      {plan.stores.map(({ store, item_ids }) => (
        <div key={store.store_id} className={styles.detailsStore}>
          <h3 className={styles.detailsStoreName}>{storeLabel(store.store_name, locale)}</h3>
          <ul className={styles.lines}>
            {store.items
              .filter((i) => item_ids.includes(i.item_id))
              .map((line) => (
                <li key={line.item_id} className={styles.line} data-trust-scope="line">
                  <div className={styles.lineMain}>
                    <Link
                      href={`/product/${line.canonical_id}?name=${encodeURIComponent(
                        names?.get(line.canonical_id) ?? line.display_name_he,
                      )}`}
                      className={styles.lineName}
                      data-testid="line-product-link"
                    >
                      <ItemName item={line} show="line" />
                    </Link>
                    <span className={styles.lineTags}>
                      {line.is_substitute ? (
                        <Link
                          href={`/compare/substitution/${line.item_id}?plan=${plan.kind}`}
                          className={styles.tagLink}
                          aria-label={t("substituteWhy", {
                            name:
                              locale === "ar" && line.canonical_name_ar
                                ? line.canonical_name_ar
                                : line.display_name_he,
                          })}
                        >
                          <Tag variant="substitute">{t("substituteTag")}</Tag>
                        </Link>
                      ) : null}
                      {line.club_required ? (
                        <Tag variant="club">
                          {line.club_name
                            ? t("clubPromoNamed", { club: chainLabel(line.club_name, locale) })
                            : t("clubPromo")}
                        </Tag>
                      ) : null}
                      {line.is_estimated ? (
                        <Tag variant="estimated">{t("estimatedTag")}</Tag>
                      ) : null}
                      {line.promo_description && !line.club_required ? (
                        <span className={styles.promo}>
                          <DataText>{line.promo_description}</DataText>
                        </span>
                      ) : null}
                      {line.promo_description || line.club_required ? (
                        <PromoConfidence confidence={line.promo_confidence} />
                      ) : null}
                    </span>
                  </div>
                  <div className={styles.lineQty}>
                    × <span dir="ltr">{Number.parseFloat(line.quantity)}</span>
                  </div>
                  <TrustedPrice
                    amount={line.line_total}
                    updatedAt={line.price_valid_from}
                    fractionDigits={2}
                    size="md"
                  />
                </li>
              ))}
          </ul>
        </div>
      ))}
    </details>
  );
}
