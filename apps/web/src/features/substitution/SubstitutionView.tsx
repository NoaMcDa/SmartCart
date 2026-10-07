"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { AttributeTag } from "@/api/client";
import {
  Button,
  Card,
  IconCheck,
  IconClose,
  Price,
  Skeleton,
  SkeletonText,
  Tag,
  TrustedPrice,
  UpdatedAt,
} from "@/components/ui";
import {
  buildOptimizeInput,
  findSubstitution,
  substitutionSaving,
  useOptimize,
  type PlanKind,
  type SubstitutionContext,
} from "@/state/comparison";
import { MethodologyLink } from "@/features/seo/components";
import { basketItems, useList } from "@/state/list";
import { useShopper } from "@/state/shopper";
import { acceptSubstitute, keepOriginal, rejectSubstitute } from "./actions";
import styles from "./Substitution.module.css";

export function tagText(tag: AttributeTag): string {
  if (tag.status === "unverified") {
    return `${tag.key}${tag.value ? ` ${tag.value}` : ""} · לא מאומת`;
  }
  if (tag.status === "differs") return tag.value ?? tag.key;
  return tag.value ? `${tag.key}, ${tag.value}` : tag.key;
}

const TAG_ORDER: Record<AttributeTag["status"], number> = { matched: 0, unverified: 1, differs: 2 };

function percent(confidence: number | null | undefined): string | null {
  if (confidence === null || confidence === undefined) return null;
  return `${Math.round(confidence * 100)}%`;
}

