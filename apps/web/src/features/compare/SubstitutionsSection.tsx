"use client";

import Link from "next/link";
import type { OptimizeResponse, Plan } from "@/api/client";
import { Button, Price, Tag, UpdatedAt } from "@/components/ui";
import { ItemName } from "@/components/ui/ItemName";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { compareMessages } from "@/i18n/messages/compare";
import { chainLabel } from "@/lib/storeName";
import { findOriginal, planSubstitutions, substitutionSavingWithBasis } from "@/state/comparison";
import { keepOriginal } from "@/features/substitution/actions";
import { Count } from "./Count";
import styles from "./Results.module.css";
import { perUnitLabel } from "@/lib/attributes";

/**
 * Every substitute in the recommended plan, original next to substitute, with "why?" (the
 * substitution card) and undo (DesktopResults artboard, issue #48 "list of all substituted items").
 */
export function SubstitutionsSection({ res, plan }: { res: OptimizeResponse; plan: Plan }) {
  const t = useT(compareMessages);
  const { locale } = useLocale();
  const subs = planSubstitutions(plan);
  if (subs.length === 0) return null;
  const chains = [...new Set(subs.map((s) => chainLabel(s.store.chain_name, locale)))].join(
    t("subsJoiner"),
  );
  return (
    <section className={styles.subs} aria-labelledby="subs-title" data-testid="subs-section">
      <div className={styles.subsHead}>
        <h2 id="subs-title" className={styles.sectionTitle}>
          {t("subsTitle", { chains })}
        </h2>
        <span className={styles.muted}>{t("subsUndoAny")}</span>
      </div>
      <ul className={styles.subsList}>
        {subs.map(({ item }) => {
          const original = findOriginal(res, item.canonical_id);
          // The same rule as the substitution card: against the original at this store when the
          // API sends it, else against the home store's, and the row says which.
          const here = item.original_here ?? null;
          const shownOriginal = here ?? original?.item ?? null;
          const saving = substitutionSavingWithBasis({ item, original });
          return (
            <li key={item.item_id} className={styles.subRow} data-trust-scope="substitution">
              <div className={styles.subCol}>
                <span className={styles.subLabel}>{t("inYourList")}</span>
                <span className={styles.subName}>
                  {shownOriginal ? <ItemName item={shownOriginal} /> : t("originalProduct")}
                </span>
                {shownOriginal ? (
                  <>
                    <span className={styles.unitPrice}>
                      <Price amount={shownOriginal.effective_unit_price} />{" "}
                      {perUnitLabel(shownOriginal.uom, locale)}
                    </span>
                    <span className={styles.unitPrice} data-testid="sub-original-where">
                      {t(here ? "subAtThisStore" : "subAtYourStore")}
                    </span>
                  </>
                ) : null}
              </div>
              <div className={styles.subCol}>
                <Tag variant="substitute">{t("substituteLabel")}</Tag>
                <span className={styles.subName}>
                  <ItemName item={item} show="shelf" />
                </span>
                <span className={styles.unitPrice}>
                  <Price amount={item.effective_unit_price} /> {perUnitLabel(item.uom, locale)}
                </span>
              </div>
              <div className={styles.subSaving}>
                {saving && saving.total > 0 ? (
                  <>
                    <Price amount={saving.total} tone="good" size="md" />
                    <span className={styles.muted}>
                      × <Count n={saving.quantity} noun="unit" />
                    </span>
                    <span className={styles.muted} data-testid="sub-saving-basis">
                      {t(saving.basis === "here" ? "subSavingBasisHere" : "subSavingBasisHome")}
                    </span>
                  </>
                ) : null}
                <UpdatedAt iso={item.price_valid_from} />
              </div>
              <div className={styles.subActions}>
                <Button
                  variant="outline"
                  size="sm"
                  href={`/compare/substitution/${item.item_id}?plan=${plan.kind}`}
                  aria-label={t("whyLabel", { name: item.display_name_he })}
                >
                  {t("why")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => keepOriginal(item, original?.item.display_name_he)}
                  aria-label={t("undoSwapLabel", { name: item.display_name_he })}
                >
                  {t("undoSwap")}
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      <p className={styles.muted}>
        <Link href={`/compare/substitution/${subs[0]!.item.item_id}?plan=${plan.kind}`}>
          {t("walkThrough")}
        </Link>
      </p>
    </section>
  );
}
