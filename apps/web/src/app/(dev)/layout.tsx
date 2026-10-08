import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/** Developer and test-only routes: the normal shell, never indexed, never in the sitemap. */
export default function DevLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
