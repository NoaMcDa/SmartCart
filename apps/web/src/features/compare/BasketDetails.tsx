"use client";

import Link from "next/link";
import type { Plan } from "@/api/client";
import { PromoConfidence, Tag, TrustedPrice } from "@/components/ui";
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
  return (
    <details className={styles.details} data-testid="basket-details">
      <summary className={styles.detailsSummary}>
        פירוט הסל ב{plan.stores.map((s) => s.store.chain_name).join(" וב")}
      </summary>
      {plan.stores.map(({ store, item_ids }) => (
        <div key={store.store_id} className={styles.detailsStore}>
          <h3 className={styles.detailsStoreName}>{store.store_name}</h3>
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
                      {line.display_name_he}
                    </Link>
                    <span className={styles.lineTags}>
                      {line.is_substitute ? (
                        <Link
                          href={`/compare/substitution/${line.item_id}?plan=${plan.kind}`}
                          className={styles.tagLink}
                          aria-label={`תחליף: ${line.display_name_he}, למה?`}
                        >
                          <Tag variant="substitute">תחליף · למה?</Tag>
                        </Link>
                      ) : null}
                      {line.club_required ? (
                        <Tag variant="club">
                          מבצע מועדון{line.club_name ? ` · ${line.club_name}` : ""}
                        </Tag>
                      ) : null}
                      {line.is_estimated ? <Tag variant="estimated">מחיר משוער · שקיל</Tag> : null}
                      {line.promo_description && !line.club_required ? (
                        <span className={styles.promo}>{line.promo_description}</span>
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
