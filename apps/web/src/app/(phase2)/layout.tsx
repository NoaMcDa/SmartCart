import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";

/**
 * P2-E owns this route group: /scan, /alerts, /lists/[id]/share and /lists/accept/[token]. They
 * all need to know who is signed in (alerts and shared lists are per user); the root layout mounts
 * AuthProvider, so `useAuth()` works here without a second provider.
 */
export default function Phase2Layout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
