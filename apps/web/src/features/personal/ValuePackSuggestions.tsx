"use client";

import { useEffect, useId, useMemo } from "react";
import { Button, Card, Price, Tag, UpdatedAt } from "@/components/ui";
import { reportPersonalization } from "@/features/consent/betaEvents";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { personalMessages } from "@/i18n/messages/personal";
import { perUnitLabel } from "@/lib/attributes";
import { rescueFocus } from "@/lib/focus";
import { productName } from "@/lib/format";
import { chainLabel } from "@/lib/storeName";
import { getListState, listActions, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import { personalActions, usePersonal } from "./personalState";
import { StatusNote, useNote } from "./StatusNote";
import { useNow } from "./useNow";
import { useValuePacks, visibleValuePacks, type ValuePack } from "./valuePacks";
import styles from "./Personal.module.css";

/**
 * "Prefer value packs" (a profile preference, off by default): below the list, a larger pack of a
 * product on the list where its unit price is lower, with both unit prices, the store and when
 * each price was updated. It is a suggestion with a quantity change behind one tap, never applied
 * by itself, and the change can be undone. Nothing is shown while the preference is off.
 */
export function ValuePackSuggestions() {
  const t = useT(personalMessages);
  const { locale } = useLocale();
  const { doc, hydrated } = usePersonal();
  const { state } = useList();
  const shopper = useShopper();
  const now = useNow();
  const [note, setNote] = useNote();
  const titleId = useId();

  const enabled = hydrated && doc.prefs.value_packs;
  const { packs } = useValuePacks(state.items, shopper, enabled);
  const visible = useMemo(() => visibleValuePacks(packs, doc, now), [packs, doc, now]);

  useEffect(() => {
    if (visible.length > 0) reportPersonalization("value_pack", "shown");
  }, [visible.length]);

  if (!enabled) return null;
  if (visible.length === 0 && !note) return null;

  const nameOf = (canonicalId: number): string => {
    const row = state.items.find((i) => i.canonical?.canonical_id === canonicalId);
    return row?.canonical ? productName(row.canonical, locale) : "";
  };

  function apply(pack: ValuePack) {
    const rows = getListState().items.filter((i) => i.canonical?.canonical_id === pack.canonicalId);
    const first = rows[0];
    if (!first) return;
    const others = rows.slice(1).reduce((sum, r) => sum + r.quantity, 0);
    const before = first.quantity;
    const to = Math.round((pack.quantityToSet - others) * 1000) / 1000;
    if (!(to > 0)) return;
    const name = nameOf(pack.canonicalId);
    listActions.setQuantity(first.id, to);
    reportPersonalization("value_pack", "accepted");
    setNote({
      text: t("packApplied", { name, to: pack.quantityToSet }),
      undo: () => {
        listActions.setQuantity(first.id, before);
        reportPersonalization("value_pack", "undone");
        setNote({ text: t("packUndone", { name, from: pack.quantity }) });
      },
    });
  }

  function dismiss(pack: ValuePack) {
    const key = String(pack.canonicalId);
    personalActions.dismiss("value_pack", key);
    reportPersonalization("value_pack", "dismissed");
    setNote({
      text: t("packDismissed", { name: nameOf(pack.canonicalId) }),
      undo: () => {
        personalActions.undismiss("value_pack", key);
        reportPersonalization("value_pack", "undone");
      },
    });
  }

  return (
    <>
      {visible.length > 0 ? (
        <Card
          as="section"
          aria-labelledby={titleId}
          className={styles.card}
          data-testid="value-packs"
        >
          <div className={styles.head}>
            <h2 id={titleId} className={styles.title}>
              {t("packTitle")}
            </h2>
            <p className={styles.hint}>{t("packHint")}</p>
          </div>
          <ul className={styles.list}>
            {visible.map((pack) => {
              const name = nameOf(pack.canonicalId);
              const per = perUnitLabel(pack.uom, locale);
              return (
                <li
                  key={pack.canonicalId}
                  className={styles.item}
                  data-testid="value-pack"
                  data-trust-scope="value-pack"
                >
                  <div className={styles.itemMain}>
                    <div className={styles.packHead}>
                      <span className={styles.itemName}>{name}</span>
                      <Tag variant="differs">{t("packTag")}</Tag>
                    </div>
                    <dl className={styles.compare}>
                      <div>
                        <dt>{t("packNow", { units: pack.current.packUnits })}</dt>
                        <dd>
                          <span>
                            <Price amount={pack.current.unitPrice} fractionDigits={2} /> {per}
                          </span>
                          <UpdatedAt iso={pack.current.updatedAt} className={styles.itemMeta} />
                        </dd>
                      </div>
                      <div>
                        <dt>{t("packLarger", { units: pack.larger.packUnits })}</dt>
                        <dd>
                          <span>
                            <Price amount={pack.larger.unitPrice} fractionDigits={2} tone="good" />{" "}
                            {per}
                          </span>
                          <UpdatedAt iso={pack.larger.updatedAt} className={styles.itemMeta} />
                        </dd>
                      </div>
                    </dl>
                    <p className={styles.itemMeta}>
                      {t("packSaving", { pct: pack.unitSavingPct })}
                      {" · "}
                      {t("packStore", { store: chainLabel(pack.store.chain, locale) })}
                    </p>
                    <p className={styles.itemMeta}>
                      {formatRich(t("packMore"), {
                        from: <span dir="ltr">{pack.quantity}</span>,
                        to: <span dir="ltr">{pack.quantityToSet}</span>,
                      })}{" "}
                      {t("packCheckout")}
                    </p>
                    <div className={styles.actions}>
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={t("packApplyAria", { name })}
                        onClick={(e) => {
                          rescueFocus(e.currentTarget, { neighbors: false });
                          apply(pack);
                        }}
                      >
                        {t("packApply")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={t("packDismissAria", { name })}
                        onClick={(e) => {
                          rescueFocus(e.currentTarget);
                          dismiss(pack);
                        }}
                      >
                        {t("packDismiss")}
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}
      {/* Always the same place in the tree: the live region keeps announcing when the card is gone. */}
      <StatusNote note={note} onClose={() => setNote(null)} testId="value-pack-status" />
    </>
  );
}
