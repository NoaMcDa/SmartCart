import type { Metadata } from "next";
import { JsonLd } from "@/features/seo/components";
import { absoluteUrl, METHODOLOGY_PATH, METHODOLOGY_UPDATED } from "@/features/seo/config";
import { getProducts, getQuality } from "@/features/seo/data";
import { isoDate } from "@/features/seo/format";
import { breadcrumbList, webPageJsonLd } from "@/features/seo/jsonld";
import { MethodologyContent } from "@/features/seo/MethodologyContent";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import styles from "@/features/seo/seo.module.css";

const TITLE = "איך אנחנו משווים מחירים";
const DESCRIPTION =
  "מאיפה המחירים, איך מתאימים מוצרים, איך מחושב החיסכון, מה אנחנו מתחייבים לא לעשות, ומה איכות ההתאמות שלנו, עם תאריך המדידה.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: absoluteUrl(METHODOLOGY_PATH) },
  openGraph: { title: TITLE, description: DESCRIPTION, type: "article", locale: "he_IL" },
};

/*
 * The server HTML (and the metadata and JSON-LD) is Hebrew, which is what search engines index.
 * The body is a client component that switches to Arabic after hydration (#73, docs/seo.md).
 */
export default function Page() {
  const products = getProducts();
  const quality = getQuality();
  return (
    <article className={styles.page}>
      <JsonLd
        data={[
          breadcrumbList([
            { name: "בית", path: "/" },
            { name: TITLE, path: METHODOLOGY_PATH },
          ]),
          webPageJsonLd({
            name: TITLE,
            description: DESCRIPTION,
            path: METHODOLOGY_PATH,
            dateModified: isoDate(METHODOLOGY_UPDATED),
          }),
        ]}
      />
      <PageViewTracker pageType="methodology" />
      <MethodologyContent productCount={products.count} quality={quality} />
    </article>
  );
}
