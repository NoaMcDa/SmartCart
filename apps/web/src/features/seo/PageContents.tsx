"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Price, Tag } from "@/components/ui";
import { useRich } from "@/i18n/format-2";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { seoMessages } from "@/i18n/messages/seo";
import { BasketDefinition, BasketMonthTable } from "./BasketTable";
import {
  Breadcrumbs,
  FlexLevelsExplained,
  Kind,
  ListBuilderCta,
  NoPricesNotice,
  PriceTable,
  TrustNote,
} from "./components";
import { METHODOLOGY_PATH } from "./config";
import { attrLabel, attrValue, monthLabel, perUnit } from "./format";
import type { Crumb } from "./jsonld";
import type { BasketIndexFile, BasketMonth, Category, Product } from "./types";
import styles from "./seo.module.css";

/*
 * Bodies of the product, category and basket-index pages. The pages (server components) keep the
 * metadata, JSON-LD and data loading; these client components render the text, so it can switch
 * to Arabic after hydration while the server HTML stays Hebrew for search engines. Names that come
 * from the catalog (products, categories, chains) are Hebrew data and stay as they are.
 */

export function ProductContent({
  product,
  crumbs,
  related,
  updatedAt,
}: {
  product: Product;
  crumbs: Crumb[];
  related: Product[];
  updatedAt: string;
}) {
  const t = useT(seoMessages);
  const { locale } = useLocale();
  const unit = perUnit(product.base_unit, locale);
  const typeNode = product.path[product.path.length - 1];
  return (
    <>
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{product.name_he}</h1>
        <p className={styles.lede}>
          {t("productLede", { unit, name: product.name_he })}
          {product.base_unit === "kg" ? ` ${t("productLedeKg")}` : ""}
        </p>
        {product.base_unit === "kg" ? (
          <Tag variant="estimated">{t("estimatedPriceWeighed")}</Tag>
        ) : null}
      </header>

      <section className={styles.section} aria-labelledby="h-prices">
        <h2 id="h-prices" className={styles.h2}>
          {t("pricesByChain")}
        </h2>
        {product.prices && product.prices.length > 0 ? (
          <>
            <PriceTable prices={product.prices} unit={product.base_unit} />
            <p className={styles.muted}>{t("medianNote")}</p>
          </>
        ) : (
          <NoPricesNotice />
        )}
      </section>

      <section className={styles.section} aria-labelledby="h-match">
        <h2 id="h-match" className={styles.h2}>
          {t("sameProduct")}
        </h2>
        <p>{t("sameProductBody")}</p>
        <dl className={styles.attrs}>
          <dt>{t("productType")}</dt>
          <dd>{typeNode?.name_he ?? product.name_he}</dd>
          {Object.entries(product.critical_attrs).map(([key, value]) => (
            <div key={key} className={styles.attrRow}>
              <dt>{attrLabel(key, locale)}</dt>
              <dd>
                <bdi>{attrValue(key, value, locale)}</bdi>
              </dd>
            </div>
          ))}
        </dl>
        <FlexLevelsExplained />
      </section>

      {related.length > 0 ? (
        <section className={styles.section} aria-labelledby="h-related">
          <h2 id="h-related" className={styles.h2}>
            {t("relatedProducts")}
          </h2>
          <ul className={styles.linkGrid}>
            {related.map((p) => (
              <li key={p.slug}>
                <Link href={`/p/${p.slug}`} className={styles.linkRow}>
                  <span className={styles.linkName}>{p.name_he}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <ListBuilderCta variant="product" name={product.name_he} />
      <TrustNote
        label={product.price_valid_from ? "pricesAsOf" : "catalogAsOf"}
        updatedAt={updatedAt}
      />
    </>
  );
}

/** Lowest of the chains' median unit prices, or null when nothing is priced yet. */
function startingPrice(product: Product): number | null {
  if (!product.prices || product.prices.length === 0) return null;
  return Math.min(...product.prices.map((p) => p.median_unit_price));
}

export function CategoryContent({
  category,
  crumbs,
  subcategories,
  shown,
  hasPrices,
  updatedAt,
}: {
  category: Category;
  crumbs: Crumb[];
  subcategories: Category[];
  shown: Product[];
  hasPrices: boolean;
  updatedAt: string;
}) {
  const t = useT(seoMessages);
  const r = useRich(seoMessages);
  const { locale } = useLocale();
  return (
    <>
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{category.name_he}</h1>
        <p className={styles.lede}>
          {t("categoryLede", { name: category.name_he, count: category.canonical_count })}
        </p>
      </header>

      {subcategories.length > 0 ? (
        <section className={styles.section} aria-labelledby="h-sub">
          <h2 id="h-sub" className={styles.h2}>
            {t("subCategories")}
          </h2>
          <ul className={styles.linkGrid}>
            {subcategories.map((c) => (
              <li key={c.slug}>
                <Link href={`/c/${c.slug}`} className={styles.linkRow}>
                  <span className={styles.linkName}>{c.name_he}</span>
                  <span className={styles.linkMeta}>
                    {t("productsCount", { count: c.canonical_count })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className={styles.section} aria-labelledby="h-products">
        <h2 id="h-products" className={styles.h2}>
          {category.level === 1 ? t("popularProducts") : t("categoryProducts")}
        </h2>
        <ul className={styles.linkGrid}>
          {shown.map((p) => {
            const from = startingPrice(p);
            const inner = (
              <>
                <span className={styles.linkName}>{p.name_he}</span>
                <span className={styles.linkMeta}>
                  {from !== null
                    ? r(
                        "startingFrom",
                        { price: <Price amount={from} fractionDigits={2} /> },
                        { unit: perUnit(p.base_unit, locale) },
                      )
                    : t("noPricesYet")}
                </span>
              </>
            );
            return (
              <li key={p.slug}>
                {p.has_page ? (
                  <Link href={`/p/${p.slug}`} className={styles.linkRow}>
                    {inner}
                  </Link>
                ) : (
                  <div className={styles.linkRow}>{inner}</div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <ListBuilderCta variant="category" name={category.name_he} />
      <TrustNote label={hasPrices ? "pricesAsOf" : "catalogAsOf"} updatedAt={updatedAt} />
    </>
  );
}

export function BasketIndexContent({
  basket,
  latest,
  history,
  crumbs,
  updatedAt,
}: {
  basket: BasketIndexFile["basket"];
  latest: BasketMonth | undefined;
  history: BasketMonth[];
  crumbs: Crumb[];
  updatedAt: string;
}) {
  const t = useT(seoMessages);
  const { locale } = useLocale();
  const kind: ReactNode = <Kind kind="estimate" />;
  const r = useRich(seoMessages);
  return (
    <>
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{t("biTitle")}</h1>
        <p className={styles.lede}>{t("biLede", { count: basket.item_count })}</p>
      </header>

      {latest ? (
        <>
          <BasketMonthTable month={latest} />
          {history.length > 0 ? (
            <section className={styles.section} aria-labelledby="h-history">
              <h2 id="h-history" className={styles.h2}>
                {t("biPrevious")}
              </h2>
              {history.map((m) => (
                <details key={m.month} className={styles.details}>
                  <summary>{monthLabel(m.month, locale)}</summary>
                  <BasketMonthTable month={m} headingLevel={3} />
                </details>
              ))}
            </section>
          ) : null}
        </>
      ) : (
        <section className={styles.section} aria-labelledby="h-empty">
          <h2 id="h-empty" className={styles.h2}>
            {t("biEmptyTitle")}
          </h2>
          <NoPricesNotice />
          <p>{t("biEmptyBody")}</p>
        </section>
      )}

      <section className={styles.section} aria-labelledby="h-basket">
        <h2 id="h-basket" className={styles.h2}>
          {t("biBasket")}
        </h2>
        <details className={styles.details}>
          <summary>{t("biBasketSummary", { version: basket.version })}</summary>
          <BasketDefinition basket={basket} />
        </details>
        <p className={styles.muted}>{r("biBasketNote", { kind })}</p>
      </section>

      <section className={styles.section} aria-labelledby="h-method">
        <h2 id="h-method" className={styles.h2}>
          {t("biHow")}
        </h2>
        <ul>
          <li>{t("biHow1")}</li>
          <li>{t("biHow2")}</li>
          <li>{t("biHow3")}</li>
          <li>{t("biHow4")}</li>
          <li>{t("biHow5")}</li>
        </ul>
        <p>
          <Link href={METHODOLOGY_PATH}>{t("biFullMethod")}</Link>
        </p>
      </section>

      <ListBuilderCta variant="basket" />
      <TrustNote label="biUpdatedLabel" updatedAt={updatedAt} />
    </>
  );
}
