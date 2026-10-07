import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { AuthProvider } from "@/features/auth/AuthProvider";

/**
 * P2-E owns this route group: /scan, /alerts, /lists/[id]/share and /lists/accept/[token]. They
 * all need to know who is signed in (alerts and shared lists are per user), so AuthProvider
 * wraps the shell the same way the (secondary) group does.
 */
export default function Phase2Layout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
