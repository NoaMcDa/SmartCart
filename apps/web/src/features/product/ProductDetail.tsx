"use client";

import { useEffect, useState } from "react";
import {
  compare,
  search,
  type CanonicalRef,
  type CompareResponse,
  type FlexLevel,
} from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Chip, FlexChip } from "@/components/ui/Chip";
import { Price } from "@/components/ui/Price";
import { PromoConfidence } from "@/components/ui/PromoConfidence";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tag } from "@/components/ui/Tag";
import { AlertMe } from "@/features/alerts/AlertMe";
import { PriceHistory, type HistoryStoreOption } from "@/features/history/PriceHistory";
import { IconClock } from "@/components/ui/icons";
import { ReportGapButton } from "@/features/feedback/GapReportSheet";
import { useShopper } from "@/state/shopper";
import { useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { productMessages, type ProductMessageKey } from "@/i18n/messages/product";
import { formatDistance } from "@/lib/format";
import { listActions } from "@/state/list";
import { formatUpdated, storeRows, variantsOf, type StoreRow } from "./productData";
import styles from "./Product.module.css";

const NEXT_LEVEL: Record<FlexLevel, FlexLevel> = {
  any_brand: "exact",
  exact: "close",
  close: "any_brand",
};

type State =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; compare: CompareResponse; categoryPath: string[]; ref: CanonicalRef | null };

/** The result of one request, tagged with the request it answers (so a stale one is ignored). */
type Loaded =
  | { key: string; error: true }
  | {
      key: string;
      error?: false;
      compare: CompareResponse;
      categoryPath: string[];
      ref: CanonicalRef | null;
    };

/**
 * Product detail (issue #50): the canonical name, variants ranked by unit price, and what it costs
 * at each store in the radius, every price with its update time (D10). Phase 2 adds the 90-day
 * price history chart (issue #28) and the working "alert me below" form (issue #23).
 *
 * Data: one /compare call for this canonical (quantity 1) at the profile's location. The name comes
 * from the `?name=` hint the linking screen passes (the compare lines only carry chain item names).
 */
