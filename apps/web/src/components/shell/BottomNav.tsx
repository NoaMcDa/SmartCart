"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "./nav-items";
import styles from "./BottomNav.module.css";

/** Phone bottom tab bar (hidden at >= 768 px, where the top bar carries the sections). */
export function BottomNav() {
  const pathname = usePathname() ?? "/";
  return (
    <nav aria-label="ניווט ראשי" className={styles.nav} data-testid="bottom-nav">
      {NAV_ITEMS.map(({ key, href, label, Icon, match }) => {
        const active = match(pathname);
        if (key === "scan") {
          return (
            <div key={key} className={styles.scanItem}>
              <Link
                href={href}
                className={styles.scanButton}
                aria-label="סריקת ברקוד"
                aria-current={active ? "page" : undefined}
              >
                <Icon size={26} />
              </Link>
              <span aria-hidden="true">{label}</span>
            </div>
          );
        }
        return (
          <Link
            key={key}
            href={href}
            className={styles.item}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={22} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
