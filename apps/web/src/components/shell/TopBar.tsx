"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { IconCart, IconUser } from "@/components/ui/icons";
import { useT } from "@/i18n/LocaleProvider";
import { navMessages } from "@/i18n/messages/nav";
import { NAV_ITEMS } from "./nav-items";
import styles from "./TopBar.module.css";

/**
 * Top bar. Phone: brand plus the theme switch (sections are in the bottom bar).
 * Desktop (>= 768 px): brand, the same five sections, theme switch, profile.
 */
export function TopBar() {
  const pathname = usePathname() ?? "/";
  const t = useT(navMessages);
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label={t("home")}>
          <span className={styles.logo}>
            <IconCart size={18} />
          </span>
          <span lang="en" dir="ltr">
            SmartCart
          </span>
        </Link>
        <nav aria-label={t("mainNav")} className={styles.nav} data-testid="top-nav">
          {NAV_ITEMS.filter((i) => i.key !== "profile").map(({ key, href, match }) => (
            <Link
              key={key}
              href={href}
              className={styles.link}
              aria-current={match(pathname) ? "page" : undefined}
            >
              {t(key)}
            </Link>
          ))}
        </nav>
        <div className={styles.actions}>
          <ThemeToggle />
          <Link
            href="/profile"
            className={styles.profile}
            aria-label={t("profile")}
            aria-current={pathname.startsWith("/profile") ? "page" : undefined}
          >
            <IconUser size={20} />
          </Link>
        </div>
      </div>
    </header>
  );
}
