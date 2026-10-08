import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JsonLd } from "@/features/seo/components";
import { absoluteUrl, CHECKOUT_GOVERNS } from "@/features/seo/config";
import {
  categoryPages,
  childCategories,
  getCategory,
  getProducts,
  productsIn,
} from "@/features/seo/data";
import { breadcrumbList, categoryJsonLd } from "@/features/seo/jsonld";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import { CategoryContent } from "@/features/seo/PageContents";
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
      <CategoryContent
        category={category}
        crumbs={crumbs}
        subcategories={children}
        shown={shown}
        hasPrices={priceDate !== null}
        updatedAt={priceDate ?? getProducts().generated_at}
      />
    </div>
  );
}
