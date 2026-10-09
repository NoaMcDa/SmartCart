"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { StoreResult } from "@/api/client";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Price } from "@/components/ui/Price";
import { Skeleton } from "@/components/ui/Skeleton";
import { Switch } from "@/components/ui/Switch";
import { Tag } from "@/components/ui/Tag";
import { IconCheck, IconClock, IconInfo } from "@/components/ui/icons";
import { useAuth } from "@/features/auth/AuthProvider";
import { recordSpend } from "@/features/budget/spendState";
import { pushPendingSpend } from "@/features/budget/sync";
import { ReportGapButton } from "@/features/feedback/GapReportSheet";
import { recordSaving } from "@/features/profile/savingsHistory";
import { useComparison, type LastResult } from "@/features/split/lastResult";
import { netSavingForStore } from "@/features/split/savings";
import { trackEvent } from "@/features/seo/track";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { ItemName } from "@/components/ui/ItemName";
import { DataText } from "@/i18n/DataText";
import { formatRich } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { sharedMessages } from "@/i18n/messages/shared";
import { storeMessages } from "@/i18n/messages/store";
import { translatePlural } from "@/i18n/plural";
import { formatTime } from "@/lib/format";
import { storeLabel } from "@/lib/storeName";
import { detectPlatform } from "@/lib/platform";
import { resolveDepartments } from "./departments";
import { useOnline, useWakeLock, warmStoreModePage } from "./device";
import {
  buildSession,
  clearSession,
  groupByDepartment,
  progressOf,
  realizedSaving,
  setChecked,
  startSession,
  useSession,
  type ShopItem,
} from "./session";
import styles from "./StoreMode.module.css";

function pickStore(result: LastResult, storeId: number, plan: string | null): StoreResult | null {
  const o = result.optimize;
  if (plan === "split") {
    const part = o?.split?.stores.find((a) => a.store.store_id === storeId);
    if (part) return part.store;
  }
  return (
    result.compare?.stores.find((s) => s.store_id === storeId) ??
    [o?.single, o?.minimum_effort, o?.split]
      .flatMap((p) => p?.stores ?? [])
      .find((a) => a.store.store_id === storeId)?.store ??
    null
  );
}

/** Travel and extra-stop cost attributed to a trip to `store` under the chosen plan (D7). */
function overheadFor(result: LastResult, store: StoreResult, plan: string | null): number | null {
  const split = result.optimize?.split;
  if (plan === "split" && split?.breakdown) {
    return (
      (Number(split.breakdown.travel_cost) + Number(split.breakdown.extra_stop_cost)) /
      Math.max(1, split.stores.length)
    );
  }
  const saving = netSavingForStore(result, store);
  return saving.net === null ? null : saving.travel;
}

function Empty() {
  const t = useT(storeMessages);
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>{t("title")}</h1>
      <Card data-testid="store-empty">
        <h2 className={styles.sectionTitle}>{t("emptyTitle")}</h2>
        <p className={styles.muted}>{t("emptyBody")}</p>
        <div>
          <Button href="/compare" size="sm">
            {t("emptyCta")}
          </Button>
        </div>
      </Card>
    </div>
  );
}

/**
 * In-store mode (issue #66): the chosen store's items by department, with large check targets, a
 * progress count and a running total. `?store=<id>` starts a session from the last comparison
 * (`&plan=split` for a split part); the Split and Map screens start theirs themselves. All data
 * is copied into localStorage at the start, so it works offline and after a reload.
 */
