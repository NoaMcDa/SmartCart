"use client";

import { AppShell } from "@/components/shell/AppShell";
import { Button } from "@/components/ui/Button";
import { useT } from "@/i18n/LocaleProvider";
import { appMessages } from "@/i18n/messages/app";

export default function NotFound() {
  const t = useT(appMessages);
  return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, alignItems: "flex-start" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>{t("notFoundTitle")}</h1>
        <p style={{ color: "var(--sc-muted)" }}>{t("notFoundBody")}</p>
        <Button href="/">{t("backToList")}</Button>
      </div>
    </AppShell>
  );
}
