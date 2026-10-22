import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { PersonalSync } from "@/features/personal/PersonalSync";

/**
 * W4b owns this route group: list builder, comparison results, substitution card.
 * PersonalSync (the account copy of the person's habits, signed in only) lives here as well as in
 * the secondary group, because the list builder is where the habits are read.
 */
export default function CoreLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <PersonalSync />
      <AppShell>{children}</AppShell>
    </>
  );
}