function StoreModeInner() {
  const t = useT(storeMessages);
  const shared = useT(sharedMessages);
  const { locale } = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const storeParam = Number(params.get("store")) || null;
  const planParam = params.get("plan");
  const session = useSession();
  const { result } = useComparison();
  const online = useOnline();
  const auth = useAuth();
  const [finishOpen, setFinishOpen] = useState(false);
  // "סיימתי לקנות" also adds the shop to the monthly budget (issue #70); the person can opt out here.
  const [recordInBudget, setRecordInBudget] = useState(true);
  const [undo, setUndo] = useState<{ itemId: number; name: string } | null>(null);
  const resolving = useRef(false);
  // Set when the user finishes, so the "start from ?store=" effect does not open a new session
  // in the moment between clearing the old one and leaving the page.
  const finishing = useRef(false);

  // Start a session for ?store= when there is none for that store yet.
  useEffect(() => {
    if (finishing.current || !storeParam || !result) return;
    if (session && session.storeId === storeParam) return;
    const store = pickStore(result, storeParam, planParam);
    if (!store) return;
    startSession(
      buildSession(store, result, {
        overhead: overheadFor(result, store, planParam),
        plan: planParam === "split" ? "split" : "single",
      }),
    );
  }, [storeParam, planParam, result, session]);

  // Departments for the checklist (once), then keep the page itself available offline.
  useEffect(() => {
    if (!session || session.departmentsResolved || resolving.current) return;
    resolving.current = true;
    void resolveDepartments(session).finally(() => {
      resolving.current = false;
    });
  }, [session]);
  useEffect(() => {
    if (session) void warmStoreModePage();
  }, [session?.storeId]); // eslint-disable-line react-hooks/exhaustive-deps

  useWakeLock(Boolean(session));

  // Native-app decision (#56): store mode opened with a plan. Once per shopping session.
  const reportedSession = useRef<string | null>(null);
  useEffect(() => {
    if (!session || reportedSession.current === session.startedAt) return;
    reportedSession.current = session.startedAt;
    trackEvent("store_mode_used", { plan: session.plan ?? "single", platform: detectPlatform() });
  }, [session]);

  // Undo snackbar disappears by itself.
  useEffect(() => {
    if (!undo) return;
    const t = setTimeout(() => setUndo(null), 6000);
    return () => clearTimeout(t);
  }, [undo]);

  const groups = useMemo(
    () => (session ? groupByDepartment(session.items, locale) : []),
    [session, locale],
  );

  if (!session) {
    // A start is pending when the URL names a store and a result exists.
    return storeParam && result ? (
      <div className={styles.page} aria-busy="true">
        <h1 className={styles.title}>{t("title")}</h1>
        <Skeleton height={64} radius={16} />
        <Skeleton height={64} radius={16} />
      </div>
    ) : (
      <Empty />
    );
  }

  const progress = progressOf(session);
  const saving = realizedSaving(session);
  const unchecked = session.items.filter((i) => !i.checked);

  function toggle(item: ShopItem) {
    setChecked(item.itemId, !item.checked);
    setUndo(item.checked ? null : { itemId: item.itemId, name: item.name });
  }

  // What the budget records: the prices of what was collected, or, when nothing was ticked, the
  // whole plan for this store. Always the prices the app showed, never a receipt.
  const spend =
    progress.checked > 0
      ? { total: progress.checkedTotal, count: progress.checked, ofPlan: false }
      : { total: progress.allTotal, count: progress.total, ofPlan: true };

  function finish() {
    if (!session) return;
    if (saving !== null && progress.checked > 0) {
      recordSaving({ storeName: session.storeName, listName: session.listName, net: saving });
    }
    if (recordInBudget && spend.total > 0) {
      const signedIn = auth.status === "signed-in";
      recordSpend({
        storeId: session.storeId,
        storeName: session.storeName,
        total: spend.total,
        itemCount: spend.count,
        plan: session.plan ?? "single",
        pending: signedIn,
      });
      if (signedIn) void pushPendingSpend();
    }
    finishing.current = true;
    clearSession();
    router.push("/");
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{t("title")}</h1>
        <p className={styles.storeName}>{storeLabel(session.storeName, locale)}</p>
        {!online ? (
          <p className={styles.offline} role="status" data-testid="offline-banner">
            <IconInfo size={16} /> {t("offline")}
          </p>
        ) : null}
      </header>

      <Card className={styles.progressCard} data-testid="progress-card">
        <div className={styles.progressRow}>
          <span className={styles.progressText} data-testid="progress-count">
            {formatRich(t("collectedOf"), {
              checked: <span dir="ltr">{progress.checked}</span>,
              total: <span dir="ltr">{progress.total}</span>,
            })}
          </span>
          <span className={styles.muted}>
            {formatRich(t("inCart"), {
              checked: <Price amount={progress.checkedTotal} />,
              all: <Price amount={progress.allTotal} />,
            })}
          </span>
        </div>
        <div
          role="progressbar"
          aria-label={t("progressLabel")}
          aria-valuemin={0}
          aria-valuemax={progress.total}
          aria-valuenow={progress.checked}
          aria-valuetext={t("collectedOf", { checked: progress.checked, total: progress.total })}
          className={styles.bar}
        >
          <span
            className={styles.barFill}
            style={{
              inlineSize: `${progress.total ? (progress.checked / progress.total) * 100 : 0}%`,
            }}
          />
        </div>
        {session.missingCount > 0 ? (
          <Tag variant="missing">
            {translatePlural(storeMessages, locale, "missing", session.missingCount, {
              n: session.missingCount,
            })}
          </Tag>
        ) : null}
      </Card>

      {groups.map((group) => (
        <section
          key={group.department}
          aria-labelledby={`dept-${group.department}`}
          className={styles.group}
        >
          <h2 id={`dept-${group.department}`} className={styles.groupTitle}>
            {group.label}
          </h2>
          <ul className={styles.items}>
            {group.items.map((item) => (
              <li key={item.itemId} className={styles.itemWrap} data-checked={item.checked}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={item.checked}
                  className={styles.item}
                  data-testid="shop-item"
                  data-checked={item.checked}
                  onClick={() => toggle(item)}
                >
                  <span className={styles.box} aria-hidden="true">
                    {item.checked ? <IconCheck size={22} /> : null}
                  </span>
                  <span className={styles.itemText}>
                    <span className={styles.itemName}>
                      <ItemName
                        item={{ display_name_he: item.name, canonical_name_ar: item.nameAr }}
                        show="line"
                      />
                    </span>
                    <span className={styles.muted}>
                      <span dir="ltr">{item.quantity}</span> {item.uom ? "×" : ""}
                    </span>
                    <span className={styles.tags}>
                      {item.isSubstitute ? (
                        <Tag variant="differs">{t("substituteLabel")}</Tag>
                      ) : null}
                      {item.isEstimated ? (
                        <Tag variant="estimated">{t("estimatedShort")}</Tag>
                      ) : null}
                      {item.promo ? (
                        <Tag variant="matched">
                          <DataText>{item.promo}</DataText>
                        </Tag>
                      ) : null}
                    </span>
                    <span className={styles.updated}>
                      <IconClock size={12} />{" "}
                      {t("updated", { time: formatTime(item.priceUpdatedAt, locale) })}
                    </span>
                  </span>
                  <Price amount={item.lineTotal} size="md" className={styles.itemPrice} />
                </button>
                <ReportGapButton
                  label={shared("reportShort")}
                  context={{
                    storeId: session.storeId,
                    storeName: session.storeName,
                    canonicalId: item.canonicalId,
                    itemId: item.itemId,
                    itemName: item.name,
                    shownPrice: item.lineTotal,
                    priceUpdatedAt: item.priceUpdatedAt,
                  }}
                />
              </li>
            ))}
          </ul>
        </section>
      ))}

      <p className={styles.muted}>
        {t("footer", { time: formatTime(session.pricesUpdatedAt, locale) })}
      </p>

      <div className={styles.finishBar}>
        <Button block size="md" onClick={() => setFinishOpen(true)} data-testid="finish">
          {t("finish")}
        </Button>
      </div>

      {undo ? (
        <div className={styles.snackbar} role="status" data-testid="undo-bar">
          <span>{t("marked", { name: undo.name })}</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setChecked(undo.itemId, false);
              setUndo(null);
            }}
          >
            {t("undo")}
          </Button>
        </div>
      ) : null}

      <BottomSheet
        open={finishOpen}
        onClose={() => setFinishOpen(false)}
        eyebrow={storeLabel(session.storeName, locale)}
        title={t("sheetTitle")}
        footer={
          <>
            <Button variant="outline" onClick={() => setFinishOpen(false)}>
              {t("backToShop")}
            </Button>
            <Button onClick={finish} data-testid="finish-confirm">
              {t("finishConfirm")}
            </Button>
          </>
        }
      >
        <dl className={styles.summary} data-testid="summary">
          <div>
            <dt>{t("collectedDt")}</dt>
            <dd>
              {formatRich(t("ofTotal"), {
                checked: <span dir="ltr">{progress.checked}</span>,
                total: <span dir="ltr">{progress.total}</span>,
              })}
            </dd>
          </div>
          <div>
            <dt>{t("itemsTotal")}</dt>
            <dd>
              <Price amount={progress.checkedTotal} size="lg" />
            </dd>
          </div>
          <div>
            <dt>{t("netSaved")}</dt>
            <dd>
              {saving !== null && progress.checked > 0 ? (
                <Price amount={saving} size="lg" tone={saving > 0 ? "good" : "default"} />
              ) : (
                <span className={styles.muted}>
                  {progress.checked === 0 ? t("noneCollected") : t("noBaseline")}
                </span>
              )}
            </dd>
          </div>
        </dl>
        {unchecked.length > 0 ? (
          <div>
            <p className={styles.legend}>{t("notCollected", { n: unchecked.length })}</p>
            <ul className={styles.uncheckedList}>
              {unchecked.map((i) => (
                <li key={i.itemId}>
                  <ItemName
                    item={{ display_name_he: i.name, canonical_name_ar: i.nameAr }}
                    show="product"
                  />
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {spend.total > 0 ? (
          <Switch
            checked={recordInBudget}
            onChange={setRecordInBudget}
            label={t("budgetLabel")}
            description={formatRich(t("budgetDesc"), {
              total: <Price amount={spend.total} />,
              scope: t(spend.ofPlan ? "scopePlan" : "scopeChecked", { n: spend.count }),
            })}
          />
        ) : null}
        <p className={styles.muted}>{t("sheetNote")}</p>
      </BottomSheet>
    </div>
  );
}

export function StoreMode() {
  const t = useT(storeMessages);
  return (
    <Suspense
      fallback={
        <div className={styles.page} aria-busy="true">
          <h1 className={styles.title}>{t("title")}</h1>
          <Skeleton height={64} radius={16} />
        </div>
      }
    >
      <DocumentTitle text={t("title")} />
      <StoreModeInner />
    </Suspense>
  );
}
