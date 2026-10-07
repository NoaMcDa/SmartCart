"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { IconChevronBack, IconChevronNext, IconInfo } from "@/components/ui/icons";
import { ChainControls } from "@/features/profile/controls/ChainControls";
import { LocationControls } from "@/features/profile/controls/LocationControls";
import { TravelControls } from "@/features/profile/controls/TravelControls";
import { updateProfile } from "@/features/profile/profileState";
import styles from "./Onboarding.module.css";

type StepDef = {
  title: string;
  why: ReactNode;
  body: ReactNode;
};

const STEPS: ReadonlyArray<StepDef> = [
  {
    title: "איפה את קונה?",
    why: (
      <>
        כדי להציג סניפים קרובים אליך ולחשב כמה עולה להגיע אליהם. המיקום נשמר רק ברמת שכונה (מעוגל
        לכ-100 מטר), רק אחרי שאישרת, ואפשר למחוק אותו בכל רגע. לא מוכרים נתונים ולא משתפים אותם.{" "}
        <Link href="/privacy">מדיניות הפרטיות</Link>
      </>
    ),
    body: <LocationControls />,
  },
  {
    title: "הסופר שלי והמועדונים",
    why: (
      <>
        כדי לחשב את החיסכון מול החנות שבה את קונה בדרך כלל, ולהציג מבצעי מועדון רק אם את חברה בהם.
        בלי חנות בסיס לא נציג חיסכון, כי אנחנו לא משווים מול החנות הכי יקרה.
      </>
    ),
    body: <ChainControls />,
  },
  {
    title: "איך את עושה קניות?",
    why: (
      <>
        כדי לדעת כמה עולה הנסיעה ואם שווה לעצור בחנות נוספת. פיצול הקנייה יוצג רק אם החיסכון נטו,
        אחרי נסיעה ואחרי השווי שבחרת, באמת משתלם.
      </>
    ),
    body: <TravelControls />,
  },
];

/**
 * First-run flow (issue #18): three skippable steps, each with a visible "why we ask". Answers are
 * saved as they change (the local profile; `ProfileSync` mirrors it when signed in), so skipping or
 * leaving halfway keeps what was entered and skipping leaves the documented defaults.
 */
export function OnboardingFlow() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const last = STEPS.length - 1;
  const current = STEPS[step]!;

  function finish() {
    updateProfile({ onboardingDone: true });
    router.push("/");
  }

  function next() {
    if (step >= last) finish();
    else setStep(step + 1);
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>ברוכים הבאים</h1>
        <p className={styles.lead}>
          שלוש שאלות קצרות כדי שההשוואה הראשונה תהיה שלך. אפשר לדלג על כל שלב ולחזור אליו בפרופיל.
        </p>
      </header>

      <nav aria-label="התקדמות">
        <ol className={styles.progress}>
          {STEPS.map((s, i) => (
            <li
              key={s.title}
              className={styles.dot}
              data-state={i < step ? "done" : i === step ? "current" : "todo"}
              aria-current={i === step ? "step" : undefined}
            >
              <span className="sr-only">{`שלב ${i + 1} מתוך ${STEPS.length}: ${s.title}`}</span>
            </li>
          ))}
        </ol>
        <p className={styles.stepCount} data-testid="step-count">
          שלב <span dir="ltr">{step + 1}</span> מתוך <span dir="ltr">{STEPS.length}</span>
        </p>
      </nav>

      <Card as="section" aria-labelledby="step-title" className={styles.card}>
        <h2 id="step-title" className={styles.stepTitle}>
          {current.title}
        </h2>
        <aside className={styles.why} aria-label="למה אנחנו שואלים">
          <IconInfo size={18} />
          <p>
            <strong>למה אנחנו שואלים: </strong>
            {current.why}
          </p>
        </aside>
        {current.body}
      </Card>

      <div className={styles.actions}>
        <Button
          size="md"
          block
          onClick={next}
          iconEnd={<IconChevronNext size={18} />}
          data-testid="onboarding-next"
        >
          {step >= last ? "סיום" : "המשך"}
        </Button>
        <div className={styles.secondary}>
          {step > 0 ? (
            <Button
              variant="ghost"
              iconStart={<IconChevronBack size={18} />}
              onClick={() => setStep(step - 1)}
            >
              חזרה
            </Button>
          ) : (
            <span />
          )}
          <Button variant="ghost" onClick={next} data-testid="onboarding-skip">
            {step >= last ? "דילוג וסיום" : "דילוג על השלב"}
          </Button>
        </div>
      </div>
    </div>
  );
}
