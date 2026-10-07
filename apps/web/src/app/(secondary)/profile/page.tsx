import type { Metadata } from "next";
import { ProfileScreen } from "@/features/profile/ProfileScreen";

export const metadata: Metadata = { title: "פרופיל" };

/**
 * The "ערכת צבעים" section with ThemePreferenceControl must stay in ProfileScreen: issue #63
 * requires the theme switch in Profile, in sync with the header.
 */
export default function Page() {
  return <ProfileScreen />;
}
