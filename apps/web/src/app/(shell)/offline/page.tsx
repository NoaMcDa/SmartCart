import type { Metadata } from "next";
import { DocumentTitle } from "@/components/shell/PageChrome";
import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { OfflineScreen } from "./OfflineScreen";

export const metadata: Metadata = {
  title: translate(appMessages, DEFAULT_LOCALE, "offlineTitle"),
  robots: { index: false },
};

/**
 * Offline fallback. The service worker precaches this page and serves it for any navigation it
 * has no cached copy of while the network is down.
 */
export default function Page() {
  return (
    <>
      <DocumentTitle id="offlineTitle" />
      <OfflineScreen />
    </>
  );
}
