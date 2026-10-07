"use client";

import { ThemePreferenceControl } from "@/components/theme/ThemePreferenceControl";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Price } from "@/components/ui/Price";
import { IconInfo } from "@/components/ui/icons";
import { useAuth } from "@/features/auth/AuthProvider";
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
  const entries = useSavings();
  const total = totalSaved(entries);
  if (entries.length === 0) {
    return (
      <p className={styles.muted} data-testid="savings-empty">
        עוד אין חיסכון להציג. אחרי שתסיימי קנייה במצב חנות נחשב כמה באמת חסכת, מול החנות שלך ואחרי
        נסיעה. אנחנו לא מציגים הערכות.
      </p>
    );
  }
  const recent = [...entries].reverse().slice(0, 5);
  return (
    <>
      <div className={styles.savingsTotal} data-testid="savings-total">
        <Price amount={total} size="xl" tone={total > 0 ? "good" : "default"} />
        <span className={styles.muted}>
          מצטבר מתוך <span dir="ltr">{entries.length}</span> קניות, מול החנות שלך, אחרי נסיעה
        </span>
      </div>
      <ul className={styles.savingsList}>
        {recent.map((e) => (
          <li key={e.id}>
            <span>
              {e.storeName}
              <span className={styles.muted}>
                {" · "}
                {new Date(e.at).toLocaleDateString("he-IL", { day: "numeric", month: "numeric" })}
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
  const auth = useAuth();
  if (auth.status === "signed-in") {
    return (
      <div className={styles.account}>
        <p className={styles.muted}>
          מחוברת כ-<span dir="ltr">{auth.email}</span>. ההעדפות נשמרות גם בחשבון.
        </p>
        <Button size="sm" variant="outline" onClick={() => void auth.signOut()}>
          התנתקות
        </Button>
      </div>
    );
  }
  return (
    <div className={styles.account}>
      <p className={styles.muted}>
        בלי חשבון, ההעדפות נשמרות במכשיר הזה בלבד. התחברות שומרת אותן גם בין מכשירים.
      </p>
      <Button size="sm" onClick={auth.openSignIn} disabled={auth.status === "loading"}>
        התחברות עם אימייל
      </Button>
    </div>
  );
}

/** Everything the app knows about the user, in one place (issues #55 and #30). */
export function ProfileScreen() {
  const profile = useProfile();
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>פרופיל</h1>
        <p className={styles.lead}>
          כל מה שהאפליקציה יודעת עלייך, במקום אחד. שינוי כאן משפיע על ההשוואה הבאה.
        </p>
      </header>

      {!profile.homeChainId ? (
        <p className={styles.hintBanner} data-testid="baseline-banner">
          <IconInfo size={18} />
          <span>
            עוד לא בחרת את הסופר שלך. בלי חנות בסיס לא נוכל להראות חיסכון נטו, כי החיסכון נמדד תמיד
            מול החנות שבה את קונה בדרך כלל.
          </span>
        </p>
      ) : null}

      <div className={styles.grid}>
        <Card as="section" aria-labelledby="account-heading">
          <h2 id="account-heading" className={styles.sectionTitle}>
            חשבון
          </h2>
          <AccountSection />
        </Card>

        <Card as="section" aria-labelledby="savings-heading">
          <h2 id="savings-heading" className={styles.sectionTitle}>
            החיסכון שלי
          </h2>
          <SavingsSection />
        </Card>

        <Card as="section" aria-labelledby="location-heading">
          <h2 id="location-heading" className={styles.sectionTitle}>
            מיקום ורדיוס
          </h2>
          <LocationControls />
        </Card>

        <Card as="section" aria-labelledby="chains-heading">
          <h2 id="chains-heading" className={styles.sectionTitle}>
            רשתות ומועדונים
          </h2>
          <ChainControls />
        </Card>

        <Card as="section" aria-labelledby="travel-heading">
          <h2 id="travel-heading" className={styles.sectionTitle}>
            איך אני קונה
          </h2>
          <TravelControls />
        </Card>

        <Card as="section" aria-labelledby="diet-heading">
          <h2 id="diet-heading" className={styles.sectionTitle}>
            כשרות ותזונה
          </h2>
          <DietSection />
        </Card>

        <Card as="section" aria-labelledby="flex-heading" className={styles.wide}>
          <h2 id="flex-heading" className={styles.sectionTitle}>
            ברירות מחדל לגמישות
          </h2>
          <FlexDefaultsSection />
        </Card>

        <Card as="section" aria-labelledby="theme-heading">
          <h2 id="theme-heading" className={styles.sectionTitle}>
            ערכת צבעים
          </h2>
          <ThemePreferenceControl />
        </Card>

        <Card as="section" aria-labelledby="privacy-heading">
          <h2 id="privacy-heading" className={styles.sectionTitle}>
            פרטיות ונתונים
          </h2>
          <PrivacySection />
        </Card>
      </div>
    </div>
  );
}
