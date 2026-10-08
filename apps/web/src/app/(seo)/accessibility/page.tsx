import type { Metadata } from "next";
import { Breadcrumbs, JsonLd } from "@/features/seo/components";
import { absoluteUrl, ACCESSIBILITY_PATH } from "@/features/seo/config";
import { formatDateHe, isoDate } from "@/features/seo/format";
import { breadcrumbList, webPageJsonLd } from "@/features/seo/jsonld";
import styles from "@/features/seo/seo.module.css";
import { CoordinatorLine } from "./CoordinatorLine";

const TITLE = "הצהרת נגישות";
const DESCRIPTION =
  "מה נבדק בנגישות של SmartCart לפי תקן ישראלי 5568 (WCAG 2.0 ברמה AA), מה עוד נשאר לבדוק ידנית ואיך לדווח על בעיה.";

/** Date of the last accessibility review. Update it with docs/a11y-report.md. */
const REVIEWED = "2026-10-07T00:00:00+03:00";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: absoluteUrl(ACCESSIBILITY_PATH) },
};

export default function Page() {
  const contactName = process.env.NEXT_PUBLIC_CONTACT_NAME?.trim() || undefined;
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || undefined;
  const contactPhone = process.env.NEXT_PUBLIC_CONTACT_PHONE?.trim() || undefined;
  const crumbs = [
    { name: "בית", path: "/" },
    { name: TITLE, path: ACCESSIBILITY_PATH },
  ];
  return (
    <article className={styles.page}>
      <JsonLd
        data={[
          breadcrumbList(crumbs),
          webPageJsonLd({
            name: TITLE,
            description: DESCRIPTION,
            path: ACCESSIBILITY_PATH,
            dateModified: isoDate(REVIEWED),
          }),
        ]}
      />
      <Breadcrumbs crumbs={crumbs} />
      <header className={styles.section}>
        <h1 className={styles.title}>{TITLE}</h1>
        <p className={styles.lede}>
          אנחנו רוצים ש-SmartCart תהיה שימושית לכולם. היעד שלנו הוא עמידה בתקן הישראלי 5568, שמקביל
          ל-WCAG 2.0 ברמה AA.
        </p>
        <p className={styles.muted}>
          נבדק לאחרונה: <time dateTime={isoDate(REVIEWED)}>{formatDateHe(REVIEWED)}</time>
        </p>
      </header>

      <section className={styles.section} aria-labelledby="h-done">
        <h2 id="h-done" className={styles.h2}>
          מה נבדק
        </h2>
        <ul>
          <li>בדיקה אוטומטית (axe) של כל מסכי האתר, בטלפון ובמחשב, בערכת נושא בהירה ובכהה.</li>
          <li>ניגודיות טקסט של לפחות 4.5:1 בכל צמדי הצבעים של ערכת העיצוב, בשתי ערכות הנושא.</li>
          <li>שמות נגישים בעברית לכל כפתור שיש בו רק אייקון.</li>
          <li>משמעות לא נמסרת בצבע בלבד: ליד כל ירוק, כתום ואדום יש אייקון וטקסט.</li>
          <li>מבנה ימין לשמאל אמיתי, ומחירים ומספרים נשארים משמאל לימין בתוך טקסט עברי.</li>
          <li>יעדי מגע של לפחות 44 פיקסלים, ומיקוד מקלדת גלוי.</li>
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="h-todo">
        <h2 id="h-todo" className={styles.h2}>
          מה עדיין לא נבדק
        </h2>
        <ul>
          <li>מעבר ידני עם קורא מסך (VoiceOver ב-iOS ו-TalkBack ב-Android) בעברית.</li>
          <li>בדיקה משפטית של ההתאמה לתקן 5568 על ידי גורם מוסמך.</li>
          <li>השלמת כל המסכים שעדיין בבנייה: הם ייבדקו כשיושלמו.</li>
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="h-report">
        <h2 id="h-report" className={styles.h2}>
          נתקלת בבעיה?
        </h2>
        <p>
          ספרי לנו איפה ומה לא עבד, ואיזה דפדפן, קורא מסך או מכשיר השתמשת.
          <CoordinatorLine name={contactName} email={contactEmail} phone={contactPhone} />
        </p>
      </section>
    </article>
  );
}
