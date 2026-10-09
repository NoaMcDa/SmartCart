import type { Metadata } from "next";
import { JsonLd } from "@/features/seo/components";
import { absoluteUrl, ACCESSIBILITY_PATH } from "@/features/seo/config";
import { isoDate } from "@/features/seo/format";
import { breadcrumbList, webPageJsonLd } from "@/features/seo/jsonld";
import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { accessibilityMessages } from "@/i18n/messages/accessibility";
import { AccessibilityBody } from "./AccessibilityBody";

const TITLE = translate(accessibilityMessages, DEFAULT_LOCALE, "pageTitle");
const DESCRIPTION =
  "מה נבדק בנגישות של SmartCart לפי תקן ישראלי 5568 (WCAG 2.0 ברמה AA), מה עוד נשאר לבדוק ידנית ואיך לדווח על בעיה.";

/** Date of the last accessibility review. Update it with docs/a11y-report.md. */
const REVIEWED = "2026-10-07T00:00:00+03:00";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: absoluteUrl(ACCESSIBILITY_PATH) },
};

export default function Page() {
  const contactName = process.env.NEXT_PUBLIC_CONTACT_NAME?.trim() || undefined;
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || undefined;
  const contactPhone = process.env.NEXT_PUBLIC_CONTACT_PHONE?.trim() || undefined;
  const crumbs = [
    { name: translate(accessibilityMessages, DEFAULT_LOCALE, "crumbHome"), path: "/" },
    { name: TITLE, path: ACCESSIBILITY_PATH },
  ];
  return (
    <AccessibilityBody
      reviewed={REVIEWED}
      contactName={contactName}
      contactEmail={contactEmail}
      contactPhone={contactPhone}
    >
      <JsonLd
        data={[
          breadcrumbList(crumbs),
          webPageJsonLd({
            name: TITLE,
            description: DESCRIPTION,
            path: ACCESSIBILITY_PATH,
            dateModified: isoDate(REVIEWED),
          }),
        ]}
      />
    </AccessibilityBody>
  );
}
