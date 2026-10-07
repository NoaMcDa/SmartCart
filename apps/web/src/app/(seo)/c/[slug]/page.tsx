import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Price } from "@/components/ui";
import { Breadcrumbs, JsonLd, ListBuilderCta, TrustNote } from "@/features/seo/components";
import { absoluteUrl, CHECKOUT_GOVERNS } from "@/features/seo/config";
import {
  categoryPages,
  childCategories,
  getCategory,
  getProducts,
  productsIn,
} from "@/features/seo/data";
import { PER_UNIT } from "@/features/seo/format";
import { breadcrumbList, categoryJsonLd } from "@/features/seo/jsonld";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import styles from "@/features/seo/seo.module.css";
import type { Category, Product } from "@/features/seo/types";

type Params = { slug: string };

/** Only the categories the generator exported; anything else is a 404. */
export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  return categoryPages().map((c) => ({ slug: c.slug }));
}

function crumbsFor(category: Category) {
  return [
    { name: "בית", path: "/" },
    ...category.path.map((p) => ({ name: p.name_he, path: `/c/${p.slug}` })),
    { name: category.name_he, path: `/c/${category.slug}` },
  ];
}

function describe(category: Category): string {
  return `השוואת מחירים ל${category.name_he} בין רשתות הסופר בישראל: ${category.canonical_count} מוצרים מייצגים, מחיר ליחידת מידה ותאריך עדכון. ${CHECKOUT_GOVERNS}`;
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const category = getCategory(slug);
  if (!category) return {};
  const title = `מחירי ${category.name_he} בסופרים`;
  const description = describe(category);
  return {
    title,
    description,
    alternates: { canonical: absoluteUrl(`/c/${slug}`) },
    openGraph: { title, description, type: "website", locale: "he_IL" },
  };
}

/** Lowest of the chains' median unit prices, or null when nothing is priced yet. */
function startingPrice(product: Product): number | null {
  if (!product.prices || product.prices.length === 0) return null;
  return Math.min(...product.prices.map((p) => p.median_unit_price));
}

function latestPriceDate(products: Product[]): string | null {
  const dates = products.map((p) => p.price_valid_from).filter((d): d is string => d !== null);
  return dates.length > 0 ? dates.reduce((a, b) => (a > b ? a : b)) : null;
}

export default async function Page({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const category = getCategory(slug);
  if (!category) notFound();
  const products = productsIn(category);
  const children = childCategories(category.slug);
  const shown = category.level === 1 ? products.slice(0, 12) : products;
  const priceDate = latestPriceDate(products);
  const url = absoluteUrl(`/c/${category.slug}`);
  const crumbs = crumbsFor(category);
  return (
    <div className={styles.page}>
      <JsonLd data={[breadcrumbList(crumbs), categoryJsonLd(category, shown, url)]} />
      <PageViewTracker pageType="category" />
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{category.name_he}</h1>
        <p className={styles.lede}>
          השוואת מחירים ל{category.name_he} בין רשתות הסופר, לפי קבצי השקיפות של הרשתות. בקטגוריה יש{" "}
          {category.canonical_count} מוצרים מייצגים, וכל אחד מושווה לפי מחיר ליחידת מידה.
        </p>
      </header>

      {children.length > 0 ? (
        <section className={styles.section} aria-labelledby="h-sub">
          <h2 id="h-sub" className={styles.h2}>
            תתי-קטגוריות
          </h2>
          <ul className={styles.linkGrid}>
            {children.map((c) => (
              <li key={c.slug}>
                <Link href={`/c/${c.slug}`} className={styles.linkRow}>
                  <span className={styles.linkName}>{c.name_he}</span>
                  <span className={styles.linkMeta}>{c.canonical_count} מוצרים</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className={styles.section} aria-labelledby="h-products">
        <h2 id="h-products" className={styles.h2}>
          {category.level === 1 ? "המוצרים הנפוצים" : "מוצרים בקטגוריה"}
        </h2>
        <ul className={styles.linkGrid}>
          {shown.map((p) => {
            const from = startingPrice(p);
            const inner = (
              <>
                <span className={styles.linkName}>{p.name_he}</span>
                <span className={styles.linkMeta}>
                  {from !== null ? (
                    <>
                      החל מ-
                      <Price amount={from} fractionDigits={2} /> {PER_UNIT[p.base_unit]}
                    </>
                  ) : (
                    "עדיין אין מחירים"
                  )}
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

      <ListBuilderCta
        text={`קונה ${category.name_he}? הדביקי את הרשימה שלך וראי איפה הכי זול לסל כולו.`}
      />
      <TrustNote
        label={priceDate ? "המחירים נכונים לתאריך" : "נתוני הקטלוג עודכנו בתאריך"}
        updatedAt={priceDate ?? getProducts().generated_at}
      />
    </div>
  );
}
