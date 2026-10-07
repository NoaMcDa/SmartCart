import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

/** W5 owns this route group: onboarding, product, profile, split, map, store mode. */
export default function SecondaryLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
