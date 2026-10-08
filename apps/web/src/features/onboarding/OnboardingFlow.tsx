"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { IconChevronBack, IconChevronNext, IconInfo } from "@/components/ui/icons";
import { formatRich } from "@/i18n/format";
import { useT } from "@/i18n/LocaleProvider";
import { onboardingMessages } from "@/i18n/messages/onboarding";
import { ChainControls } from "@/features/profile/controls/ChainControls";
import { LocationControls } from "@/features/profile/controls/LocationControls";
import { TravelControls } from "@/features/profile/controls/TravelControls";
import { updateProfile } from "@/features/profile/profileState";
import styles from "./Onboarding.module.css";

type StepDef = {
  titleKey: "step1Title" | "step2Title" | "step3Title";
  /** The "why we ask" text; the first step ends with a link to the privacy policy. */
  whyKey: "step1Why" | "step2Why" | "step3Why";
  privacyLink?: boolean;
  body: ReactNode;
};

const STEPS: ReadonlyArray<StepDef> = [
  { titleKey: "step1Title", whyKey: "step1Why", privacyLink: true, body: <LocationControls /> },
  { titleKey: "step2Title", whyKey: "step2Why", body: <ChainControls /> },
  { titleKey: "step3Title", whyKey: "step3Why", body: <TravelControls /> },
];

/**
 * First-run flow (issue #18): three skippable steps, each with a visible "why we ask". Answers are
 * saved as they change (the local profile; `ProfileSync` mirrors it when signed in), so skipping or
 * leaving halfway keeps what was entered and skipping leaves the documented defaults.
 */
export function OnboardingFlow() {
  const t = useT(onboardingMessages);
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
      <DocumentTitle text={t("welcome")} />
      <header className={styles.header}>
        <h1 className={styles.title}>{t("welcome")}</h1>
        <p className={styles.lead}>{t("lead")}</p>
      </header>

      <nav aria-label={t("progress")}>
        <ol className={styles.progress}>
          {STEPS.map((s, i) => (
            <li
              key={s.titleKey}
              className={styles.dot}
              data-state={i < step ? "done" : i === step ? "current" : "todo"}
              aria-current={i === step ? "step" : undefined}
            >
              <span className="sr-only">
                {t("stepSpoken", { n: i + 1, total: STEPS.length, title: t(s.titleKey) })}
              </span>
            </li>
          ))}
        </ol>
        <p className={styles.stepCount} data-testid="step-count">
          {formatRich(t("stepCount"), {
            n: <span dir="ltr">{step + 1}</span>,
            total: <span dir="ltr">{STEPS.length}</span>,
          })}
        </p>
      </nav>

      <Card as="section" aria-labelledby="step-title" className={styles.card}>
        <h2 id="step-title" className={styles.stepTitle}>
          {t(current.titleKey)}
        </h2>
        <aside className={styles.why} aria-label={t("whyAside")}>
          <IconInfo size={18} />
          <p>
            <strong>{t("whyLabel")}</strong>
            {t(current.whyKey)}
            {current.privacyLink ? (
              <>
                {" "}
                <Link href="/privacy">{t("privacyPolicy")}</Link>
              </>
            ) : null}
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
          {step >= last ? t("finish") : t("next")}
        </Button>
        <div className={styles.secondary}>
          {step > 0 ? (
            <Button
              variant="ghost"
              iconStart={<IconChevronBack size={18} />}
              onClick={() => setStep(step - 1)}
            >
              {t("back")}
            </Button>
          ) : (
            <span />
          )}
          <Button variant="ghost" onClick={next} data-testid="onboarding-skip">
            {step >= last ? t("skipFinish") : t("skipStep")}
          </Button>
        </div>
      </div>
    </div>
  );
}
