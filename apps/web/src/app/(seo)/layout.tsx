import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

/** W6 owns this route group: static SEO pages on the same domain (D8). W6 may swap the shell. */
export default function SeoLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
