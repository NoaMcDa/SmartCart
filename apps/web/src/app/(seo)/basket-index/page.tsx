import type { Metadata } from "next";
import Link from "next/link";
import { BasketDefinition, BasketMonthTable } from "@/features/seo/BasketTable";
import {
  Breadcrumbs,
  JsonLd,
  ListBuilderCta,
  NoPricesNotice,
  TrustNote,
} from "@/features/seo/components";
import { absoluteUrl, BASKET_INDEX_PATH, METHODOLOGY_PATH } from "@/features/seo/config";
import { getBasketIndex, publishedMonths } from "@/features/seo/data";
import { isoDate, monthLabelHe } from "@/features/seo/format";
import { breadcrumbList, webPageJsonLd } from "@/features/seo/jsonld";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import styles from "@/features/seo/seo.module.css";

const TITLE = "מדד הסל החודשי";
const DESCRIPTION =
  "כמה עולה סל קבוע של מוצרי יסוד בכל רשת סופר בישראל, מדי חודש. הסל מפורסם, השיטה מתועדת, והמספרים נבדקים לפני הפרסום.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: absoluteUrl(BASKET_INDEX_PATH) },
  openGraph: { title: TITLE, description: DESCRIPTION, type: "article", locale: "he_IL" },
};

export default function Page() {
  const index = getBasketIndex();
  const months = publishedMonths(index);
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
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{TITLE}</h1>
        <p className={styles.lede}>
          כל חודש אנחנו מתמחרים סל קבוע של {index.basket.item_count} מוצרי יסוד בכל רשת. הסל לא
          משתנה בתוך גרסה, כדי שאפשר יהיה להשוות בין חודשים. המדד מראה כמה הסל עולה בכל רשת ומה
          ההפרש מהזולה, ואינו חיסכון: החיסכון שלך נמדד מול החנות שלך, ברשימה שלך.
        </p>
      </header>

      {latest ? (
        <>
          <BasketMonthTable month={latest} />
          {history.length > 0 ? (
            <section className={styles.section} aria-labelledby="h-history">
              <h2 id="h-history" className={styles.h2}>
                חודשים קודמים
              </h2>
              {history.map((m) => (
                <details key={m.month} className={styles.details}>
                  <summary>{monthLabelHe(m.month)}</summary>
                  <BasketMonthTable month={m} headingLevel={3} />
                </details>
              ))}
            </section>
          ) : null}
        </>
      ) : (
        <section className={styles.section} aria-labelledby="h-empty">
          <h2 id="h-empty" className={styles.h2}>
            המדד הראשון טרם פורסם
          </h2>
          <NoPricesNotice />
          <p>
            המדד הראשון יתפרסם אחרי שנתוני המחירים ייטענו וייבדקו. עד אז אפשר לראות כאן את הסל
            שיתומחר.
          </p>
        </section>
      )}

      <section className={styles.section} aria-labelledby="h-basket">
        <h2 id="h-basket" className={styles.h2}>
          הסל הקבוע
        </h2>
        <details className={styles.details}>
          <summary>רשימת המוצרים והכמויות (גרסה {index.basket.version})</summary>
          <BasketDefinition basket={index.basket} />
        </details>
        <p className={styles.muted}>
          הרכב הסל והכמויות נבחרו בשיקול דעת ואינם סל צריכה שנמדד{" "}
          <span className={styles.kind}>הערכה</span>.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="h-method">
        <h2 id="h-method" className={styles.h2}>
          איך המדד מחושב
        </h2>
        <ul>
          <li>המחיר של רשת לכל מוצר הוא החציוני בין סניפיה, חנויות פיזיות בלבד, ליחידת מידה.</li>
          <li>מבצעים כלולים, חוץ ממבצעי מועדון. מחירי מוצרים במשקל הם הערכה.</li>
          <li>רשת שחסר לה מחיר למוצר בסל לא מדורגת, והחסרים מפורטים.</li>
          <li>
            לפני פרסום נבדקים פריטים חסרים, שינויים חריגים מהחודש הקודם ועדכניות המחירים. מדד שנכשל
            בבדיקה לא מתפרסם.
          </li>
          <li>הפרשי מחירים בין סניפים של אותה רשת אינם מופיעים במדד.</li>
        </ul>
        <p>
          <Link href={METHODOLOGY_PATH}>המתודולוגיה המלאה</Link>
        </p>
      </section>

      <ListBuilderCta text="הסל שלך שונה מהסל הממוצע. הדביקי את הרשימה שלך וראי איפה היא זולה." />
      <TrustNote label="עודכן לאחרונה:" updatedAt={updatedAt} />
    </article>
  );
}
