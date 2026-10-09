import type { Metadata } from "next";
import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { Showcase } from "./Showcase";

export const metadata: Metadata = {
  title: translate(appMessages, DEFAULT_LOCALE, "designSystemTitle"),
  robots: { index: false, follow: false },
};

/**
 * Developer route: every src/components/ui component in the light and the dark theme side by side
 * (stacked below ~760 px). Playwright screenshots it at 390 px and 1280 px. Not linked from the app.
 */
export default function Page() {
  return <Showcase />;
}
