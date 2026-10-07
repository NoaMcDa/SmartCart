import type { Metadata } from "next";
import { OnboardingFlow } from "@/features/onboarding/OnboardingFlow";

export const metadata: Metadata = { title: "ברוכים הבאים" };

export default function Page() {
  return <OnboardingFlow />;
}