export function SubstitutionCard({
  ctx,
  fallbackOriginalName,
  onContinue,
  onKeep,
  onReject,
  busy,
}: {
  ctx: SubstitutionContext;
  fallbackOriginalName: string | null;
  onContinue: () => void;
  onKeep: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  const { item, store, original, index, count } = ctx;
  const originalName = original?.item.display_name_he ?? fallbackOriginalName ?? "המוצר המקורי";
  const saving = substitutionSaving(ctx);
  const tags = [...(item.tags ?? [])].sort((a, b) => TAG_ORDER[a.status] - TAG_ORDER[b.status]);
  const conf = percent(item.confidence);
  const isLast = index + 1 >= count;

  return (
    <Card as="article" className={styles.card} aria-labelledby="sub-title" data-testid="sub-card">
      <div className={styles.eyebrow}>
        החלפה <span dir="ltr">{index + 1}</span> מתוך <span dir="ltr">{count}</span> ·{" "}
        {store.chain_name}
      </div>
      <h2 id="sub-title" className={styles.title}>
        החלפנו את <strong>{originalName}</strong> ב-<strong>{item.display_name_he}</strong>
      </h2>

      <div className={styles.compare}>
        <div className={styles.side} data-trust-scope="original" data-testid="sub-original">
          <div className={styles.sideLabel}>ברשימה שלך</div>
          <div className={styles.sideName}>{originalName}</div>
          {original ? (
            <>
              <TrustedPrice
                amount={original.item.shelf_price}
                updatedAt={original.item.price_valid_from}
                size="lg"
                fractionDigits={2}
              />
              <div className={styles.unit}>
                <Price amount={original.item.effective_unit_price} fractionDigits={2} /> ל-
                {original.item.uom}
              </div>
              <div className={styles.where}>בסופר שלך, {original.store.store_name}</div>
            </>
          ) : (
            <div className={styles.unit}>אין מחיר להשוואה בסופר שלך</div>
          )}
        </div>
        <div
          className={[styles.side, styles.substitute].join(" ")}
          data-trust-scope="substitute"
          data-testid="sub-substitute"
        >
          <div className={styles.sideLabelSub}>
            <Tag variant="substitute">התחליף</Tag>
          </div>
          <div className={styles.sideName}>{item.display_name_he}</div>
          <TrustedPrice
            amount={item.shelf_price}
            updatedAt={item.price_valid_from}
            size="lg"
            fractionDigits={2}
          />
          <div className={styles.unit}>
            <Price amount={item.effective_unit_price} fractionDigits={2} /> ל-{item.uom}
          </div>
          <div className={styles.where}>{store.store_name}</div>
        </div>
      </div>

      {saving && saving.total > 0 ? (
        <div className={styles.saving} data-testid="sub-saving">
          <span className={styles.savingText}>
            <IconCheck size={15} />
            חיסכון <Price amount={saving.perUnit} fractionDigits={2} /> ×{" "}
            <span dir="ltr">{saving.quantity}</span> {saving.quantity === 1 ? "יחידה" : "יחידות"}
          </span>
          <Price amount={saving.total} fractionDigits={2} size="lg" tone="good" />
        </div>
      ) : saving ? (
        <div className={styles.noSaving}>אין חיסכון במחיר המדף בהחלפה הזו</div>
      ) : null}

      <div className={styles.why}>
        <h3 className={styles.whyTitle}>למה זה תחליף מתאים</h3>
        <ul className={styles.tags} aria-label="השוואת תכונות">
          {tags.map((t) => (
            <li key={`${t.status}-${t.key}`}>
              <Tag variant={t.status}>{tagText(t)}</Tag>
            </li>
          ))}
        </ul>
        <p className={styles.source} data-testid="sub-source">
          לפי שם המוצר בקובץ השקיפות
          {conf ? (
            <>
              {" "}
              · ביטחון <span dir="ltr">{conf}</span>
            </>
          ) : null}{" "}
          · <UpdatedAt iso={item.price_valid_from} prefix="מחיר עודכן" />
        </p>
        <p className={styles.methodology} data-testid="sub-methodology">
          <MethodologyLink>איך אנחנו מחליטים מה תחליף מתאים</MethodologyLink>
        </p>
      </div>

      <div className={styles.actions}>
        <Button block onClick={onContinue} disabled={busy}>
          {isLast ? "בסדר, חזרה לתוצאות" : "בסדר, להחלפה הבאה"}
        </Button>
        <div className={styles.secondary}>
          <Button variant="outline" size="sm" onClick={onKeep} disabled={busy}>
            השאירי את המקורי
          </Button>
          <Button
            variant="outline"
            size="sm"
            tone="bad"
            onClick={onReject}
            disabled={busy}
            iconStart={<IconClose size={15} />}
          >
            לא תחליף טוב
          </Button>
        </div>
      </div>
    </Card>
  );
}

/**
 * Substitution card (issue #48) for one substituted line, found in the cached /optimize result
 * by item id (`plan` picks the plan the user came from).
 */
export function SubstitutionView({ itemId, plan }: { itemId: number; plan?: PlanKind }) {
  const router = useRouter();
  const { state, hydrated } = useList();
  const shopper = useShopper();
  const [busy, setBusy] = useState(false);
  const basket = useMemo(() => basketItems(state), [state]);
  const input = useMemo(
    () => (shopper ? buildOptimizeInput(basket, shopper) : null),
    [basket, shopper],
  );
  const result = useOptimize(input);
  const data = "data" in result ? result.data : undefined;
  const ctx = data && Number.isFinite(itemId) ? findSubstitution(data, itemId, plan) : null;

  if (!hydrated || !shopper || (!data && result.status !== "error" && basket.length > 0)) {
    return (
      <>
        <Card aria-busy="true" aria-label="טוען את פרטי ההחלפה">
          <Skeleton width="50%" height={14} />
          <Skeleton width="90%" height={22} />
          <SkeletonText lines={4} />
        </Card>
      </>
    );
  }

  if (result.status === "error" && !data) {
    return (
      <>
        <Card role="alert">
          <p>לא הצלחנו לטעון את ההחלפה.</p>
          <Button onClick={result.reload}>נסי שוב</Button>
        </Card>
      </>
    );
  }

  if (!ctx) {
    return (
      <>
        <Card data-testid="sub-not-found">
          <h2 className={styles.title}>לא מצאנו את ההחלפה הזו</h2>
          <p className={styles.unit}>
            ייתכן שהרשימה השתנתה מאז, או שהפריט כבר מוגדר כמוצר מדויק. אפשר לחזור לתוצאות ולראות את
            ההחלפות העדכניות.
          </p>
          <Button href="/compare">חזרה לתוצאות</Button>
        </Card>
      </>
    );
  }

  const fallbackName =
    state.items.find((i) => i.canonical?.canonical_id === ctx.item.canonical_id)?.canonical
      ?.display_name_he ?? null;
  const originalName = ctx.original?.item.display_name_he ?? fallbackName;
  const next = ctx.siblings[ctx.index + 1];

  return (
    <>
      <SubstitutionCard
        ctx={ctx}
        fallbackOriginalName={fallbackName}
        busy={busy}
        onContinue={() => {
          acceptSubstitute(ctx.item);
          router.push(
            next ? `/compare/substitution/${next.item.item_id}?plan=${ctx.plan.kind}` : "/compare",
          );
        }}
        onKeep={() => {
          keepOriginal(ctx.item, originalName);
          router.push("/compare");
        }}
        onReject={async () => {
          setBusy(true);
          await rejectSubstitute(ctx.item, originalName);
          router.push("/compare");
        }}
      />
    </>
  );
}
