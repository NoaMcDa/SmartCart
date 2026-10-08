"use client";

import type { ReactNode } from "react";
import { BottomNav } from "@/components/shell/BottomNav";
import { TopBar } from "@/components/shell/TopBar";
import { useT } from "@/i18n/LocaleProvider";
import { seoMessages } from "@/i18n/messages/seo";
import { SeoFooterLinks } from "./components";
import styles from "./seo.module.css";

/**
 * Chrome of the static SEO group: the same skip link, top bar and bottom tabs as the app (it
 * composes the shell's parts, so a visitor from search lands inside the product), plus a footer
 * with the trust links on every page.
 */
export function SeoShell({ children }: { children: ReactNode }) {
  const t = useT(seoMessages);
  return (
    <div className={styles.shell}>
      <a href="#main" className="skip-link">
        {t("skipLink")}
      </a>
      <TopBar />
      <main id="main" className={styles.main} data-testid="content">
        {children}
      </main>
      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <SeoFooterLinks />
          <p>
            {t("checkoutGoverns")} {t("footerCommitment")}
          </p>
        </div>
      </footer>
      <BottomNav />
    </div>
  );
}
