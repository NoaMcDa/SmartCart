"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useState } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Price } from "@/components/ui/Price";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tag } from "@/components/ui/Tag";
import { IconClock, IconInfo } from "@/components/ui/icons";
import { ReportGapButton } from "@/features/feedback/GapReportSheet";
import {
  homeStoreOf,
  useComparison,
  wholeBasketStores,
  type LastResult,
} from "@/features/split/lastResult";
import { netSavingForStore } from "@/features/split/savings";
import { buildSession, startSession } from "@/features/store/session";
import { useRich } from "@/i18n/format-2";
import { useT } from "@/i18n/LocaleProvider";
import { mapMessages } from "@/i18n/messages/map";
import { formatDistance, formatTime } from "@/lib/format";
import { useRouter } from "next/navigation";
import { FallbackMap } from "./FallbackMap";
import { storePosition, type LatLon } from "./geo";
import type { Pin } from "./PinButton";
import styles from "./Map.module.css";

// MapLibre is large and needs WebGL and the DOM: load it on demand, only on this route.
const MapCanvas = dynamic(() => import("./MapCanvas"), {
  ssr: false,
  loading: () => <Skeleton height={420} radius={16} />,
});

function Empty({
  title,
  body,
  href,
  cta,
}: {
  title: string;
  body: string;
  href: string;
  cta: string;
}) {
  const t = useT(mapMessages);
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{t("title")}</h1>
      <Card data-testid="map-empty">
        <h2 className={styles.sectionTitle}>{title}</h2>
        <p className={styles.muted}>{body}</p>
        <div>
          <Button href={href} size="sm">
            {cta}
          </Button>
        </div>
      </Card>
    </div>
  );
}

function recommendedStoreIds(result: LastResult): Set<number> {
  const o = result.optimize;
  const plan = [o?.single, o?.split, o?.minimum_effort].find((p) => p?.recommended);
  return new Set(plan?.stores.map((a) => a.store.store_id) ?? []);
}

/**
 * Map view (issue #59): one pin per store from the last comparison, each showing the basket
 * total; tapping a pin opens a bottom sheet with that store's details and net saving (D7).
 * The list under the map is the accessible alternative and also the fallback when WebGL is off.
 */
