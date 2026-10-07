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
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>מפת סניפים</h1>
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
        <h1 className={styles.title}>מפת סניפים</h1>
        <Skeleton height={420} radius={16} />
      </div>
    );
  }
  if (status === "error") {
    return (
      <Empty
        title="לא הצלחנו לטעון את הסניפים"
        body="בדקי את החיבור ונסי שוב מתוצאות ההשוואה."
        href="/compare"
        cta="לתוצאות ההשוואה"
      />
    );
  }
  if (!result || !center || stores.length === 0) {
    return (
      <Empty
        title="אין עדיין השוואה להציג על המפה"
        body="אחרי שתשווי רשימה נציג כאן את הסניפים שברדיוס, כל אחד עם סכום הסל שלו."
        href="/compare"
        cta="לתוצאות ההשוואה"
      />
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
        <h1 className={styles.title}>מפת סניפים</h1>
        <div className={styles.headerActions}>
          <Button href="/compare" size="sm" variant="outline">
            חזרה לתצוגת רשימה
          </Button>
        </div>
      </header>

      {approximate ? (
        <p className={styles.note} data-testid="map-approx">
          <IconInfo size={16} />
          <span>
            המרחק של כל סניף מהמיקום שלך מדויק, אבל הכיוון שלו על המפה מוצג בקירוב עד שנוסיף כתובות
            סניפים מדויקות.
          </span>
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
        {unsupported ? <>המפה לא זמינה במכשיר הזה, מוצג תרשים. </> : null}
        נתוני המפה: ©{" "}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
          תורמי OpenStreetMap
        </a>
        . הדפדפן טוען את המפה מ-OpenStreetMap, ראי <Link href="/privacy">מדיניות הפרטיות</Link>.
      </p>

      <section aria-labelledby="map-list-heading" className={styles.list}>
        <h2 id="map-list-heading" className={styles.sectionTitle}>
          הסניפים ברדיוס
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
                    aria-label={`${store.store_name}, ${formatDistance(store.distance_m)}, סל ₪${pin.total}. לפרטים`}
                  >
                    <span className={styles.storeMain}>
                      <span className={styles.storeName}>{store.store_name}</span>
                      <span className={styles.muted}>
                        {formatDistance(store.distance_m)}
                        {pin.recommended ? " · מומלץ" : ""}
                        {pin.cheapest ? " · הכי זול" : ""}
                        {pin.missingCount > 0 ? ` · חסרים ${pin.missingCount}` : ""}
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

      <p className={styles.muted}>המחיר הקובע הוא בקופה.</p>

      <BottomSheet
        open={selected !== null}
        onClose={() => setSelectedId(null)}
        eyebrow={selected?.chain_name}
        title={selected?.store_name ?? ""}
        footer={
          selected ? (
            <>
              <Button variant="outline" href={`/compare#store-${selected.store_id}`}>
                לכרטיס בתוצאות
              </Button>
              <Button onClick={startShopping}>התחילי קנייה</Button>
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
  const saving = netSavingForStore(result, store);
  return (
    <div className={styles.details} data-testid="store-sheet">
      <dl className={styles.facts}>
        <div>
          <dt>מרחק</dt>
          <dd>{formatDistance(store.distance_m)}</dd>
        </div>
        <div>
          <dt>סכום הסל</dt>
          <dd>
            <Price amount={store.total} size="lg" />
          </dd>
        </div>
        <div>
          <dt>{homeName ? `חיסכון נטו מול ${homeName}` : "חיסכון נטו"}</dt>
          <dd>
            {saving.net !== null ? (
              <>
                <Price amount={saving.net} size="lg" tone={saving.net > 0 ? "good" : "default"} />
                {!saving.fromApi ? <Tag variant="estimated">הערכה, כולל נסיעה</Tag> : null}
              </>
            ) : (
              <span className={styles.muted}>
                כדי לראות חיסכון בחרי את הסופר שלך <Link href="/profile">בפרופיל</Link>
              </span>
            )}
          </dd>
        </div>
      </dl>
      <div className={styles.tags}>
        {store.missing.length > 0 ? (
          <Tag variant="missing">חסרים {store.missing.length} פריטים</Tag>
        ) : (
          <Tag variant="matched">הסל מלא</Tag>
        )}
        {store.substituted_count > 0 ? (
          <Tag variant="differs">{store.substituted_count} תחליפים</Tag>
        ) : null}
      </div>
      <p className={styles.updated}>
        <IconClock size={13} /> מחירים עודכנו {formatTime(store.prices_updated_at)}
      </p>
      <div>
        <ReportGapButton
          label="דווחי על פער במחיר"
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
