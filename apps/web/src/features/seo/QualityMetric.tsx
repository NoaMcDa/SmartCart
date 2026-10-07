import { FlexChip } from "@/components/ui";
import type { FlexLevel } from "@/components/ui";
import { formatDateHe, isoDate, percentDown } from "./format";
import type { Quality } from "./types";
import styles from "./seo.module.css";

const LEVELS: FlexLevel[] = ["exact", "any_brand", "close"];

/**
 * The public matching-quality metric (D10, issue #21). Every number is read from `quality.json`,
 * which `export-seo` writes from the latest `evaluate` row of `match_runs`; nothing here is typed
 * by hand. The headline is the "any brand" level (the one the 98% target is about); all three
 * levels are listed with the sample each was measured on. While the evaluation set is synthetic
 * the headline says so in the same sentence.
 */
export function QualityMetric({ quality }: { quality: Quality }) {
  if (!quality.available) {
    return (
      <div className={styles.metric}>
        <p className={styles.metricHeadline}>איכות ההתאמה טרם נמדדה.</p>
        <p className={styles.muted}>
          המדד יופיע כאן אחרי ההרצה הראשונה של בדיקת ההתאמות על סט ההערכה.
        </p>
      </div>
    );
  }
  const headline = quality.precision.any_brand;
  const rows = LEVELS.filter((l) => quality.precision[l] !== undefined);
  return (
    <div className={styles.metric} data-testid="quality-metric">
      {headline !== undefined ? (
        <p className={styles.metricHeadline}>
          <span dir="ltr">{percentDown(headline)}</span> מההחלפות נכונות בסט ההערכה
          {quality.synthetic ? " (סינתטי עד שיהיו נתונים אמיתיים)" : ""}
          <span className={styles.kind}>נמדד</span>
        </p>
      ) : null}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <caption>דיוק לפי רמת גמישות</caption>
          <thead>
            <tr>
              <th scope="col">רמה</th>
              <th scope="col">החלפות נכונות</th>
              <th scope="col">גודל המדגם</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((level) => (
              <tr key={level}>
                <th scope="row">
                  <FlexChip level={level} size="sm" />
                </th>
                <td className={styles.num}>
                  <span dir="ltr">{percentDown(quality.precision[level] ?? 0)}</span>
                </td>
                <td className={styles.num}>
                  <span dir="ltr">{quality.sample[level] ?? 0}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={styles.definition}>
        <p>
          <strong>הגדרה.</strong> מתוך ההחלפות שהמערכת מציגה למשתמש לפי רמת גמישות, אחוז ההחלפות שסט
          ההערכה מסמן כנכונות לאותה רמה. החלפות שנשלחות לבדיקה אנושית אינן נספרות כמוצגות. אחוזים
          מעוגלים כלפי מטה.
        </p>
        <p>
          <strong>סט ההערכה.</strong> <span dir="ltr">{quality.gold_pairs}</span> זוגות על{" "}
          <span dir="ltr">{quality.gold_items}</span> פריטים.{" "}
          {quality.synthetic
            ? "הסט נוצר מתבניות ולא מפריטים אמיתיים מהרשתות, ולכן המספר מראה שמנגנון הבדיקה פועל ושהכללים הקשיחים נשמרים, ואינו הערכה של הדיוק על מוצרים אמיתיים."
            : "הסט תויג ידנית מפריטים אמיתיים."}
        </p>
        <p>
          <strong>תאריך מדידה.</strong>{" "}
          <time dateTime={isoDate(quality.measured_at)}>{formatDateHe(quality.measured_at)}</time>.
        </p>
        <p>
          <strong>יעד.</strong> היעד שלנו הוא דיוק של{" "}
          <span dir="ltr">{percentDown(quality.target_any_brand)}</span> ברמת כל מותג
          <span className={styles.kind}>יעד</span>. זה יעד ולא תוצאה: הוא יימדד על נתונים אמיתיים
          ועל דחיות של משתמשים בבטא.
        </p>
      </div>
    </div>
  );
}