export function MapScreen() {
  const t = useT(mapMessages);
  const r = useRich(mapMessages);
  const { status, result } = useComparison();
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  // The comparison is always centred on the shopper's neighborhood-rounded location (D11).
  const center: (LatLon & { radiusM: number }) | null = useMemo(
    () =>
      result?.location
        ? {
            lat: result.location.lat,
            lon: result.location.lon,
            radiusM: result.location.radius_m,
          }
        : null,
    [result],
  );

  const stores = useMemo(() => (result ? wholeBasketStores(result) : []), [result]);

  const { pins, approximate } = useMemo(() => {
    if (!result || !center)
      return { pins: [] as Array<Pin & { position: LatLon }>, approximate: false };
    const recommended = recommendedStoreIds(result);
    const complete = stores.filter((s) => s.missing.length === 0).map((s) => Number(s.total));
    const cheapestTotal = complete.length > 0 ? Math.min(...complete) : null;
    let approx = false;
    const list = stores.map((s) => {
      const position = storePosition(s, center);
      approx ||= position.approximate;
      return {
        storeId: s.store_id,
        storeName: s.store_name,
        chainName: s.chain_name,
        total: Number(s.total),
        missingCount: s.missing.length,
        recommended: recommended.has(s.store_id),
        cheapest:
          s.missing.length === 0 && cheapestTotal !== null && Number(s.total) === cheapestTotal,
        position,
      };
    });
    return { pins: list, approximate: approx };
  }, [result, center, stores]);

  if (status === "loading") {
    return (
      <div className={styles.page} aria-busy="true">
        <h1 className={styles.title}>{t("title")}</h1>
        <Skeleton height={420} radius={16} />
      </div>
    );
  }
  if (status === "error") {
    return (
      <Empty title={t("errorTitle")} body={t("errorBody")} href="/compare" cta={t("toResults")} />
    );
  }
  if (!result || !center || stores.length === 0) {
    return (
      <Empty title={t("emptyTitle")} body={t("emptyBody")} href="/compare" cta={t("toResults")} />
    );
  }
  const selected = stores.find((s) => s.store_id === selectedId) ?? null;
  const homeName = homeStoreOf(result)?.chain_name ?? null;

  function startShopping() {
    if (!selected || !result) return;
    const saving = netSavingForStore(result, selected);
    startSession(
      buildSession(selected, result, { overhead: saving.net === null ? null : saving.travel }),
    );
    router.push(`/store-mode?store=${selected.store_id}`);
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{t("title")}</h1>
        <div className={styles.headerActions}>
          <Button href="/compare" size="sm" variant="outline">
            {t("backToList")}
          </Button>
        </div>
      </header>

      {approximate ? (
        <p className={styles.note} data-testid="map-approx">
          <IconInfo size={16} />
          <span>{t("approxNote")}</span>
        </p>
      ) : null}

      <div className={styles.mapWrap}>
        {unsupported ? (
          <FallbackMap
            center={center}
            radiusM={center.radiusM}
            pins={pins}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        ) : (
          <MapCanvas
            center={center}
            radiusM={center.radiusM}
            pins={pins}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onUnsupported={() => setUnsupported(true)}
          />
        )}
      </div>
      <p className={styles.attribution}>
        {unsupported ? t("mapUnavailable") : null}
        {r("attribution", {
          osm: (c) => (
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noopener noreferrer"
            >
              {c}
            </a>
          ),
          privacy: (c) => <Link href="/privacy">{c}</Link>,
        })}
      </p>

      <section aria-labelledby="map-list-heading" className={styles.list}>
        <h2 id="map-list-heading" className={styles.sectionTitle}>
          {t("storesHeading")}
        </h2>
        <Card padding="none">
          <ul className={styles.storeList} data-testid="map-store-list">
            {pins.map((pin) => {
              const store = stores.find((s) => s.store_id === pin.storeId)!;
              return (
                <li key={pin.storeId}>
                  <button
                    type="button"
                    className={styles.storeRow}
                    onClick={() => setSelectedId(pin.storeId)}
                    aria-label={t("storeRowAria", {
                      store: store.store_name,
                      distance: formatDistance(store.distance_m),
                      total: pin.total,
                    })}
                  >
                    <span className={styles.storeMain}>
                      <span className={styles.storeName}>{store.store_name}</span>
                      <span className={styles.muted}>
                        {formatDistance(store.distance_m)}
                        {pin.recommended ? ` · ${t("recommended")}` : ""}
                        {pin.cheapest ? ` · ${t("cheapest")}` : ""}
                        {pin.missingCount > 0
                          ? ` · ${t("missingShort", { count: pin.missingCount })}`
                          : ""}
                      </span>
                    </span>
                    <Price amount={pin.total} size="md" />
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>
      </section>

      <p className={styles.muted}>{t("checkoutGoverns")}</p>

      <BottomSheet
        open={selected !== null}
        onClose={() => setSelectedId(null)}
        eyebrow={selected?.chain_name}
        title={selected?.store_name ?? ""}
        footer={
          selected ? (
            <>
              <Button variant="outline" href={`/compare#store-${selected.store_id}`}>
                {t("toCard")}
              </Button>
              <Button onClick={startShopping}>{t("startShopping")}</Button>
            </>
          ) : undefined
        }
      >
        {selected ? <StoreDetails result={result} store={selected} homeName={homeName} /> : null}
      </BottomSheet>
    </div>
  );
}

function StoreDetails({
  result,
  store,
  homeName,
}: {
  result: LastResult;
  store: ReturnType<typeof wholeBasketStores>[number];
  homeName: string | null;
}) {
  const t = useT(mapMessages);
  const r = useRich(mapMessages);
  const saving = netSavingForStore(result, store);
  return (
    <div className={styles.details} data-testid="store-sheet">
      <dl className={styles.facts}>
        <div>
          <dt>{t("distance")}</dt>
          <dd>{formatDistance(store.distance_m)}</dd>
        </div>
        <div>
          <dt>{t("basketTotal")}</dt>
          <dd>
            <Price amount={store.total} size="lg" />
          </dd>
        </div>
        <div>
          <dt>{homeName ? t("netSavingVs", { home: homeName }) : t("netSaving")}</dt>
          <dd>
            {saving.net !== null ? (
              <>
                <Price amount={saving.net} size="lg" tone={saving.net > 0 ? "good" : "default"} />
                {!saving.fromApi ? <Tag variant="estimated">{t("estimatedTravel")}</Tag> : null}
              </>
            ) : (
              <span className={styles.muted}>
                {r("pickHome", { profile: (c) => <Link href="/profile">{c}</Link> })}
              </span>
            )}
          </dd>
        </div>
      </dl>
      <div className={styles.tags}>
        {store.missing.length > 0 ? (
          <Tag variant="missing">{t("missingItems", { count: store.missing.length })}</Tag>
        ) : (
          <Tag variant="matched">{t("basketComplete")}</Tag>
        )}
        {store.substituted_count > 0 ? (
          <Tag variant="differs">{t("substitutes", { count: store.substituted_count })}</Tag>
        ) : null}
      </div>
      <p className={styles.updated}>
        <IconClock size={13} /> {t("pricesUpdated", { time: formatTime(store.prices_updated_at) })}
      </p>
      <div>
        <ReportGapButton
          label={t("reportPriceGap")}
          context={{
            storeId: store.store_id,
            storeName: store.store_name,
            shownPrice: store.total,
            priceUpdatedAt: store.prices_updated_at,
          }}
        />
      </div>
    </div>
  );
}
