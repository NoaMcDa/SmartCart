import type { Metadata } from "next";
import Link from "next/link";
import styles from "./privacy.module.css";

export const metadata: Metadata = { title: "מדיניות פרטיות" };

/**
 * Privacy policy (issue #30, D10, D11), Hebrew, static. Linked from onboarding and Profile.
 * It states what the MVP actually does; keep it in step with docs/web.md "Privacy and deletion".
 */
export default function Page() {
  return (
    <article className={styles.page}>
      <h1 className={styles.title}>מדיניות פרטיות</h1>
      <p className={styles.lead}>
        בקצרה: אנחנו אוספים רק מה שצריך כדי להשוות מחירים, לא מוכרים מידע על משתמשים ולא מציגים
        תוצאות ממומנות.
      </p>

      <section aria-labelledby="p-collect">
        <h2 id="p-collect">מה נשמר ולמה</h2>
        <ul>
          <li>
            <strong>מיקום ורדיוס חיפוש.</strong> כדי למצוא סניפים קרובים ולחשב נסיעה. נשמר רק אחרי
            אישור מפורש, ורק ברמת שכונה: הקואורדינטות מעוגלות לשלוש ספרות אחרי הנקודה (כ-100 מטר) לפני
            השמירה. מיקום מדויק אינו נשמר אף פעם. אפשר גם להזין עיר ושכונה במקום מיקום המכשיר.
          </li>
          <li>
            <strong>הסופר שלי, מועדונים ואמצעי הגעה.</strong> כדי לחשב חיסכון מול החנות שלך ולהציג
            מבצעי מועדון רק לחברים.
          </li>
          <li>
            <strong>העדפות כשרות, תזונה ואלרגנים וברירות מחדל לגמישות.</strong> כדי לסנן ולהתאים
            מוצרים. ההתאמה נשענת על מידע שחולץ אוטומטית ומסומנת &quot;לא מאומת&quot; כשאינה נבדקה.
          </li>
          <li>
            <strong>רשימות קניות ותוצאות השוואה אחרונות.</strong> במכשיר שלך, ובחשבון אם התחברת.
          </li>
          <li>
            <strong>דיווחי פער.</strong> כשאת מדווחת שמחיר שונה מהמדף, נשמרים הסניף, הפריט, המחיר
            שהוצג וההערה שכתבת, כדי שנבדוק את הנתונים. בלי מיקום.
          </li>
          <li>
            <strong>אימייל.</strong> רק אם בחרת להתחבר, לצורך קוד כניסה חד-פעמי.
          </li>
        </ul>
      </section>

      <section aria-labelledby="p-nosale">
        <h2 id="p-nosale">מה אנחנו לא עושים</h2>
        <ul>
          <li>לא מוכרים ולא מעבירים מידע על משתמשים לצד שלישי.</li>
          <li>אין דירוג ממומן: מקום בתוצאות נקבע לפי המחיר בלבד.</li>
          <li>אין בשירות כלי פרסום או מעקב של צד שלישי.</li>
        </ul>
      </section>

      <section aria-labelledby="p-where">
        <h2 id="p-where">איפה המידע נמצא</h2>
        <ul>
          <li>
            <strong>במכשיר:</strong> אם לא התחברת, כל ההעדפות נשמרות רק בדפדפן שלך.
          </li>
          <li>
            <strong>בחשבון:</strong> אם התחברת, ההעדפות והרשימות נשמרות במסד הנתונים של השירות
            (Supabase), עם הרשאות ברמת שורה כך שרק את יכולה לקרוא אותן.
          </li>
          <li>
            <strong>מפה:</strong> בעמוד המפה הדפדפן טוען אריחי מפה מ-OpenStreetMap. בקשת האריחים
            חושפת בפני OpenStreetMap את כתובת ה-IP ואת האזור שמוצג במפה. לא נשלח אליהם שום מידע אחר.
          </li>
        </ul>
      </section>

      <section aria-labelledby="p-retention">
        <h2 id="p-retention">כמה זמן שומרים</h2>
        <ul>
          <li>רשימת הקנייה במצב חנות נמחקת כשמסיימים קנייה, ובכל מקרה אחרי 12 שעות.</li>
          <li>
            שאר ההעדפות נשמרות עד שתמחקי אותן. ב<Link href="/profile">פרופיל</Link> אפשר לשנות כל
            דבר, לכבות את השימוש במיקום ולמחוק הכול.
          </li>
        </ul>
      </section>

      <section aria-labelledby="p-delete">
        <h2 id="p-delete">מחיקת הנתונים שלי</h2>
        <p>
          ב<Link href="/profile">פרופיל</Link>, תחת &quot;פרטיות ונתונים&quot;, הכפתור &quot;מחקי את
          הנתונים שלי&quot; מוחק מהמכשיר את כל מה שנשמר, ואם התחברת גם את הרשימות השמורות ואת פרטי
          הפרופיל בחשבון. מחיקה מלאה של החשבון עצמו (כתובת האימייל) תתווסף בקרוב.
        </p>
      </section>

      <p className={styles.note}>
        נוסח זה מתאר את גרסת ה-MVP וטרם עבר בדיקה משפטית רשמית. המחיר הקובע הוא תמיד בקופה.
      </p>
    </article>
  );
}
