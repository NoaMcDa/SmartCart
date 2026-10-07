import Link from "next/link";
import type { ReactNode } from "react";
import { Button, FlexChip, IconChevronNext, IconInfo, Price, Tag } from "@/components/ui";
import type { FlexLevel } from "@/components/ui";
import {
  ACCESSIBILITY_PATH,
  BASKET_INDEX_PATH,
  CHECKOUT_GOVERNS,
  LIST_BUILDER_PATH,
  METHODOLOGY_PATH,
} from "./config";
import { formatDateHe, isoDate, PER_UNIT } from "./format";
import { serializeJsonLd, type Crumb, type JsonLd } from "./jsonld";
import type { BaseUnit, ChainPrice } from "./types";
import styles from "./seo.module.css";

/** `<script type="application/ld+json">`; the text is escaped so it cannot close the tag. */
export function JsonLd({ data }: { data: JsonLd | JsonLd[] }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }}
    />
  );
}

/** Visible breadcrumbs; the last crumb is the current page. Mirrors the BreadcrumbList data. */
export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="נתיב הניווט" className={styles.crumbs}>
      <ol className={styles.crumbList}>
        {crumbs.map((crumb, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={crumb.path} className={styles.crumbItem}>
              {last ? (
                <span aria-current="page">{crumb.name}</span>
              ) : (
                <>
                  <Link href={crumb.path}>{crumb.name}</Link>
                  <span className={styles.crumbSep} aria-hidden="true">
                    <IconChevronNext size={14} />
                  </span>
                </>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * Link to the methodology page. Exported for the results footer and the substitution card, which
 * W4b builds (issue #21: the page is linked from there too).
 */
export function MethodologyLink({ children }: { children?: ReactNode }) {
  return <Link href={METHODOLOGY_PATH}>{children ?? "איך אנחנו משווים מחירים"}</Link>;
}

/** Update date, the checkout line and the methodology link: the trust block of every SEO page. */
export function TrustNote({ label, updatedAt }: { label: string; updatedAt: string }) {
  return (
    <aside className={styles.trust} aria-label="אמינות ועדכון">
      <p>
        {label} <time dateTime={isoDate(updatedAt)}>{formatDateHe(updatedAt)}</time>.
      </p>
      <p>
        <strong>{CHECKOUT_GOVERNS}</strong> המחירים מגיעים מקבצי השקיפות שהרשתות מחויבות לפרסם בחוק.
        ייתכנו הפרשים בין המחיר כאן למחיר בסניף.
      </p>
      <div className={styles.trustLinks}>
        <MethodologyLink />
        <Link href={BASKET_INDEX_PATH}>מדד הסל החודשי</Link>
      </div>
    </aside>
  );
}

export function ListBuilderCta({ text }: { text: string }) {
  return (
    <section className={styles.cta} aria-label="בניית רשימה">
      <p>{text}</p>
      <Button href={LIST_BUILDER_PATH}>בני רשימת קניות</Button>
    </section>
  );
}

/** Per-chain unit prices of one product. */
export function PriceTable({ prices, unit }: { prices: ChainPrice[]; unit: BaseUnit }) {
  const unitText = PER_UNIT[unit];
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption>מחיר {unitText} בכל רשת</caption>
        <thead>
          <tr>
            <th scope="col">רשת</th>
            <th scope="col">מחיר חציוני</th>
            <th scope="col">הזול ביותר</th>
            <th scope="col">סניפים</th>
          </tr>
        </thead>
        <tbody>
          {prices.map((p) => (
            <tr key={p.chain_id}>
              <th scope="row">
                {p.chain_name}
                {p.is_estimated ? (
                  <>
                    {" "}
                    <Tag variant="estimated">הערכה, מוצר במשקל</Tag>
                  </>
                ) : null}
              </th>
              <td className={styles.num}>
                <Price amount={p.median_unit_price} fractionDigits={2} />
              </td>
              <td className={styles.num}>
                <Price amount={p.min_unit_price} fractionDigits={2} />
              </td>
              <td className={styles.num}>{p.stores}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One line per flexibility level: the chip (icon plus text) and what it allows. */
export function FlexLevelsExplained() {
  const rows: { level: FlexLevel; text: string }[] = [
    { level: "exact", text: "רק המוצר עצמו, לפי ברקוד." },
    { level: "any_brand", text: "אותו מוצר מכל מותג: המאפיינים החשובים נשארים זהים." },
    { level: "close", text: "תחליף קרוב: מאפיינים משניים, כמו גודל אריזה, יכולים להשתנות." },
  ];
  return (
    <ul className={styles.levels}>
      {rows.map(({ level, text }) => (
        <li key={level}>
          <FlexChip level={level} />
          <span>{text}</span>
        </li>
      ))}
    </ul>
  );
}

export function NoPricesNotice() {
  return (
    <div className={styles.notice} role="note">
      <IconInfo size={18} />
      <p>
        עדיין לא נטענו מחירים למוצר הזה. כשקבצי השקיפות של הרשתות ייטענו, המחירים יופיעו כאן עם
        תאריך העדכון.
      </p>
    </div>
  );
}

export function SeoFooterLinks() {
  return (
    <ul className={styles.footerLinks}>
      <li>
        <Link href={METHODOLOGY_PATH}>איך אנחנו משווים מחירים</Link>
      </li>
      <li>
        <Link href={BASKET_INDEX_PATH}>מדד הסל החודשי</Link>
      </li>
      <li>
        <Link href={ACCESSIBILITY_PATH}>הצהרת נגישות</Link>
      </li>
    </ul>
  );
}

/**
 * Marks what kind of number it sits next to (issue #21: any quoted number is marked as measured
 * or as an estimate): measured, estimate, target, or fixed by law.
 */
export function Kind({ kind }: { kind: "measured" | "estimate" | "target" | "law" }) {
  const text = { measured: "נמדד", estimate: "הערכה", target: "יעד", law: "לפי החוק" }[kind];
  return <span className={styles.kind}>{text}</span>;
}
