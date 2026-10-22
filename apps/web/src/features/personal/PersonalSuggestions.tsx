"use client";

import { useEffect, useId, useMemo } from "react";
import { Button, Card } from "@/components/ui";
import { reportPersonalization } from "@/features/consent/betaEvents";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { usePlural } from "@/i18n/plural";
import { personalMessages } from "@/i18n/messages/personal";
import { rescueFocus } from "@/lib/focus";
import { productName } from "@/lib/format";
import { getListState, listActions, useList } from "@/state/list";
import {
  brandOffers,
  buyAgainItems,
  usualItems,
  type BuyAgainItem,
  type UsualItem,
} from "./habits";
import { categoryName, parsedRowFor, Qty } from "./personalCopy";
import { personalActions, usePersonal } from "./personalState";
import { StatusNote, useNote } from "./StatusNote";
import { useNow } from "./useNow";
import styles from "./Personal.module.css";

/**
 * On the home screen, above the list: "לקנות שוב?" (items whose usual interval has passed),
 * "הרגילים שלי" (what the person buys most, one tap to add) and, now and then, the offer to make a
 * category's default the exact brand. Everything is computed on this device from the person's own
 * history (`habits.ts`) and nothing is applied without a tap; each card says why it is shown, and
 * "not now" hides it. Nothing renders until the history has loaded, or while learning is off.
 */
