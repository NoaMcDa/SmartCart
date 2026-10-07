import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";
import { ThemePreferenceControl } from "@/components/theme/ThemePreferenceControl";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = { title: "פרופיל" };

/**
 * W5 replaces the placeholder content, but the "ערכת צבעים" section with ThemePreferenceControl
 * must stay: issue #63 requires the theme switch in Profile, in sync with the header.
 */
export default function Page() {
  return (
    <PlaceholderPage
      title="פרופיל"
      description="מיקום ורדיוס, רשתות ומועדונים, העדפות כשרות ותזונה, ברירות מחדל לגמישות, החיסכון שלי, פרטיות ומחיקת נתונים."
      owner="W5"
    >
      <Card as="section" aria-labelledby="theme-heading">
        <h2 id="theme-heading" style={{ fontSize: 16, fontWeight: 700 }}>
          ערכת צבעים
        </h2>
        <ThemePreferenceControl />
      </Card>
    </PlaceholderPage>
  );
}
