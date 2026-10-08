"use client";

import { useEffect, useId, useMemo, useState, type FormEvent } from "react";
import { Button, Card, IconInfo, Price } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import controls from "@/features/profile/controls/controls.module.css";
import { totalSaved, useSavings } from "@/features/profile/savingsHistory";
import { clearBudget, MAX_BUDGET, saveBudget, useBudget } from "./budgetState";
import { currentMonth, dayLabel, israelDate, monthName, monthOf, monthsEndingAt } from "./month";
import { SpendChart } from "./SpendChart";
import { budgetStatus, monthlyTotals, useSpend } from "./spendState";
import { syncSpend } from "./sync";
import styles from "./Budget.module.css";

/**
 * Monthly budget and spend (issue #70) for Profile: set, change or clear the budget; spent and
 * remaining this month; a six-month bar chart; this month's shops. All amounts are the prices the
 * app showed when the shop was recorded ("לפי המחירים שהוצגו"), not receipts, and say so. Signed
 * in, shops recorded while signed in are also saved to the account and shops from other devices
 * appear here; signed out, everything stays on this device.
 */
export function MonthlyBudgetSection({ className }: { className?: string }) {
  const headingId = useId();
  const fieldId = useId();
  const auth = useAuth();
  const budget = useBudget();
  const { entries, pending } = useSpend();
  const savings = useSavings();
  // null = show the saved budget; a string = what the person is typing.
  const [draft, setDraft] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const month = currentMonth();
  const months = useMemo(() => monthsEndingAt(month, 6), [month]);
  const signedIn = auth.status === "signed-in";
  useEffect(() => {
    if (signedIn) void syncSpend(months);
  }, [signedIn, months]);

  const totals = monthlyTotals(entries, months);
  const status = budgetStatus(budget, entries, month);
  const thisMonth = entries
    .filter((e) => monthOf(e.date) === month)
    .sort((a, b) => (a.date === b.date ? b.id.localeCompare(a.id) : b.date.localeCompare(a.date)));
  const spent = totals.at(-1)?.total ?? 0;
  // Net saving versus the person's own store, recorded by "סיימתי" (same method as "החיסכון שלי").
  const monthSavings = savings.filter((e) => monthOf(israelDate(new Date(e.at))) === month);
  const saved = totalSaved(monthSavings);
  const shown = draft ?? (budget !== null ? String(budget) : "");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (saveBudget(shown)) {
      setDraft(null);
      setMessage({ kind: "ok", text: "התקציב נשמר." });
    } else {
      setMessage({
        kind: "error",
        text: `הזיני סכום חיובי בשקלים, עד ${MAX_BUDGET.toLocaleString("he-IL")}.`,
      });
    }
  }

  function onClear() {
    clearBudget();
    setDraft(null);
    setMessage({ kind: "ok", text: "התקציב נוקה." });
  }

  return (
    <Card
      as="section"
      id="budget"
      aria-labelledby={headingId}
      className={className}
      data-testid="budget-section"
    >
      <h2 id={headingId} className={styles.sectionTitle}>
        תקציב חודשי
      </h2>

      <form className={styles.form} onSubmit={onSubmit} noValidate>
        <div className={controls.field}>
          <label htmlFor={fieldId} className={controls.label}>
            כמה את רוצה להוציא על מכולת בחודש? (₪)
          </label>
          <input
            id={fieldId}
            className={controls.input}
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_BUDGET}
            step={1}
            dir="ltr"
            placeholder="2500"
            value={shown}
            aria-describedby={message ? `${fieldId}-msg` : undefined}
            onChange={(e) => {
              setDraft(e.target.value);
              setMessage(null);
            }}
          />
        </div>
        <div className={styles.actions}>
          <Button type="submit" size="sm" disabled={shown.trim() === ""}>
            שמירת תקציב
          </Button>
          {budget !== null ? (
            <Button type="button" size="sm" variant="outline" onClick={onClear}>
              ניקוי התקציב
            </Button>
          ) : null}
        </div>
        {message ? (
          <p
            id={`${fieldId}-msg`}
            className={message.kind === "error" ? styles.warn : styles.muted}
            role={message.kind === "error" ? "alert" : "status"}
          >
            {message.kind === "error" ? <IconInfo size={16} /> : null}
            {message.text}
          </p>
        ) : null}
      </form>

      <dl className={styles.facts} data-testid="budget-facts">
        <div>
          <dt>הוצאה ב{monthName(month)}</dt>
          <dd>
            <Price amount={spent} size="lg" data-testid="budget-spent" />
          </dd>
        </div>
        <div>
          <dt>{status && status.remaining < 0 ? "חריגה מהתקציב" : "נותר החודש"}</dt>
          <dd>
            {status ? (
              <Price
                amount={Math.abs(status.remaining)}
                size="lg"
                data-testid="budget-remaining-value"
              />
            ) : (
              <span className={styles.muted}>לא הוגדר תקציב</span>
            )}
          </dd>
        </div>
        {monthSavings.length > 0 ? (
          <div>
            <dt>חיסכון נטו מול הסופר שלך</dt>
            <dd>
              <Price
                amount={saved}
                size="lg"
                tone={saved > 0 ? "good" : "default"}
                data-testid="budget-saved"
              />
            </dd>
          </div>
        ) : null}
      </dl>

      {entries.length === 0 ? (
        <p className={styles.muted} data-testid="spend-empty">
          עוד לא נרשמה קנייה. כשתלחצי &quot;סיימתי לקנות&quot; במצב חנות, הסכום יתווסף לכאן.
        </p>
      ) : (
        <>
          <h3 className={styles.subTitle}>שישה חודשים אחרונים</h3>
          <SpendChart data={totals} budget={budget} highlight={month} />
          {thisMonth.length > 0 ? (
            <>
              <h3 className={styles.subTitle}>הקניות ב{monthName(month)}</h3>
              <ul className={styles.entries} data-testid="spend-entries">
                {thisMonth.slice(0, 8).map((e) => (
                  <li key={e.id}>
                    <span>
                      <span dir="ltr">{dayLabel(e.date)}</span> · {e.store_name}
                      {e.plan === "split" ? " (פיצול)" : ""}
                      <span className={styles.muted}>
                        {" · "}
                        <span dir="ltr">{e.item_count}</span> פריטים
                      </span>
                    </span>
                    <Price amount={e.total} />
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      )}

      <p className={styles.note} data-testid="budget-method">
        הסכומים הם לפי המחירים שהוצגו באפליקציה ברגע הקנייה, לא לפי קבלות, ולכן הם הערכה. המחיר
        הקובע הוא בקופה. החיסכון נטו נמדד תמיד מול הסופר שלך ואחרי נסיעה, באותה שיטה כמו
        ב&quot;החיסכון שלי&quot;. שומרים רק תאריך, חנות, סכום ומספר פריטים, בלי שמות מוצרים.
      </p>
      <p className={styles.note}>
        {signedIn
          ? pending.length > 0
            ? `${pending.length} קניות ממתינות לשמירה בחשבון.`
            : "הקניות שנרשמו כשהיית מחוברת נשמרות גם בחשבון שלך."
          : "בלי חשבון, הנתונים נשמרים במכשיר הזה בלבד. הם לא נמכרים ולא משותפים."}
      </p>
    </Card>
  );
}
