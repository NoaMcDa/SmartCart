"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type PointerEvent } from "react";
import type { PricedItem } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Price } from "@/components/ui/Price";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tag } from "@/components/ui/Tag";
import { IconCheck, IconClock, IconInfo } from "@/components/ui/icons";
import { reportSplitViewed } from "@/features/consent/betaEvents";
import { ReportGapButton } from "@/features/feedback/GapReportSheet";
import { buildSession, startSession } from "@/features/store/session";
import { formatDistance, formatTime } from "@/lib/format";
import { useComparison, type LastResult } from "./lastResult";
import {
  assignmentOf,
  buildSplitModel,
  computeSplit,
  moveBlockedReason,
  type Assignment,
  type SplitModel,
} from "./savings";
import styles from "./Split.module.css";
import { Waterfall } from "./Waterfall";

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>פיצול סל</h1>
      <Card data-testid="split-empty">
        <h2 className={styles.sectionTitle}>{title}</h2>
        <p className={styles.muted}>{body}</p>
        <div>
          <Button href="/compare" size="sm">
            חזרה להשוואה
          </Button>
        </div>
      </Card>
    </div>
  );
}

/**
 * Cart split view (issue #41). Reads the last comparison from `sc-last-result` (see lastResult.ts);
 * with nothing stored, or without a recommended split, it shows an empty state. All figures are
 * recomputed on the client from the cached line totals (savings.ts), so a move updates the
 * subtotals, the net saving and the waterfall at once, with no request.
 */
export function SplitView() {
  const { status, result } = useComparison();
  const model = useMemo(() => (result ? buildSplitModel(result) : null), [result]);
  if (status === "loading") {
    return (
      <div className={styles.page} aria-busy="true">
        <h1 className={styles.title}>פיצול סל</h1>
        <Skeleton height={96} radius={16} />
        <Skeleton height={160} radius={16} />
      </div>
    );
  }
  if (status === "error") {
    return (
      <EmptyState
        title="לא הצלחנו לחשב את הפיצול"
        body="בדקי את החיבור ונסי שוב מתוצאות ההשוואה."
      />
    );
  }
  if (!result) {
    return (
      <EmptyState
        title="אין עדיין השוואה לפצל"
        body="כשתשווי רשימה נציג כאן את הפיצול בין שתי חנויות, ותוכלי להזיז פריטים ביניהן ולראות איך החיסכון משתנה."
      />
    );
  }
  if (!model) {
    return (
      <EmptyState
        title="אין פיצול משתלם לרשימה הזו"
        body="אחרי נסיעה ואחרי השווי של עצירה נוספת, קנייה בחנות אחת משתלמת יותר. אפשר לשנות את שווי העצירה בפרופיל."
      />
    );
  }
  return <SplitBoard key={result.savedAt} result={result} model={model} />;
}

type DragState = {
  canonicalId: number;
  from: number;
  x: number;
  y: number;
  over: number | null;
  name: string;
};

function overStore(x: number, y: number): number | null {
  const el = document.elementFromPoint(x, y);
  const target = el?.closest<HTMLElement>("[data-drop-store]");
  return target?.dataset.dropStore ? Number(target.dataset.dropStore) : null;
}

