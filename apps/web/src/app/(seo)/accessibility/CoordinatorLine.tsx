import { DEFAULT_LOCALE } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { accessibilityMessages } from "@/i18n/messages/accessibility";

type Key = keyof typeof accessibilityMessages.he;

const t = (key: Key, vars?: Record<string, string>) =>
  translate(accessibilityMessages, DEFAULT_LOCALE, key, vars);

/** Digits and a leading plus only, for a `tel:` link. */
const telHref = (phone: string) => `tel:${phone.replace(/[^\d+]/g, "")}`;

/**
 * The accessibility coordinator line (standard 5568 asks for a named contact), built from
 * NEXT_PUBLIC_CONTACT_NAME, NEXT_PUBLIC_CONTACT_EMAIL and NEXT_PUBLIC_CONTACT_PHONE (build-time
 * values). Any subset works; with none set it keeps the line saying the details will be
 * published before launch.
 */
export function CoordinatorLine({
  name,
  email,
  phone,
}: {
  name?: string;
  email?: string;
  phone?: string;
}) {
  if (!name && !email && !phone) return <> {t("pending")}</>;
  return (
    <>
      {" "}
      <span data-testid="a11y-coordinator">
        {name ? `${t("coordinator", { name })} ` : null}
        {email || phone ? `${t("reach")} ` : null}
        {email ? (
          <>
            {t("byEmail")} <a href={`mailto:${email}`}>{email}</a>
          </>
        ) : null}
        {email && phone ? ` ${t("or")} ` : null}
        {phone ? (
          <>
            {t("byPhone")}{" "}
            <a href={telHref(phone)} dir="ltr">
              {phone}
            </a>
          </>
        ) : null}
        {email || phone ? "." : null}
      </span>
    </>
  );
}
