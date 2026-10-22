import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { PersonalSync } from "@/features/personal/PersonalSync";
import { ProfileSync } from "@/features/profile/ProfileSync";

/**
 * W5 owns this route group: onboarding, product, profile, split, map, store mode, privacy.
 * ProfileSync (mirror to /me/profile) lives here; AuthProvider is mounted once in the root layout.
 */
export default function SecondaryLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <ProfileSync />
      <PersonalSync />
      <AppShell>{children}</AppShell>
    </>
  );
}