function SplitBoard({ result, model }: { result: LastResult; model: SplitModel }) {
  const router = useRouter();
  const initial = useMemo(() => assignmentOf(model.plan), [model]);
  const [assignment, setAssignment] = useState<Assignment>(initial);
  const [tab, setTab] = useState(0);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [announcement, setAnnouncement] = useState("");

  // Beta event (feature use): a split plan is on screen. No-op unless the person consented.
  useEffect(() => {
    reportSplitViewed();
  }, []);

  const view = useMemo(() => computeSplit(model, assignment), [model, assignment]);
  const changed = useMemo(
    () => [...initial].some(([canonical, store]) => assignment.get(canonical) !== store),
    [initial, assignment],
  );
  const [first, second] = model.columnStores;
  const updatedAt = model.columnStores
    .map((s) => s.prices_updated_at)
    .sort()
    .at(-1);

  function move(canonicalId: number, toStoreId: number) {
    const reason = moveBlockedReason(model, canonicalId, toStoreId);
    const name = model.pool.priced
      .get(canonicalId)
      ?.get(assignment.get(canonicalId) ?? -1)?.display_name_he;
    if (reason) {
      setAnnouncement(`לא ניתן להעביר${name ? ` את ${name}` : ""}: ${reason}`);
      return;
    }
    const next = new Map(assignment);
    next.set(canonicalId, toStoreId);
    const target = model.pool.stores.get(toStoreId);
    const after = computeSplit(model, next);
    setAssignment(next);
    setAnnouncement(
      `${name ?? "הפריט"} הועבר ל${target?.chain_name ?? "החנות השנייה"}.` +
        (after.waterfall ? ` חיסכון נטו ₪${after.waterfall.net.toFixed(2)}.` : ""),
    );
  }

  function startDrag(e: PointerEvent<HTMLElement>, item: PricedItem, from: number) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({
      canonicalId: item.canonical_id,
      from,
      x: e.clientX,
      y: e.clientY,
      over: null,
      name: item.display_name_he,
    });
  }

  function moveDrag(e: PointerEvent<HTMLElement>) {
    setDrag((d) =>
      d ? { ...d, x: e.clientX, y: e.clientY, over: overStore(e.clientX, e.clientY) } : d,
    );
  }

  function endDrag(e: PointerEvent<HTMLElement>) {
    const current = drag;
    setDrag(null);
    if (!current) return;
    const target = overStore(e.clientX, e.clientY);
    if (target !== null && target !== current.from) move(current.canonicalId, target);
  }

  function startShopping(index: number) {
    const col = view.columns[index];
    if (!col || col.items.length === 0) return;
    const overhead = view.waterfall
      ? (view.waterfall.travel + view.waterfall.extraStop) / Math.max(1, view.visited)
      : null;
    const session = buildSession(col.store, result, {
      canonicalIds: col.items.map((i) => i.canonical_id),
      overhead,
    });
    startSession(session);
    router.push(`/store-mode?store=${col.store.store_id}`);
  }

  const w = view.waterfall;
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>פיצול סל</h1>
        <p className={styles.muted}>
          {result.listName ? `${result.listName} · ` : ""}
          {first?.chain_name} ו{second?.chain_name}
        </p>
      </header>

      <Card
        variant="recommended"
        className={styles.hero}
        aria-live="polite"
        data-testid="split-summary"
      >
        {w ? (
          <>
            <div className={styles.heroNet} data-good={w.net > 0}>
              {w.net > 0 ? <IconCheck size={18} /> : <IconInfo size={18} />}
              <span>חיסכון נטו מול {model.homeName ?? "החנות שלי"}</span>
              <Price
                amount={w.net}
                size="hero"
                tone={w.net > 0 ? "good" : "default"}
                data-testid="net-saving"
              />
            </div>
            {w.net <= 0 ? (
              <p className={styles.warn} role="status">
                אחרי הנסיעה והעצירה הנוספת, החלוקה הזו כבר לא חוסכת. אפשר להחזיר פריטים או לאפס.
              </p>
            ) : null}
          </>
        ) : (
          <p className={styles.warn} role="status" data-testid="baseline-missing">
            <IconInfo size={16} /> בלי חנות בסיס אי אפשר להציג חיסכון נטו. בחרי את הסופר שלך{" "}
            <Link href="/profile">בפרופיל</Link>.
          </p>
        )}
        <dl className={styles.facts}>
          <div>
            <dt>סה״כ לקנייה</dt>
            <dd>
              <Price amount={view.total} data-testid="split-total" />
            </dd>
          </div>
          <div>
            <dt>זמן נוסף</dt>
            <dd>
              <span dir="ltr">+{view.extraMinutes}</span> דק&apos;
            </dd>
          </div>
          {updatedAt ? (
            <div>
              <dt>מחירים</dt>
              <dd className={styles.updated}>
                <IconClock size={13} /> עודכנו {formatTime(updatedAt)}
              </dd>
            </div>
          ) : null}
        </dl>
      </Card>

      {w ? <Waterfall data={w} homeName={model.homeName ?? "החנות שלי"} /> : null}

      <div className={styles.toolbar}>
        <p className={styles.hintText}>
          גררי פריט אל החנות השנייה, או השתמשי בכפתור &quot;העברה&quot; בכל שורה.
        </p>
        <Button
          variant="outline"
          size="sm"
          disabled={!changed}
          onClick={() => {
            setAssignment(new Map(initial));
            setAnnouncement("הפיצול המומלץ שוחזר.");
          }}
        >
          איפוס לפיצול המומלץ
        </Button>
      </div>

      <div className={styles.tabs} role="tablist" aria-label="חנויות בפיצול">
        {view.columns.map((col, i) => (
          <button
            key={col.store.store_id}
            type="button"
            role="tab"
            id={`tab-${col.store.store_id}`}
            aria-selected={tab === i}
            aria-controls={`panel-${col.store.store_id}`}
            className={styles.tab}
            data-drop-store={col.store.store_id}
            data-over={drag?.over === col.store.store_id}
            onClick={() => setTab(i)}
          >
            {col.store.chain_name} · <Price amount={col.subtotal} />
          </button>
        ))}
      </div>

      <div className={styles.columns}>
        {view.columns.map((col, i) => {
          const other = view.columns[1 - i]?.store;
          return (
            <section
              key={col.store.store_id}
              role="tabpanel"
              id={`panel-${col.store.store_id}`}
              aria-labelledby={`tab-${col.store.store_id}`}
              className={styles.column}
              data-active={tab === i}
              data-drop-store={col.store.store_id}
              data-over={drag?.over === col.store.store_id}
              data-testid={`split-column-${col.store.store_id}`}
            >
              <header className={styles.columnHead}>
                <div>
                  <h2 className={styles.columnTitle}>{col.store.store_name}</h2>
                  <p className={styles.muted}>
                    {formatDistance(col.store.distance_m)} ·{" "}
                    <span dir="ltr">{col.items.length}</span> פריטים
                  </p>
                </div>
                <div className={styles.subtotal}>
                  <span className={styles.muted}>סכום ביניים</span>
                  <Price
                    amount={col.subtotal}
                    size="lg"
                    data-testid={`subtotal-${col.store.store_id}`}
                  />
                </div>
              </header>
              <ul className={styles.items}>
                {col.items.length === 0 ? (
                  <li className={styles.emptyColumn}>
                    אין פריטים בחנות הזו. אפשר לקנות הכול בחנות אחת.
                  </li>
                ) : null}
                {col.items.map((item) => {
                  const reason = other
                    ? moveBlockedReason(model, item.canonical_id, other.store_id)
                    : null;
                  return (
                    <li
                      key={item.item_id}
                      className={styles.item}
                      data-testid="split-item"
                      data-canonical={item.canonical_id}
                      data-dragging={drag?.canonicalId === item.canonical_id}
                    >
                      <span
                        className={styles.handle}
                        aria-hidden="true"
                        onPointerDown={(e) => startDrag(e, item, col.store.store_id)}
                        onPointerMove={moveDrag}
                        onPointerUp={endDrag}
                        onPointerCancel={() => setDrag(null)}
                      >
                        ⋮⋮
                      </span>
                      <div className={styles.itemMain}>
                        <span className={styles.itemName}>{item.display_name_he}</span>
                        <span className={styles.muted}>
                          <span dir="ltr">{item.quantity}</span> × · <IconClock size={12} /> עודכן{" "}
                          {formatTime(item.price_valid_from)}
                        </span>
                        <span className={styles.tags}>
                          {item.is_substitute ? <Tag variant="differs">תחליף</Tag> : null}
                          {item.is_estimated ? <Tag variant="estimated">מחיר משוער</Tag> : null}
                          {item.promo_description ? (
                            <Tag variant="matched">{item.promo_description}</Tag>
                          ) : null}
                        </span>
                        {reason ? (
                          <span
                            id={`why-${item.item_id}`}
                            className={styles.reason}
                            data-testid="move-reason"
                          >
                            <IconInfo size={13} /> {reason}, לכן אי אפשר להעביר
                          </span>
                        ) : null}
                      </div>
                      <span className={styles.itemPrice}>
                        <Price amount={item.line_total} />
                      </span>
                      <div className={styles.itemActions}>
                        {other ? (
                          <Button
                            size="sm"
                            variant="outline"
                            aria-label={`העברת ${item.display_name_he} ל${other.chain_name}`}
                            aria-disabled={reason ? true : undefined}
                            aria-describedby={reason ? `why-${item.item_id}` : undefined}
                            className={reason ? styles.blocked : undefined}
                            onClick={() => move(item.canonical_id, other.store_id)}
                          >
                            העברה ל{other.chain_name}
                          </Button>
                        ) : null}
                        <ReportGapButton
                          label="דיווח"
                          context={{
                            storeId: col.store.store_id,
                            storeName: col.store.store_name,
                            canonicalId: item.canonical_id,
                            itemId: item.item_id,
                            itemName: item.display_name_he,
                            shownPrice: item.line_total,
                            priceUpdatedAt: item.price_valid_from,
                          }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <Button
                variant="secondary"
                block
                disabled={col.items.length === 0}
                onClick={() => startShopping(i)}
              >
                התחילי קנייה ב{col.store.chain_name}
              </Button>
            </section>
          );
        })}
      </div>

      <p className={styles.muted}>
        המחיר הקובע הוא בקופה. הסכומים מחושבים מהמחירים שנשמרו בהשוואה האחרונה.
      </p>

      <div className="sr-only" role="status" aria-live="polite" data-testid="split-announcer">
        {announcement}
      </div>

      {drag ? (
        <div
          className={styles.ghost}
          aria-hidden="true"
          style={{
            insetBlockStart: drag.y + 8,
            // The page is RTL, so inline-start is the right edge: keep the label just left of the pointer.
            insetInlineStart: document.documentElement.clientWidth - drag.x + 8,
          }}
        >
          {drag.name}
        </div>
      ) : null}
    </div>
  );
}
