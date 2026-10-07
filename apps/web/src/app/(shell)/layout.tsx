import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

/** W4a owns this route group: shell-level placeholders (alerts, scan) and the offline fallback. */
export default function ShellLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
