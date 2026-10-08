"use client";

import { PlaceholderPage } from "@/components/shell/PlaceholderPage";
import { useT } from "@/i18n/LocaleProvider";
import { appMessages } from "@/i18n/messages/app";

export function OfflineScreen() {
  const t = useT(appMessages);
  return (
    <PlaceholderPage
      title={t("offlineHeading")}
      description={t("offlineDescription")}
      owner="W4a"
    />
  );
}
