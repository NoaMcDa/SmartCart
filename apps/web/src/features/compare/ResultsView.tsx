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
  planUpdatedAt,
  plansOf,
  responseUpdatedAt,
  useOptimize,
} from "@/state/comparison";
import { BudgetRemaining } from "@/features/budget/BudgetRemaining";
import { reportResultsShown, reportSubstitutionsShown } from "@/features/consent/betaEvents";
import { MethodologyLink } from "@/features/seo/components";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { compareMessages } from "@/i18n/messages/compare";
import { sharedMessages } from "@/i18n/messages/shared";
import { productName } from "@/lib/format";
import { cityLabelFor } from "@/features/profile/cities";
import { setFlash, useFlash } from "@/state/flash";
import { basketItems, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import { BasketDetails } from "./BasketDetails";
import { Count } from "./Count";
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
  const t = useT(compareMessages);
  const shared = useT(sharedMessages);
  const { locale } = useLocale();
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

      <BudgetRemaining planTotal={recommended.total} updatedAt={planUpdatedAt(recommended)} />
      <SmartCartCard plan={recommended} />
      <SubstitutionsSection res={res} plan={recommended} />
      <BasketDetails plan={recommended} names={names} />

      <footer className={styles.footnote} data-testid="disclaimer">
        <p>
          <strong>{locale === "he" ? res.disclaimer_he : shared("checkoutGoverns")}</strong>{" "}
          {t("footerBody")} <MethodologyLink>{t("methodologyLink")}</MethodologyLink>
        </p>
        <p className={styles.footRow}>
          <UpdatedAt iso={updated} prefix={shared("pricesUpdated")} withIcon />
          <Button
            variant="ghost"
            size="sm"
            onClick={onReportGap}
            iconStart={<IconInfo size={16} />}
          >
            {t("reportGapButton")}
          </Button>
        </p>
      </footer>
    </div>
  );
}

function LoadingCards() {
  const t = useT(compareMessages);
  return (
    <div className={styles.cards} aria-busy="true" aria-label={t("loadingResults")}>
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
  const t = useT(compareMessages);
  const { locale } = useLocale();
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
      if (it.canonical) m.set(it.canonical.canonical_id, productName(it.canonical, locale));
    }
    return m;
  }, [state.items, locale]);

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
        <h2 className={styles.sectionTitle}>{t("emptyTitle")}</h2>
        <p className={styles.muted}>{t("emptyBody")}</p>
        <Button href="/">{t("buildList")}</Button>
      </Card>
    );
  } else if (result.status === "error" && !data) {
    const offline = !(result.error instanceof ApiError);
    body = (
      <Card className={styles.stateCard} role="alert">
        <h2 className={styles.sectionTitle}>{t("errTitle")}</h2>
        <p className={styles.muted}>{offline ? t("errOffline") : t("errServer")}</p>
        <Button onClick={result.reload}>{t("retry")}</Button>
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
          <Count n={itemCount} noun="items" />
        </span>
        {radiusKm !== null ? (
          <span>
            {" · "}
            {formatRich(t("radiusText"), { km: <span dir="ltr">{radiusKm}</span> })}
            {shopper?.cityLabel
              ? t("fromCity", { city: cityLabelFor(shopper.cityLabel, locale) })
              : ""}
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
        label={t("viewLabel")}
        value="list"
        onChange={(v) => {
          if (v === "map") router.push("/map");
        }}
        options={[
          { value: "list", label: t("viewList"), icon: <IconList size={16} /> },
          { value: "map", label: t("viewMap"), icon: <IconMap size={16} /> },
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
          <h2 className={styles.sectionTitle}>{t("noHomeTitle")}</h2>
          <p className={styles.muted}>{t("noHomeBody")}</p>
          <Button href="/onboarding" variant="outline" size="sm">
            {t("noHomeCta")}
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
