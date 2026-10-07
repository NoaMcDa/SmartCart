import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

/** W4b owns this route group: list builder, comparison results, substitution card. */
export default function CoreLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
