import type { Metadata } from "next";
import Link from "next/link";
import {
  Breadcrumbs,
  FlexLevelsExplained,
  JsonLd,
  Kind,
  ListBuilderCta,
} from "@/features/seo/components";
import {
  absoluteUrl,
  BASKET_INDEX_PATH,
  CHECKOUT_GOVERNS,
  METHODOLOGY_PATH,
  METHODOLOGY_UPDATED,
} from "@/features/seo/config";
import { getProducts, getQuality } from "@/features/seo/data";
import { formatDateHe, isoDate } from "@/features/seo/format";
import { breadcrumbList, webPageJsonLd } from "@/features/seo/jsonld";
import { PageViewTracker } from "@/features/seo/PageViewTracker";
import { QualityMetric } from "@/features/seo/QualityMetric";
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
      <Breadcrumbs
        crumbs={[
          { name: "בית", path: "/" },
          { name: TITLE, path: METHODOLOGY_PATH },
        ]}
      />
      <header className={styles.section}>
        <h1 className={styles.title}>{TITLE}</h1>
        <p className={styles.lede}>
          כאן כתוב בלי ז׳רגון מאיפה המחירים, איך אנחנו מחליטים שמוצר מחליף מוצר אחר, איך מחושב
          החיסכון ומה אנחנו מתחייבים לא לעשות. כל מספר בעמוד מסומן: <Kind kind="measured" /> נמדד,{" "}
          <Kind kind="estimate" /> הערכה, <Kind kind="target" /> יעד שעוד לא הושג, או{" "}
          <Kind kind="law" /> נקבע בחוק.
        </p>
        <p className={styles.muted}>
          עודכן לאחרונה:{" "}
          <time dateTime={isoDate(METHODOLOGY_UPDATED)}>{formatDateHe(METHODOLOGY_UPDATED)}</time>
        </p>
      </header>

      <section id="sources" className={styles.section} aria-labelledby="h-sources">
        <h2 id="h-sources" className={styles.h2}>
          מאיפה המחירים
        </h2>
        <p>
          המחירים מגיעים רק מקבצי השקיפות שהרשתות הגדולות חייבות לפרסם לפי חוק קידום התחרות בענף
          המזון ותקנות שקיפות המחירים. הקבצים פתוחים לציבור, ונועדו גם למי שבונה אפליקציות כמונו.
          אנחנו לא אוספים שום דבר מאתרי הקנייה המקוונים של הרשתות: לא מחירים, לא תמונות ולא תיאורים.
        </p>
        <ul>
          <li>
            הרשתות חייבות לעדכן את הקובץ תוך שעה משינוי מחיר בקופה
            <Kind kind="law" />. אנחנו טוענים קובץ מלא מדי לילה, ובמהלך היום גם עדכונים של הרשתות
            שמפרסמות אותם. על כל מחיר מוצג מתי הוא עודכן.
          </li>
          <li>
            קובץ שנכשל בבדיקות איכות (מחיר אפס, קפיצת מחיר חריגה, ירידה חדה במספר הפריטים, תאריך
            ישן) לא נטען: הוא נעצר בצד ונבדק.
          </li>
          <li>
            מחיר בסניף יכול להיות שונה ממחיר הרשת. אנחנו שומרים מחיר בסיס לרשת ויוצאי דופן לפי סניף.
            מבצעי מועדון וכרטיס אשראי מוצגים רק אם סימנת שאת חברה, עם רמת ביטחון. מוצרים במשקל
            מסומנים &quot;הערכה&quot;.
          </li>
          <li>
            <strong>{CHECKOUT_GOVERNS}</strong> אם מצאת פער בין מה שמוצג לבין המדף, כפתור
            &quot;דווחי על פער&quot; שולח אותו לבדיקה.
          </li>
        </ul>
      </section>

      <section id="matching" className={styles.section} aria-labelledby="h-matching">
        <h2 id="h-matching" className={styles.h2}>
          איך עובדת ההתאמה
        </h2>
        <p>
          כל פריט של כל רשת משויך למוצר מייצג אחד בקטלוג שלנו (&quot;מוצר קנוני&quot;), עם רמת
          ביטחון. כך אפשר להשוות גם מוצרים של מותג הבית, שאין להם ברקוד משותף בין הרשתות. אצלך נקבע,
          לכל פריט ברשימה, כמה גמישות מותר:
        </p>
        <FlexLevelsExplained />
        <ul>
          <li>
            <strong>כללים קשיחים.</strong> מאפיינים שמגדירים את המוצר, כמו אחוז שומן, טרי מול קפוא
            או טעם, חייבים להיות זהים ברמת &quot;כל מותג&quot;. דמיון בשם לא מחליף את הכלל: חלב 3%
            לא יוחלף בחלב 1%.
          </li>
          <li>
            <strong>דיוק לפני כיסוי.</strong> עדיף לפספס התאמה מאשר להציג התאמה שגויה. התאמה לא
            ודאית עוברת לבדיקה אנושית ולא מוצגת. כל החלפה שמוצגת מסומנת, עם הסיבה, ואפשר לבטל אותה.
          </li>
          <li>
            <strong>מה לא מאומת.</strong> כשרות והעדפות תזונה לא מגיעות בקבצי הרשתות בצורה מובנית,
            ולכן הן מסומנות &quot;לא מאומת&quot; ואינן כלל התאמה.
          </li>
          <li>
            לחיצה על &quot;לא תחליף טוב&quot; שולחת את ההתאמה לבדיקה ומוציאה אותה מההשוואות עד
            שתיבדק. כך משתמשים משפרים את ההתאמות לכולם.
          </li>
        </ul>
        <p className={styles.muted}>
          הקטלוג מכיל כרגע <span dir="ltr">{products.count}</span> מוצרים מייצגים
          <Kind kind="measured" />. הרשימה והדירוג שלהם נבחרו בשיקול דעת ולא נמדדו
          <Kind kind="estimate" />, והרשימה טרם נסקרה בידי מומחה תחום.
        </p>
      </section>

      <section id="saving" className={styles.section} aria-labelledby="h-saving">
        <h2 id="h-saving" className={styles.h2}>
          איך מחושב החיסכון
        </h2>
        <p>
          המספר הראשי הוא <strong>החיסכון נטו</strong>, תמיד לעומת הסופר שאמרת שאת קונה בו בדרך כלל,
          ולעולם לא לעומת הרשת היקרה ביותר:
        </p>
        <p>
          <strong>חיסכון נטו = חיסכון בסל − עלות הנסיעה − מה ששווה לך עצירה נוספת.</strong>
        </p>
        <ul>
          <li>עלות הנסיעה נגזרת מהמרחק ומאופן ההגעה שבחרת. את שווי העצירה הנוספת את קובעת.</li>
          <li>
            השוואה בין מוצרים נעשית לפי מחיר ליחידת מידה (ל-100 גרם, ל-100 מ״ל, ליחידה או לק״ג), כך
            שגודל אריזה לא מטה את התוצאה.
          </li>
          <li>פיצול הקנייה בין שתי חנויות מוצג רק אם החיסכון נטו שלו עובר סף מינימלי.</li>
        </ul>
      </section>

      <section id="neutrality" className={styles.section} aria-labelledby="h-neutrality">
        <h2 id="h-neutrality" className={styles.h2}>
          ניטרליות
        </h2>
        <ul>
          <li>אנחנו לא מוכרים מידע על משתמשים, לא לרשתות ולא לאף אחד אחר.</li>
          <li>אין דירוג ממומן: סדר התוצאות נקבע לפי מחיר בלבד.</li>
          <li>
            אם נוסיף בעתיד קישורי שותפים לחנויות מקוונות, הם יסומנו בבירור ולא ישפיעו על הדירוג.
          </li>
          <li>אין ב-SmartCart כלי פרסום או מעקב של צד שלישי.</li>
        </ul>
      </section>

      <section id="quality" className={styles.section} aria-labelledby="h-quality">
        <h2 id="h-quality" className={styles.h2}>
          מדד איכות ההתאמה
        </h2>
        <p>
          כמה מההחלפות שאנחנו מציגים נכונות? המספר נמשך אוטומטית מהמדידה האחרונה שלנו, ואיננו מוקלד
          ידנית.
        </p>
        <QualityMetric quality={quality} />
      </section>

      <section id="basket-index" className={styles.section} aria-labelledby="h-basket">
        <h2 id="h-basket" className={styles.h2}>
          מדד הסל החודשי
        </h2>
        <p>
          מדי חודש אנחנו מתמחרים סל קבוע בכל רשת,{" "}
          <Link href={BASKET_INDEX_PATH}>במדד הסל החודשי</Link>. הסל מפורסם וגרסתו קבועה, כדי שאפשר
          יהיה להשוות בין חודשים. מחיר רשת הוא החציוני בין סניפיה (חנויות פיזיות בלבד). מבצעים
          כלולים, חוץ ממבצעי מועדון, ומחירי מוצרים במשקל הם הערכה. הפרשי מחירים בין סניפים של אותה
          רשת אינם מופיעים במדד. מדד שלא עבר בדיקה לפני פרסום לא מתפרסם.
        </p>
      </section>

      <section id="privacy" className={styles.section} aria-labelledby="h-privacy">
        <h2 id="h-privacy" className={styles.h2}>
          פרטיות
        </h2>
        <ul>
          <li>המיקום נשמר מעוגל לרמת שכונה, ורק בהסכמה מפורשת.</li>
          <li>קבלות (בעתיד) יעובדו ויימחקו.</li>
          <li>לא נמכור מידע אישי, ואין אצלנו רשתות פרסום של צד שלישי.</li>
          <li>
            בבטא הסגורה אנחנו סופרים אירועים בסיסיים בשרת שלנו בלבד (למשל כמה זמן לקח להגיע לתוצאות
            וכמה החלפות נדחו), בלי תוכן הרשימה ובלי טקסט חופשי.
          </li>
          <li>אפשר למחוק את כל הנתונים מהפרופיל.</li>
        </ul>
      </section>

      <ListBuilderCta text="רוצה לראות את זה על הרשימה שלך? הדביקי אותה והשוואי בין הסופרים הקרובים." />
    </article>
  );
}
