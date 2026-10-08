"use client";

import { DocumentTitle } from "@/components/shell/PageChrome";
import { ThemePreferenceControl } from "@/components/theme/ThemePreferenceControl";
import { LocaleSwitch } from "@/i18n/LocaleSwitch";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Price } from "@/components/ui/Price";
import { IconInfo } from "@/components/ui/icons";
import { useAuth } from "@/features/auth/AuthProvider";
import { MonthlyBudgetSection } from "@/features/budget/MonthlyBudgetSection";
import { formatRich, stripBidiMarks } from "@/i18n/format";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { profileMessages } from "@/i18n/messages/profile";
import { ChainControls } from "./controls/ChainControls";
import { LocationControls } from "./controls/LocationControls";
import { TravelControls } from "./controls/TravelControls";
import { DietSection } from "./DietSection";
import { FlexDefaultsSection } from "./FlexDefaultsSection";
import { PrivacySection } from "./PrivacySection";
import { totalSaved, useSavings } from "./savingsHistory";
import { useProfile } from "./profileState";
import styles from "./Profile.module.css";

function SavingsSection() {
  const t = useT(profileMessages);
  const { intl } = useLocale();
  const entries = useSavings();
  const total = totalSaved(entries);
  if (entries.length === 0) {
    return (
      <p className={styles.muted} data-testid="savings-empty">
        {t("savingsEmpty")}
      </p>
    );
  }
  const recent = [...entries].reverse().slice(0, 5);
  return (
    <>
      <div className={styles.savingsTotal} data-testid="savings-total">
        <Price amount={total} size="xl" tone={total > 0 ? "good" : "default"} />
        <span className={styles.muted}>
          {formatRich(t("savingsTotalNote"), { n: <span dir="ltr">{entries.length}</span> })}
        </span>
      </div>
      <ul className={styles.savingsList}>
        {recent.map((e) => (
          <li key={e.id}>
            <span>
              {e.storeName}
              <span className={styles.muted}>
                {" · "}
                {stripBidiMarks(
                  new Date(e.at).toLocaleDateString(intl, { day: "numeric", month: "numeric" }),
                )}
              </span>
            </span>
            <Price amount={e.net} tone={e.net > 0 ? "good" : "default"} />
          </li>
        ))}
      </ul>
    </>
  );
}

function AccountSection() {
  const t = useT(profileMessages);
  const auth = useAuth();
  if (auth.status === "signed-in") {
    return (
      <div className={styles.account}>
        <p className={styles.muted}>
          {formatRich(t("accountSignedIn"), { email: <span dir="ltr">{auth.email}</span> })}
        </p>
        <Button size="sm" variant="outline" onClick={() => void auth.signOut()}>
          {t("signOut")}
        </Button>
      </div>
    );
  }
  return (
    <div className={styles.account}>
      <p className={styles.muted}>{t("accountSignedOut")}</p>
      <Button size="sm" onClick={auth.openSignIn} disabled={auth.status === "loading"}>
        {t("signInWithEmail")}
      </Button>
    </div>
  );
}

/** Everything the app knows about the user, in one place (issues #55 and #30). */
export function ProfileScreen() {
  const t = useT(profileMessages);
  const profile = useProfile();
  return (
    <div className={styles.page}>
      <DocumentTitle text={t("title")} />
      <header>
        <h1 className={styles.title}>{t("title")}</h1>
        <p className={styles.lead}>{t("lead")}</p>
      </header>

      {!profile.homeChainId ? (
        <p className={styles.hintBanner} data-testid="baseline-banner">
          <IconInfo size={18} />
          <span>{t("baselineBanner")}</span>
        </p>
      ) : null}

      <div className={styles.grid}>
        <Card as="section" aria-labelledby="account-heading">
          <h2 id="account-heading" className={styles.sectionTitle}>
            {t("accountHeading")}
          </h2>
          <AccountSection />
        </Card>

        <Card as="section" aria-labelledby="savings-heading">
          <h2 id="savings-heading" className={styles.sectionTitle}>
            {t("savingsHeading")}
          </h2>
          <SavingsSection />
        </Card>

        <MonthlyBudgetSection className={styles.wide} />

        <Card as="section" aria-labelledby="location-heading">
          <h2 id="location-heading" className={styles.sectionTitle}>
            {t("locationHeading")}
          </h2>
          <LocationControls />
        </Card>

        <Card as="section" aria-labelledby="chains-heading">
          <h2 id="chains-heading" className={styles.sectionTitle}>
            {t("chainsHeading")}
          </h2>
          <ChainControls />
        </Card>

        <Card as="section" aria-labelledby="travel-heading">
          <h2 id="travel-heading" className={styles.sectionTitle}>
            {t("travelHeading")}
          </h2>
          <TravelControls />
        </Card>

        <Card as="section" aria-labelledby="diet-heading">
          <h2 id="diet-heading" className={styles.sectionTitle}>
            {t("dietHeading")}
          </h2>
          <DietSection />
        </Card>

        <Card as="section" aria-labelledby="flex-heading" className={styles.wide}>
          <h2 id="flex-heading" className={styles.sectionTitle}>
            {t("flexHeading")}
          </h2>
          <FlexDefaultsSection />
        </Card>

        <Card as="section" aria-labelledby="theme-heading">
          <h2 id="theme-heading" className={styles.sectionTitle}>
            {t("themeHeading")}
          </h2>
          <ThemePreferenceControl />
          <LocaleSwitch />
        </Card>

        <Card as="section" aria-labelledby="privacy-heading">
          <h2 id="privacy-heading" className={styles.sectionTitle}>
            {t("privacyHeading")}
          </h2>
          <PrivacySection />
        </Card>
      </div>
    </div>
  );
}
