"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/i18n/LocaleProvider";
import { navMessages } from "@/i18n/messages/nav";
import { NAV_ITEMS } from "./nav-items";
import styles from "./BottomNav.module.css";

/** Phone bottom tab bar (hidden at >= 768 px, where the top bar carries the sections). */
export function BottomNav() {
  const pathname = usePathname() ?? "/";
  const t = useT(navMessages);
  return (
    <nav aria-label={t("mainNav")} className={styles.nav} data-testid="bottom-nav">
      {NAV_ITEMS.map(({ key, href, Icon, match }) => {
        const label = t(key);
        const active = match(pathname);
        if (key === "scan") {
          return (
            <div key={key} className={styles.scanItem}>
              <Link
                href={href}
                className={styles.scanButton}
                aria-label={t("scanBarcode")}
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
