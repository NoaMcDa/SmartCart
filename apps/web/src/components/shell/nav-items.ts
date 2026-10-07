import { IconBarcode, IconBell, IconCompare, IconList, IconUser } from "@/components/ui/icons";

export type NavItem = {
  key: "lists" | "compare" | "scan" | "alerts" | "profile";
  href: string;
  label: string;
  Icon: typeof IconList;
  /** Extra path prefixes that mark this section active (the map and split views live in Compare). */
  match: (pathname: string) => boolean;
};

/**
 * Five sections in DOM order. With dir="rtl" the first item renders rightmost, which gives the
 * spec's right-to-left order: Lists, Compare, Scan (raised center), Alerts, Profile.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { key: "lists", href: "/", label: "רשימות", Icon: IconList, match: (p) => p === "/" },
  {
    key: "compare",
    href: "/compare",
    label: "השוואה",
    Icon: IconCompare,
    match: (p) => p.startsWith("/compare") || p.startsWith("/map") || p.startsWith("/split"),
  },
  {
    key: "scan",
    href: "/scan",
    label: "סריקה",
    Icon: IconBarcode,
    match: (p) => p.startsWith("/scan"),
  },
  {
    key: "alerts",
    href: "/alerts",
    label: "התראות",
    Icon: IconBell,
    match: (p) => p.startsWith("/alerts"),
  },
  {
    key: "profile",
    href: "/profile",
    label: "פרופיל",
    Icon: IconUser,
    match: (p) => p.startsWith("/profile"),
  },
];
