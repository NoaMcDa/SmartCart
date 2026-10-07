"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, type OptimizeResponse, type Plan, type StoreResult } from "@/api/client";
import {
  Button,
  Card,
  IconInfo,
  IconList,
  IconMap,
  SegmentedControl,
  Skeleton,
  SkeletonText,
  UpdatedAt,
} from "@/components/ui";
import {
  buildOptimizeInput,
  homeStore,
  plansOf,
  responseUpdatedAt,
  useOptimize,
} from "@/state/comparison";
import { reportResultsShown, reportSubstitutionsShown } from "@/features/consent/betaEvents";
import { MethodologyLink } from "@/features/seo/components";
import { setFlash, useFlash } from "@/state/flash";
import { basketItems, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import { BasketDetails } from "./BasketDetails";
import { useResolveHomeStore } from "@/features/profile/profileState";
import { PlanCard } from "./PlanCard";
import { ReportGapSheet } from "./ReportGapSheet";
import { SmartCartCard } from "./SmartCartCard";
import { SubstitutionsSection } from "./SubstitutionsSection";
import { substitutionLevelCounts } from "./substitutionLevels";
import styles from "./Results.module.css";

/** Recommended plan first, then the other plan, then the home store (Results artboard). */
export function orderedPlans(res: OptimizeResponse): Plan[] {
  const plans = plansOf(res);
  const rank = (p: Plan) => (p.kind === "minimum_effort" ? 2 : p.recommended ? 0 : 1);
  return [...plans].sort((a, b) => rank(a) - rank(b));
}

export function ResultsContent({
  res,
  names,
  onReportGap,
}: {
  res: OptimizeResponse;
  names: Map<number, string>;
  onReportGap: () => void;
}) {
  const home = homeStore(res);
  const plans = orderedPlans(res);
  const recommended = plans.find((p) => p.recommended) ?? res.single;
  const updated = responseUpdatedAt(res);
  return (
    <div className={styles.content}>
      <div className={styles.cards}>
        {plans.map((plan) => (
          <PlanCard key={plan.kind} plan={plan} home={home} names={names} />
        ))}
      </div>

      <SmartCartCard plan={recommended} />
      <SubstitutionsSection res={res} plan={recommended} />
      <BasketDetails plan={recommended} names={names} />

      <footer className={styles.footnote} data-testid="disclaimer">
        <p>
          <strong>{res.disclaimer_he}</strong> המחירים לפי קבצי שקיפות המחירים של הרשתות, ומבצעי
          מועדון רק לפי המועדונים שסימנת. החיסכון מחושב תמיד מול הסופר שלך, אחרי נסיעה.{" "}
          <MethodologyLink />
        </p>
        <p className={styles.footRow}>
          <UpdatedAt iso={updated} prefix="מחירים עודכנו" withIcon />
          <Button
            variant="ghost"
            size="sm"
            onClick={onReportGap}
            iconStart={<IconInfo size={16} />}
          >
            דיווח על פער במחיר
          </Button>
        </p>
      </footer>
    </div>
  );
}

function LoadingCards() {
  return (
    <div className={styles.cards} aria-busy="true" aria-label="טוען תוצאות">
      {[0, 1, 2].map((i) => (
        <Card key={i} className={styles.plan}>
          <Skeleton width={90} height={22} radius={999} />
          <Skeleton width="70%" height={20} />
          <Skeleton width={120} height={32} />
          <SkeletonText lines={2} />
        </Card>
      ))}
    </div>
  );
}

/**
 * Comparison results (issue #36): /optimize with the list and the shopper context, three plans,
 * substitutions, line details, the checkout disclaimer and report-a-gap.
 */
export function ResultsView() {
  const router = useRouter();
  const { state, hydrated } = useList();
  const shopper = useShopper();
  const flash = useFlash();
  const [gapOpen, setGapOpen] = useState(false);

  const basket = useMemo(() => basketItems(state), [state]);
  const input = useMemo(
    () => (shopper ? buildOptimizeInput(basket, shopper) : null),
    [basket, shopper],
  );
  const result = useOptimize(input);
  const data = "data" in result ? result.data : undefined;

  // Beta events (docs/beta-plan.md): once per response, never any list text or names.
  const reported = useRef<OptimizeResponse | null>(null);
  useEffect(() => {
    if (!data || reported.current === data) return;
    reported.current = data;
    const recommended = plansOf(data).find((p) => p.recommended) ?? data.single;
    reportResultsShown({
      itemCount: basket.length,
      storeCount: new Set(plansOf(data).flatMap((p) => p.stores.map((s) => s.store.store_id))).size,
    });
    reportSubstitutionsShown(substitutionLevelCounts(recommended, state.items));
  }, [data, basket.length, state.items]);

  // Show the message carried over from the substitution card once, then clear it.
  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 8000);
    return () => window.clearTimeout(t);
  }, [flash]);

  const names = useMemo(() => {
    const m = new Map<number, string>();
    for (const it of state.items) {
      if (it.canonical) m.set(it.canonical.canonical_id, it.canonical.display_name_he);
    }
    return m;
  }, [state.items]);

  const itemCount = state.items.filter((i) => !i.notFound).length;
  const radiusKm = shopper ? Math.round(shopper.radiusM / 100) / 10 : null;
  const gapStores = useMemo<StoreResult[]>(
    () =>
      data
        ? [
            ...new Map(
              plansOf(data).flatMap((p) => p.stores.map((s) => [s.store.store_id, s.store])),
            ).values(),
          ]
        : [],
    [data],
  );
  useResolveHomeStore(gapStores);

  let body: ReactNode;
  if (!hydrated || !shopper) {
    body = <LoadingCards />;
  } else if (basket.length === 0) {
    body = (
      <Card className={styles.stateCard}>
        <h2 className={styles.sectionTitle}>אין עדיין מה להשוות</h2>
        <p className={styles.muted}>הוסיפי פריטים לרשימה ונחשב איפה הכי משתלם לקנות אותם.</p>
        <Button href="/">לבניית הרשימה</Button>
      </Card>
    );
  } else if (result.status === "error" && !data) {
    const offline = !(result.error instanceof ApiError);
    body = (
      <Card className={styles.stateCard} role="alert">
        <h2 className={styles.sectionTitle}>לא הצלחנו לחשב את ההשוואה</h2>
        <p className={styles.muted}>
          {offline
            ? "נראה שאין חיבור לשרת. בדקי את החיבור ונסי שוב."
            : "השרת החזיר שגיאה. נסי שוב בעוד רגע."}
        </p>
        <Button onClick={result.reload}>נסי שוב</Button>
      </Card>
    );
  } else if (!data) {
    body = <LoadingCards />;
  } else {
    body = <ResultsContent res={data} names={names} onReportGap={() => setGapOpen(true)} />;
  }

  return (
    <>
      <p className={styles.subline} data-testid="results-subline">
        <span>
          <span dir="ltr">{itemCount}</span> פריטים
        </span>
        {radiusKm !== null ? (
          <span>
            {" · "}עד <span dir="ltr">{radiusKm}</span> ק&quot;מ
            {shopper?.cityLabel ? ` מ${shopper.cityLabel}` : ""}
          </span>
        ) : null}
        {data ? (
          <span>
            {" · "}
            <UpdatedAt iso={responseUpdatedAt(data)} />
          </span>
        ) : null}
      </p>

      <SegmentedControl
        label="תצוגה"
        value="list"
        onChange={(v) => {
          if (v === "map") router.push("/map");
        }}
        options={[
          { value: "list", label: "רשימה", icon: <IconList size={16} /> },
          { value: "map", label: "מפה", icon: <IconMap size={16} /> },
        ]}
        className={styles.toggle}
      />

      <div role="status" aria-live="polite" className={styles.flashRegion}>
        {flash ? (
          <p className={styles.flash} data-testid="flash">
            {flash}
          </p>
        ) : null}
      </div>

      {shopper && shopper.homeStoreId === null ? (
        <Card className={styles.stateCard} data-testid="no-home-store">
          <h2 className={styles.sectionTitle}>מה הסופר שלך?</h2>
          <p className={styles.muted}>
            את החיסכון אנחנו מחשבים רק מול הסופר שבו את קונה בדרך כלל. בחרי אותו ונראה כמה באמת
            נחסך.
          </p>
          <Button href="/onboarding" variant="outline" size="sm">
            בחירת הסופר שלי
          </Button>
        </Card>
      ) : null}

      <div aria-busy={result.status === "loading"}>{body}</div>

      <ReportGapSheet
        open={gapOpen}
        onClose={() => setGapOpen(false)}
        stores={gapStores}
        items={[...names.entries()].map(([canonical_id, name]) => ({ canonical_id, name }))}
      />
    </>
  );
}
