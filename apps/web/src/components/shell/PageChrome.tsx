"use client";

import Link from "next/link";
import { useEffect } from "react";
import { IconChevronBack } from "@/components/ui/icons";
import { useLocale, useT } from "@/i18n/LocaleProvider";
import { LOCALES } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages, type AppMessageKey } from "@/i18n/messages/app";

/**
 * Small client pieces for server-rendered route files (`src/app`): they cannot call `useT`, so a
 * page names a message key and these render the text in the user's locale. The server markup is
 * Hebrew (the same text the page's `metadata` carries), and Arabic replaces it after mount.
 */

/** The page's `<h1>`. */
export function PageHeading({ id, className }: { id: AppMessageKey; className?: string }) {
  const t = useT(appMessages);
  return <h1 className={className}>{t(id)}</h1>;
}

/** A link with the back chevron and a translated label. */
export function BackLink({
  href,
  id,
  className,
}: {
  href: string;
  id: AppMessageKey;
  className?: string;
}) {
  const t = useT(appMessages);
  return (
    <Link href={href} className={className}>
      <IconChevronBack size={18} />
      {t(id)}
    </Link>
  );
}

/**
 * Keeps `document.title` in the user language. Next writes the Hebrew `metadata.title` on the
 * server; this writes the same text in Hebrew and the Arabic text in Arabic, with the same
 * `"%s · SmartCart"` template as the root layout. A server page names an app message `id`; a
 * client screen passes its own translated `text`.
 */
export function DocumentTitle({ id, text }: { id?: AppMessageKey; text?: string }) {
  const { locale } = useLocale();
  useEffect(() => {
    const title = text ?? (id ? translate(appMessages, locale, id) : "");
    if (!title) return;
    const wanted = `${title} · SmartCart`;
    // Next re-renders its Hebrew `<title>` after hydration; keep ours while this page is open.
    const apply = () => {
      if (document.title !== wanted) document.title = wanted;
    };
    apply();
    const observer = new MutationObserver(apply);
    observer.observe(document.head, { childList: true, characterData: true, subtree: true });
    return () => observer.disconnect();
  }, [locale, id, text]);
  return null;
}

/**
 * Root-layout counterpart of `DocumentTitle` for the description and the iOS home-screen title,
 * which the root `metadata` renders in Hebrew. Only the app default text is swapped: a page with
 * a description of its own (the SEO pages) keeps it.
 */
export function LocaleMeta() {
  const { locale } = useLocale();
  useEffect(() => {
    const swap = (name: string, key: "metaDescription" | "appleTitle") => {
      const wanted = translate(appMessages, locale, key);
      const known = LOCALES.map((l) => translate(appMessages, l, key));
      for (const el of document.head.querySelectorAll(`meta[name="${name}"]`)) {
        const current = el.getAttribute("content") ?? "";
        if (current !== wanted && known.includes(current)) el.setAttribute("content", wanted);
      }
    };
    swap("description", "metaDescription");
    swap("apple-mobile-web-app-title", "appleTitle");
  }, [locale]);
  return null;
}