export function ProductDetail({
  canonicalId,
  nameHint,
}: {
  canonicalId: number;
  nameHint: string | null;
}) {
  const t = useT(productMessages);
  const r = useRich(productMessages);
  const { locale } = useLocale();
  const shopper = useShopper();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [level, setLevel] = useState<FlexLevel>("any_brand");
  const [added, setAdded] = useState(false);

  // Location, radius, home store and clubs come from the shared shopper context (W4b state).
  const lat = shopper?.lat;
  const lon = shopper?.lon;
  const radius = shopper?.radiusM;
  const home = shopper?.homeStoreId ?? null;
  const clubsKey = shopper ? shopper.clubs.join("|") : "";
  const requestKey = `${canonicalId}|${nameHint ?? ""}|${lat}|${lon}|${radius}|${home}|${clubsKey}`;

  // The price query is always "any brand": the flexibility chip below only sets the level of the
  // list entry ("exact" would need a barcode to price).
  useEffect(() => {
    if (lat === undefined || lon === undefined) return;
    let cancelled = false;
    void (async () => {
      try {
        const [result, hits] = await Promise.all([
          compare({
            items: [{ canonical_id: canonicalId, quantity: 1, flex_level: "any_brand" }],
            location: { lat, lon, radius_m: radius },
            home_store_id: home,
            clubs: clubsKey ? clubsKey.split("|") : [],
          }),
          nameHint ? search(nameHint, 5).catch(() => null) : Promise.resolve(null),
        ]);
        if (cancelled) return;
        const hit = hits?.hits.find((h) => h.canonical.canonical_id === canonicalId);
        setLoaded({
          key: requestKey,
          compare: result,
          categoryPath: hit?.canonical.category_path_he ?? [],
          ref: hit?.canonical ?? null,
        });
      } catch {
        if (!cancelled) setLoaded({ key: requestKey, error: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canonicalId, nameHint, lat, lon, radius, home, clubsKey, requestKey]);

  const current = loaded && loaded.key === requestKey ? loaded : null;
  const state: State = !current
    ? { kind: "loading" }
    : current.error
      ? { kind: "error" }
      : {
          kind: "ready",
          compare: current.compare,
          categoryPath: current.categoryPath,
          ref: current.ref,
        };

  const readyCompare = state.kind === "ready" ? state.compare : null;
  const rows = readyCompare ? storeRows(readyCompare, canonicalId) : [];
  const variants = variantsOf(rows, locale);
  const title = nameHint ?? variants[0]?.name ?? t("pageTitle");
  const unitText = variants[0]?.unitLabel ?? t("perUnitDefault");

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        {state.kind === "ready" && state.categoryPath.length > 0 ? (
          <nav aria-label={t("categoryNav")}>
            <ol className={styles.crumbs}>
              {state.categoryPath.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ol>
          </nav>
        ) : null}
        <h1 className={styles.title}>{title}</h1>
        <div className={styles.headerActions}>
          <FlexChip
            level={level}
            onClick={() => {
              setLevel(NEXT_LEVEL[level]);
              setAdded(false);
            }}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              addToList(canonicalId, title, level, state.kind === "ready" ? state.ref : null);
              setAdded(true);
            }}
          >
            {t("addToList")}
          </Button>
          {added ? (
            <span role="status" className={styles.added}>
              {t("added")}
            </span>
          ) : null}
        </div>
      </header>

      {state.kind === "loading" ? (
        <Card aria-busy="true" aria-label={t("loadingPrices")}>
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </Card>
      ) : null}

      {state.kind === "error" ? (
        <Card role="alert">
          <p>{t("loadError")}</p>
        </Card>
      ) : null}

      {state.kind === "ready" && rows.length === 0 ? (
        <Card data-testid="product-empty">
          <p>{t("noPrice")}</p>
        </Card>
      ) : null}

      {state.kind === "ready" && rows.length > 0 ? (
        <>
          <section aria-labelledby="variants-heading" className={styles.section}>
            <h2 id="variants-heading" className={styles.sectionTitle}>
              {t("variantsHeading")}
            </h2>
            <Card padding="none">
              <ol className={styles.variants} data-testid="variants">
                {variants.map((v, i) => (
                  <li key={v.name} className={styles.variant}>
                    <span className={styles.rank} aria-hidden="true">
                      {i + 1}
                    </span>
                    <div className={styles.variantMain}>
                      <span className={styles.variantName}>{v.name}</span>
                      <span className={styles.muted}>
                        {r(
                          "cheapestAt",
                          { ltr: (c) => <span dir="ltr">{c}</span> },
                          { store: v.cheapestStore, count: v.storeCount },
                        )}
                      </span>
                      <span className={styles.tags}>
                        {v.isEstimated ? (
                          <Tag variant="estimated">{t("estimatedWeighed")}</Tag>
                        ) : null}
                        {v.isSubstitute ? <Tag variant="differs">{t("substitute")}</Tag> : null}
                      </span>
                    </div>
                    <span className={styles.unit}>
                      <Price amount={v.unitPrice} fractionDigits={2} size="md" />
                      <span className={styles.muted}>{v.unitLabel}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          </section>

          <section aria-labelledby="stores-heading" className={styles.section}>
            <h2 id="stores-heading" className={styles.sectionTitle}>
              {t("storesHeading")}
            </h2>
            <Card padding="none">
              <table className={styles.table} data-testid="store-prices">
                <caption className="sr-only">{t("tableCaption")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("colStore")}</th>
                    <th scope="col">{t("colShelf")}</th>
                    <th scope="col">{t("colFinal")}</th>
                    <th scope="col">
                      <span className="sr-only">{t("colReport")}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ store, item, effective, shelf }) => {
                    const member = item.club_name
                      ? (shopper?.clubs.includes(item.club_name) ?? false)
                      : false;
                    const hasPromo = Boolean(item.promo_description) || item.club_required;
                    return (
                      <tr key={store.store_id}>
                        <th scope="row" className={styles.storeCell}>
                          <span className={styles.storeName}>{store.store_name}</span>
                          <span className={styles.muted}>
                            {formatDistance(store.distance_m)} · {item.display_name_he}
                          </span>
                          {item.is_substitute ? (
                            <Tag variant="differs">{t("substitute")}</Tag>
                          ) : null}
                        </th>
                        <td data-label={t("colShelf")} className={styles.shelfCell}>
                          <Price amount={shelf} tone="muted" />
                          {item.is_estimated ? (
                            <Tag variant="estimated">{t("estimatedShort")}</Tag>
                          ) : null}
                        </td>
                        <td data-label={t("colFinal")} className={styles.finalCell}>
                          <Price amount={effective} size="md" />
                          {hasPromo ? (
                            <span className={styles.promo}>
                              {item.club_required ? (
                                <Chip tone="accent" size="sm">
                                  {item.club_name
                                    ? t("clubPromoNamed", { club: item.club_name })
                                    : t("clubPromo")}
                                </Chip>
                              ) : (
                                <Chip tone="neutral" size="sm">
                                  {item.promo_description}
                                </Chip>
                              )}
                              {item.club_required && !member ? (
                                <span className={styles.muted}>{t("clubOnly")}</span>
                              ) : null}
                              <PromoConfidence confidence={item.promo_confidence} />
                            </span>
                          ) : null}
                          <span className={styles.updated}>
                            <IconClock size={12} />{" "}
                            {t("updated", {
                              time: formatUpdated(item.price_valid_from, new Date(), locale),
                            })}
                          </span>
                        </td>
                        <td className={styles.reportCell}>
                          <ReportGapButton
                            label={t("reportShort")}
                            context={{
                              storeId: store.store_id,
                              storeName: store.store_name,
                              canonicalId,
                              itemId: item.item_id,
                              itemName: item.display_name_he,
                              shownPrice: effective,
                              priceUpdatedAt: item.price_valid_from,
                            }}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
            <p className={styles.footnote}>{t("footnote")}</p>
          </section>
        </>
      ) : null}

      {state.kind !== "loading" ? (
        <PriceHistory
          canonicalId={canonicalId}
          stores={historyStores(rows, home, t)}
          unitLabel={unitText}
        />
      ) : null}

      <AlertMe canonicalId={canonicalId} name={title} unitLabel={unitText} />
    </div>
  );
}

/**
 * Adds the product to the shared list (W4b `listActions`) at the chosen flexibility. Without the
 * search hit's reference (no `?name=` hint) a minimal reference is built from the name.
 */
function addToList(canonicalId: number, name: string, level: FlexLevel, ref: CanonicalRef | null) {
  const canonical: CanonicalRef = ref ?? {
    canonical_id: canonicalId,
    display_name_he: name,
    taxonomy_id: "",
    base_unit: "unit",
  };
  const next = listActions.add([
    {
      input_text: name,
      canonical,
      confidence: 1,
      needs_confirmation: false,
      not_found: false,
      candidates: [],
      quantity: "1",
      flex_level: level,
      is_weighed: false,
    },
  ]);
  const row = next.items.find((i) => i.canonical?.canonical_id === canonicalId);
  // A remembered category default would win over `level` when the row is created; the user's
  // choice on this screen is explicit, so set it on the row.
  if (row) listActions.setFlex(row.id, { level, allow: row.allow, remember: false });
}

/** The stores the history can be shown for: my store, the cheapest nearby, the chain base price. */
function historyStores(
  rows: ReadonlyArray<StoreRow>,
  homeStoreId: number | null,
  t: (key: ProductMessageKey, vars?: Record<string, string | number>) => string,
): HistoryStoreOption[] {
  const options: HistoryStoreOption[] = [];
  if (homeStoreId !== null) {
    const mine = rows.find((r) => r.store.store_id === homeStoreId);
    options.push({
      storeId: homeStoreId,
      label: mine ? t("historyMineChain", { chain: mine.store.chain_name }) : t("historyMine"),
    });
  }
  const cheapest = rows[0];
  if (cheapest && cheapest.store.store_id !== homeStoreId) {
    options.push({
      storeId: cheapest.store.store_id,
      label: t("historyCheapest", { chain: cheapest.store.chain_name }),
    });
  }
  options.push({ storeId: null, label: t("historyBase") });
  return options;
}
