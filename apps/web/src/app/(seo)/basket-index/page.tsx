import type { Metadata } from "next";
import { JsonLd } from "@/features/seo/components";
import { absoluteUrl, BASKET_INDEX_PATH } from "@/features/seo/config";
import { basketShowsDraft, getBasketIndex, shownMonths } from "@/features/seo/data";
import { isoDate } from "@/features/seo/format";
import { breadcrumbList, webPageJsonLd } from "@/features/seo/jsonld";
import { BasketIndexContent } from "@/features/seo/PageContents";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import styles from "@/features/seo/seo.module.css";

const TITLE = "מדד הסל החודשי";
const DESCRIPTION =
  "כמה עולה סל קבוע של מוצרי יסוד בכל רשת סופר בישראל, מדי חודש. הסל מפורסם, השיטה מתועדת, והמספרים נבדקים לפני הפרסום.";

export function generateMetadata(): Metadata {
  // A preview build that shows a draft month must never be indexed.
  const showsDraft = basketShowsDraft();
  return {
    title: TITLE,
    description: DESCRIPTION,
    alternates: { canonical: absoluteUrl(BASKET_INDEX_PATH) },
    openGraph: { title: TITLE, description: DESCRIPTION, type: "article", locale: "he_IL" },
    robots: showsDraft ? { index: false, follow: false } : undefined,
  };
}

export default function Page() {
  const index = getBasketIndex();
  const months = shownMonths(index);
  const [latest, ...history] = months;
  const updatedAt = latest?.price_date ?? latest?.computed_at ?? index.generated_at;
  const crumbs = [
    { name: "בית", path: "/" },
    { name: TITLE, path: BASKET_INDEX_PATH },
  ];
  return (
    <article className={styles.page}>
      <JsonLd
        data={[
          breadcrumbList(crumbs),
          webPageJsonLd({
            name: TITLE,
            description: DESCRIPTION,
            path: BASKET_INDEX_PATH,
            dateModified: isoDate(updatedAt),
          }),
        ]}
      />
      <PageViewTracker pageType="basket_index" />
      <BasketIndexContent
        basket={index.basket}
        latest={latest}
        history={history}
        crumbs={crumbs}
        updatedAt={updatedAt}
      />
    </article>
  );
}