export function PersonalSuggestions() {
  const t = useT(personalMessages);
  const { locale } = useLocale();
  const plural = usePlural(personalMessages);
  const { doc, hydrated } = usePersonal();
  const { state } = useList();
  const now = useNow();
  const [note, setNote] = useNote();
  const buyId = useId();
  const usualId = useId();
  const brandId = useId();

  const learning = hydrated && doc.prefs.learn;
  const onList = useMemo(
    () => new Set(state.items.flatMap((i) => (i.canonical ? [i.canonical.canonical_id] : []))),
    [state.items],
  );
  const buyAgain = useMemo(
    () => (learning ? buyAgainItems(doc, now, onList) : []),
    [learning, doc, now, onList],
  );
  const usual = useMemo(() => (learning ? usualItems(doc, now) : []), [learning, doc, now]);
  const usualToAdd = usual.filter((u) => !onList.has(u.ref.canonical_id));
  const offer = useMemo(
    () => (learning ? (brandOffers(doc, state.flexDefaults, now)[0] ?? null) : null),
    [learning, doc, state.flexDefaults, now],
  );

  useEffect(() => {
    if (buyAgain.length > 0) reportPersonalization("buy_again", "shown");
  }, [buyAgain.length]);
  useEffect(() => {
    if (usual.length > 0) reportPersonalization("usual", "shown");
  }, [usual.length]);
  useEffect(() => {
    if (offer) reportPersonalization("brand_default", "shown");
  }, [offer]);

  if (!hydrated || !learning) return null;
  if (buyAgain.length === 0 && usual.length === 0 && !offer && !note) return null;

  function addOne(item: UsualItem | BuyAgainItem, source: "usual" | "buy_again") {
    listActions.add([parsedRowFor(item.ref, item.quantity)]);
    reportPersonalization(source, "accepted");
    setNote({ text: t("usualAdded", { name: productName(item.ref, locale) }) });
  }

  function addAll() {
    listActions.add(usualToAdd.map((u) => parsedRowFor(u.ref, u.quantity)));
    reportPersonalization("usual", "accepted");
    setNote({ text: t("usualAllAdded", { count: usualToAdd.length }) });
  }

  function dismissBuyAgain(item: BuyAgainItem) {
    const key = String(item.ref.canonical_id);
    personalActions.dismiss("buy_again", key);
    reportPersonalization("buy_again", "dismissed");
    setNote({
      text: t("buyDismissed", { name: productName(item.ref, locale) }),
      undo: () => {
        personalActions.undismiss("buy_again", key);
        reportPersonalization("buy_again", "undone");
      },
    });
  }

  function applyOffer() {
    if (!offer) return;
    const category = categoryName(offer.taxonomyId, offer.sample, locale);
    // What the person had saved for exactly this category (not an inherited level), to put back.
    const previous = getListState().flexDefaults[offer.taxonomyId] ?? null;
    listActions.setFlexDefault(offer.taxonomyId, "exact");
    reportPersonalization("brand_default", "accepted");
    setNote({
      text: t("brandApplied", { category }),
      undo: () => {
        listActions.setFlexDefault(offer.taxonomyId, previous);
        // Undone is an answer: not offered again until the signals come back three more times.
        personalActions.dismiss("brand_default", offer.taxonomyId);
        reportPersonalization("brand_default", "undone");
        setNote({ text: t("brandUndone", { category }) });
      },
    });
  }

  function dismissOffer() {
    if (!offer) return;
    const key = offer.taxonomyId;
    personalActions.dismiss("brand_default", key);
    reportPersonalization("brand_default", "dismissed");
    setNote({
      text: t("brandDismissed"),
      undo: () => {
        personalActions.undismiss("brand_default", key);
        reportPersonalization("brand_default", "undone");
      },
    });
  }

  return (
    <div className={styles.stack} data-testid="personal-suggestions">
      {buyAgain.length > 0 ? (
        <Card as="section" aria-labelledby={buyId} className={styles.card} data-testid="buy-again">
          <div className={styles.head}>
            <h2 id={buyId} className={styles.title}>
              {t("buyTitle")}
            </h2>
            <p className={styles.hint}>{t("buyHint")}</p>
          </div>
          <ul className={styles.list}>
            {buyAgain.map((item) => {
              const name = productName(item.ref, locale);
              return (
                <li
                  key={item.ref.canonical_id}
                  className={styles.item}
                  data-testid="buy-again-item"
                >
                  <div className={styles.itemMain}>
                    <span className={styles.itemName}>{name}</span>
                    <span className={styles.itemMeta} data-testid="buy-again-why">
                      {plural("everyDays", item.everyDays, { days: item.everyDays })}
                      {" · "}
                      {plural("sinceDays", item.sinceDays, { days: item.sinceDays })}
                    </span>
                  </div>
                  <div className={styles.actions}>
                    <Button
                      size="sm"
                      variant="outline"
                      aria-label={t("buyAddAria", { name })}
                      onClick={(e) => {
                        rescueFocus(e.currentTarget);
                        addOne(item, "buy_again");
                      }}
                    >
                      {t("buyAdd")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={t("buyDismissAria", { name })}
                      onClick={(e) => {
                        rescueFocus(e.currentTarget);
                        dismissBuyAgain(item);
                      }}
                    >
                      {t("buyDismiss")}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}

      {usual.length > 0 ? (
        <Card as="section" aria-labelledby={usualId} className={styles.card} data-testid="usual">
          <div className={styles.head}>
            <h2 id={usualId} className={styles.title}>
              {t("usualTitle")}
            </h2>
            <p className={styles.hint}>{t("usualHint")}</p>
          </div>
          {usualToAdd.length > 0 ? (
            <>
              <ul className={styles.list}>
                {usualToAdd.map((item) => {
                  const name = productName(item.ref, locale);
                  const kg = item.ref.base_unit === "kg";
                  return (
                    <li
                      key={item.ref.canonical_id}
                      className={styles.item}
                      data-testid="usual-item"
                    >
                      <div className={styles.itemMain}>
                        <span className={styles.itemName}>{name}</span>
                        <span className={styles.itemMeta}>
                          {formatRich(
                            t("usualMeta", { times: plural("times", item.days, { n: item.days }) }),
                            { qty: <Qty quantity={item.quantity} kg={kg} locale={locale} /> },
                          )}
                        </span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={t("usualAddOne", { name })}
                        onClick={(e) => {
                          rescueFocus(e.currentTarget);
                          addOne(item, "usual");
                        }}
                      >
                        {t("buyAdd")}
                      </Button>
                    </li>
                  );
                })}
              </ul>
              <div className={styles.actions}>
                <Button size="sm" onClick={addAll} data-testid="usual-add-all">
                  {t("usualAddAll", { count: usualToAdd.length })}
                </Button>
              </div>
            </>
          ) : (
            <p className={styles.body} data-testid="usual-all-on-list">
              {t("usualAllOnList")}
            </p>
          )}
        </Card>
      ) : null}

      {offer ? (
        <Card
          as="section"
          aria-labelledby={brandId}
          className={`${styles.card} ${styles.offer}`}
          data-testid="brand-offer"
        >
          <h2 id={brandId} className={styles.title}>
            {t("brandTitle")}
          </h2>
          <p className={styles.body}>
            {t("brandBody", {
              category: categoryName(offer.taxonomyId, offer.sample, locale),
              times: plural("times", offer.count, { n: offer.count }),
            })}
          </p>
          <p className={styles.note}>{t("brandNote")}</p>
          <div className={styles.actions}>
            <Button size="sm" onClick={applyOffer} data-testid="brand-apply">
              {t("brandApply")}
            </Button>
            <Button size="sm" variant="ghost" onClick={dismissOffer} data-testid="brand-dismiss">
              {t("brandDismiss")}
            </Button>
          </div>
        </Card>
      ) : null}

      <StatusNote note={note} onClose={() => setNote(null)} />
    </div>
  );
}
