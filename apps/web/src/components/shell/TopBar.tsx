"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { IconCart, IconUser } from "@/components/ui/icons";
import { NAV_ITEMS } from "./nav-items";
import styles from "./TopBar.module.css";

/**
 * Top bar. Phone: brand plus the theme switch (sections are in the bottom bar).
 * Desktop (>= 768 px): brand, the same five sections, theme switch, profile.
 */
export function TopBar() {
  const pathname = usePathname() ?? "/";
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label="SmartCart, לדף הבית">
          <span className={styles.logo}>
            <IconCart size={18} />
          </span>
          <span lang="en" dir="ltr">
            SmartCart
          </span>
        </Link>
        <nav aria-label="ניווט ראשי" className={styles.nav} data-testid="top-nav">
          {NAV_ITEMS.filter((i) => i.key !== "profile").map(({ key, href, label, match }) => (
            <Link
              key={key}
              href={href}
              className={styles.link}
              aria-current={match(pathname) ? "page" : undefined}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className={styles.actions}>
          <ThemeToggle />
          <Link
            href="/profile"
            className={styles.profile}
            aria-label="פרופיל"
            aria-current={pathname.startsWith("/profile") ? "page" : undefined}
          >
            <IconUser size={20} />
          </Link>
        </div>
      </div>
    </header>
  );
}
