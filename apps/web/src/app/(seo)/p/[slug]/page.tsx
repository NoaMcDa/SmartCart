import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JsonLd } from "@/features/seo/components";
import { absoluteUrl, CHECKOUT_GOVERNS, isIndexable } from "@/features/seo/config";
import { getProduct, getProducts, productPages } from "@/features/seo/data";
import { PER_UNIT } from "@/features/seo/format";
import { breadcrumbList, productJsonLd } from "@/features/seo/jsonld";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import { ProductContent } from "@/features/seo/PageContents";
import styles from "@/features/seo/seo.module.css";
import type { Product } from "@/features/seo/types";

type Params = { slug: string };

/** Only the products the generator gave a page; anything else is a 404. */
export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  return productPages().map((p) => ({ slug: p.slug }));
}

function crumbsFor(product: Product) {
  return [
    { name: "בית", path: "/" },
    ...product.path.flatMap((p) => (p.slug ? [{ name: p.name_he, path: `/c/${p.slug}` }] : [])),
    { name: product.name_he, path: `/p/${product.slug}` },
  ];
}

function describe(product: Product): string {
  const unit = PER_UNIT[product.base_unit];
  return product.no_prices_yet
    ? `${product.name_he}: מה נחשב אותו מוצר ואיך מושווים מחירים לפי מחיר ${unit} בין רשתות הסופר בישראל. ${CHECKOUT_GOVERNS}`
    : `מחיר ${product.name_he} ${unit} בכל רשת סופר בישראל, לפי קבצי השקיפות של הרשתות, עם תאריך עדכון. ${CHECKOUT_GOVERNS}`;
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) return {};
  const title = `${product.name_he}: מחיר והשוואה בין סופרים`;
  const description = describe(product);
  return {
    title,
    description,
    alternates: { canonical: absoluteUrl(`/p/${slug}`) },
    openGraph: { title, description, type: "website", locale: "he_IL" },
    robots: isIndexable(product) ? undefined : { index: false, follow: true },
  };
}

export default async function Page({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) notFound();
  const crumbs = crumbsFor(product);
  const category = [...product.path].reverse().find((p) => p.slug);
  const related = getProducts()
    .products.filter(
      (p) =>
        p.has_page &&
        p.slug !== product.slug &&
        p.path.some((n) => n.slug && n.slug === category?.slug),
    )
    .slice(0, 6);
  return (
    <div className={styles.page}>
      <JsonLd
        data={[breadcrumbList(crumbs), productJsonLd(product, absoluteUrl(`/p/${product.slug}`))]}
      />
      <PageViewTracker pageType="product" />
      <ProductContent
        product={product}
        crumbs={crumbs}
        related={related}
        updatedAt={product.price_valid_from ?? getProducts().generated_at}
      />
    </div>
  );
}
