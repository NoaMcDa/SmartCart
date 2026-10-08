"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Button, FlexChip, IconChevronNext, IconInfo, Price, Tag } from "@/components/ui";
import type { FlexLevel } from "@/components/ui";
import { useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { seoMessages, type SeoMessageKey } from "@/i18n/messages/seo";
import {
  ACCESSIBILITY_PATH,
  BASKET_INDEX_PATH,
  LIST_BUILDER_PATH,
  METHODOLOGY_PATH,
} from "./config";
import { formatDate, isoDate, perUnit } from "./format";
import { serializeJsonLd, type Crumb, type JsonLd } from "./jsonld";
import type { BaseUnit, ChainPrice } from "./types";
import styles from "./seo.module.css";

/*
 * Client components so the chrome can switch to Arabic (#73), but the server render is always
 * Hebrew (the locale context's server snapshot), which is what search engines index.
 */

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
  const t = useT(seoMessages);
  return (
    <nav aria-label={t("breadcrumbsLabel")} className={styles.crumbs}>
      <ol className={styles.crumbList}>
        {crumbs.map((crumb, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={crumb.path} className={styles.crumbItem}>
              {last ? (
                <span aria-current="page">{crumb.path === "/" ? t("home") : crumb.name}</span>
              ) : (
                <>
                  <Link href={crumb.path}>{crumb.path === "/" ? t("home") : crumb.name}</Link>
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
  const t = useT(seoMessages);
  return <Link href={METHODOLOGY_PATH}>{children ?? t("footerMethodology")}</Link>;
}

/** Update date, the checkout line and the methodology link: the trust block of every SEO page. */
export function TrustNote({
  label,
  updatedAt,
}: {
  /** Message key of the lead-in: "pricesAsOf", "catalogAsOf" or "biUpdatedLabel". */
  label: "pricesAsOf" | "catalogAsOf" | "biUpdatedLabel";
  updatedAt: string;
}) {
  const t = useT(seoMessages);
  const r = useRich(seoMessages);
  const { locale } = useLocale();
  return (
    <aside className={styles.trust} aria-label={t("trustLabel")}>
      <p>
        {r(
          "trustDate",
          {
            time: <time dateTime={isoDate(updatedAt)}>{formatDate(updatedAt, locale)}</time>,
          },
          { label: t(label) },
        )}
      </p>
      <p>
        {r("trustBody", { b: (c) => <strong>{c}</strong> }, { checkout: t("checkoutGoverns") })}
      </p>
      <div className={styles.trustLinks}>
        <MethodologyLink />
        <Link href={BASKET_INDEX_PATH}>{t("footerBasketIndex")}</Link>
      </div>
    </aside>
  );
}

const CTA_KEY = {
  methodology: "ctaMethodology",
  basket: "ctaBasket",
  product: "ctaProduct",
  category: "ctaCategory",
} as const satisfies Record<string, SeoMessageKey>;

/** Call to action on every SEO page; `name` is the product or category it is about. */
export function ListBuilderCta({
  variant,
  name,
}: {
  variant: keyof typeof CTA_KEY;
  name?: string;
}) {
  const t = useT(seoMessages);
  return (
    <section className={styles.cta} aria-label={t("ctaLabel")}>
      <p>{t(CTA_KEY[variant], { name: name ?? "" })}</p>
      <Button href={LIST_BUILDER_PATH}>{t("ctaButton")}</Button>
    </section>
  );
}

/** Per-chain unit prices of one product. */
export function PriceTable({ prices, unit }: { prices: ChainPrice[]; unit: BaseUnit }) {
  const t = useT(seoMessages);
  const { locale } = useLocale();
  const unitText = perUnit(unit, locale);
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption>{t("priceCaption", { unit: unitText })}</caption>
        <thead>
          <tr>
            <th scope="col">{t("colChain")}</th>
            <th scope="col">{t("colMedian")}</th>
            <th scope="col">{t("colCheapest")}</th>
            <th scope="col">{t("colStores")}</th>
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
                    <Tag variant="estimated">{t("estimatedWeighed")}</Tag>
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
  const t = useT(seoMessages);
  const rows: { level: FlexLevel; text: string }[] = [
    { level: "exact", text: t("flexExact") },
    { level: "any_brand", text: t("flexAnyBrand") },
    { level: "close", text: t("flexClose") },
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
  const t = useT(seoMessages);
  return (
    <div className={styles.notice} role="note">
      <IconInfo size={18} />
      <p>{t("noPrices")}</p>
    </div>
  );
}

export function SeoFooterLinks() {
  const t = useT(seoMessages);
  return (
    <ul className={styles.footerLinks}>
      <li>
        <Link href={METHODOLOGY_PATH}>{t("footerMethodology")}</Link>
      </li>
      <li>
        <Link href={BASKET_INDEX_PATH}>{t("footerBasketIndex")}</Link>
      </li>
      <li>
        <Link href={ACCESSIBILITY_PATH}>{t("footerAccessibility")}</Link>
      </li>
    </ul>
  );
}

/**
 * Marks what kind of number it sits next to (issue #21: any quoted number is marked as measured
 * or as an estimate): measured, estimate, target, or fixed by law.
 */
export function Kind({ kind }: { kind: "measured" | "estimate" | "target" | "law" }) {
  const t = useT(seoMessages);
  const text = {
    measured: t("kindMeasured"),
    estimate: t("kindEstimate"),
    target: t("kindTarget"),
    law: t("kindLaw"),
  }[kind];
  return <span className={styles.kind}>{text}</span>;
}
