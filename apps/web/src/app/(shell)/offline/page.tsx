import type { Metadata } from "next";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const metadata: Metadata = { title: "אין חיבור", robots: { index: false } };

/**
 * Offline fallback. The service worker precaches this page and serves it for any navigation it
 * has no cached copy of while the network is down.
 */
export default function Page() {
  return (
    <PlaceholderPage
      title="אין חיבור לאינטרנט"
      description="הרשימות שכבר פתחת זמינות גם בלי חיבור. המחירים יתעדכנו כשהחיבור יחזור."
      owner="W4a"
    />
  );
}
