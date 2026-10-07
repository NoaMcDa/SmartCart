import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { ProfileSync } from "@/features/profile/ProfileSync";

/**
 * W5 owns this route group: onboarding, product, profile, split, map, store mode, privacy.
 * AuthProvider (Supabase session, API token) and ProfileSync (mirror to /me/profile) live here.
 */
export default function SecondaryLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ProfileSync />
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
