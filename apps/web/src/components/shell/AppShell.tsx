"use client";

import type { ReactNode } from "react";
import { useT } from "@/i18n/LocaleProvider";
import { shellMessages } from "@/i18n/messages/shell";
import { ConsentGate } from "@/features/consent/ConsentSheet";
import { BottomNav } from "./BottomNav";
import { TopBar } from "./TopBar";
import styles from "./AppShell.module.css";

/**
 * App chrome shared by every route group: skip link, top bar (theme switch; sections on desktop),
 * the content column capped at 1200 px, and the phone bottom tab bar.
 * Screens render inside <main>; they never set their own max width or side gutters.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const t = useT(shellMessages);
  return (
    <div className={styles.shell}>
      <a href="#main" className="skip-link">
        {t("skipLink")}
      </a>
      <TopBar />
      <main id="main" className={styles.main} data-testid="content">
        {children}
      </main>
      <BottomNav />
      <ConsentGate />
    </div>
  );
}
