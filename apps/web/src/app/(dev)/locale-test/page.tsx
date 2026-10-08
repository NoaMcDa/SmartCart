import type { Metadata } from "next";
import { LocaleSwitch } from "@/i18n/LocaleSwitch";

export const metadata: Metadata = {
  title: "Locale test",
  robots: { index: false, follow: false },
};

/**
 * Test-only page that mounts `LocaleSwitch` inside the real shell, so e2e and axe can exercise the
 * language switch before it is mounted in Profile. Not linked, not in the sitemap, noindex.
 */
export default function Page() {
  return (
    <section style={{ paddingBlock: 24 }}>
      <h1 style={{ fontSize: 20, marginBlockEnd: 12 }}>Locale test</h1>
      <LocaleSwitch />
      <p style={{ marginBlockStart: 16 }}>
        <span lang="ar">مرحبا</span> / <span lang="he">שלום</span>
      </p>
    </section>
  );
}
