import type { Metadata } from "next";
import { PrivacyBody } from "./PrivacyBody";

export const metadata: Metadata = { title: "מדיניות פרטיות" };

/**
 * Privacy policy (issue #30, D10, D11), static, Hebrew in the server markup and Arabic after mount.
 * Linked from onboarding and Profile. The text is in `PrivacyBody` and `i18n/messages/privacy.ts`.
 */
export default function Page() {
  return <PrivacyBody />;
}
