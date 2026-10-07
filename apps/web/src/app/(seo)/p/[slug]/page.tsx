import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Tag } from "@/components/ui";
import {
  Breadcrumbs,
  FlexLevelsExplained,
  JsonLd,
  ListBuilderCta,
  NoPricesNotice,
  PriceTable,
  TrustNote,
} from "@/features/seo/components";
import { absoluteUrl, CHECKOUT_GOVERNS, INDEX_UNPRICED } from "@/features/seo/config";
import { getProduct, getProducts, productPages } from "@/features/seo/data";
import { attrLabel, attrValue, PER_UNIT } from "@/features/seo/format";
import { breadcrumbList, productJsonLd } from "@/features/seo/jsonld";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
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
    robots: product.no_prices_yet && !INDEX_UNPRICED ? { index: false, follow: true } : undefined,
  };
}

export default async function Page({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) notFound();
  const unit = PER_UNIT[product.base_unit];
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
  const typeNode = product.path[product.path.length - 1];
  return (
    <div className={styles.page}>
      <JsonLd
        data={[breadcrumbList(crumbs), productJsonLd(product, absoluteUrl(`/p/${product.slug}`))]}
      />
      <PageViewTracker pageType="product" />
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{product.name_he}</h1>
        <p className={styles.lede}>
          מחיר {unit} של {product.name_he} בכל רשת, לפי קבצי השקיפות של הרשתות.
          {product.base_unit === "kg" ? " מוצר שנמכר במשקל, והמחיר הוא הערכה לק״ג." : ""}
        </p>
        {product.base_unit === "kg" ? <Tag variant="estimated">מחיר מוערך, מוצר במשקל</Tag> : null}
      </header>

      <section className={styles.section} aria-labelledby="h-prices">
        <h2 id="h-prices" className={styles.h2}>
          מחירים לפי רשת
        </h2>
        {product.prices && product.prices.length > 0 ? (
          <>
            <PriceTable prices={product.prices} unit={product.base_unit} />
            <p className={styles.muted}>
              מחיר חציוני: החציון בין סניפי הרשת. מבצעים כלולים, חוץ ממבצעי מועדון.
            </p>
          </>
        ) : (
          <NoPricesNotice />
        )}
      </section>

      <section className={styles.section} aria-labelledby="h-match">
        <h2 id="h-match" className={styles.h2}>
          מה נחשב אותו מוצר
        </h2>
        <p>
          ברמת &quot;כל מותג&quot; אנחנו משווים רק מוצרים שהמאפיינים הבאים בהם זהים. מותג וגודל
          אריזה יכולים להשתנות, והמחיר מושווה ליחידת מידה.
        </p>
        <dl className={styles.attrs}>
          <dt>סוג המוצר</dt>
          <dd>{typeNode?.name_he ?? product.name_he}</dd>
          {Object.entries(product.critical_attrs).map(([key, value]) => (
            <div key={key} className={styles.attrRow}>
              <dt>{attrLabel(key)}</dt>
              <dd>
                <bdi>{attrValue(key, value)}</bdi>
              </dd>
            </div>
          ))}
        </dl>
        <FlexLevelsExplained />
      </section>

      {related.length > 0 ? (
        <section className={styles.section} aria-labelledby="h-related">
          <h2 id="h-related" className={styles.h2}>
            מוצרים קרובים
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

      <ListBuilderCta
        text={`רוצה לדעת איפה ${product.name_he} זול לך? הוסיפי אותו לרשימה והשוואי את הסל כולו.`}
      />
      <TrustNote
        label={product.price_valid_from ? "המחירים נכונים לתאריך" : "נתוני הקטלוג עודכנו בתאריך"}
        updatedAt={product.price_valid_from ?? getProducts().generated_at}
      />
    </div>
  );
}
