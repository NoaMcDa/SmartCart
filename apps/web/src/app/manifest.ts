import type { MetadataRoute } from "next";
import { cookies } from "next/headers";
import { THEME_COLOR } from "@/components/theme/theme-constants";
import { DEFAULT_LOCALE, LOCALE_KEY, isLocale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";

/**
 * Web app manifest, served at /manifest.webmanifest. RTL and standalone; the short name, the
 * description and `lang` follow the `sc-locale` cookie (Hebrew when it is absent), the same choice
 * the pages use.
 */
export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const stored = (await cookies()).get(LOCALE_KEY)?.value;
  const locale = isLocale(stored) ? stored : DEFAULT_LOCALE;
  return {
    id: "/",
    name: "SmartCart",
    short_name: translate(appMessages, locale, "manifestShortName"),
    description: translate(appMessages, locale, "manifestDescription"),
    lang: locale,
    dir: "rtl",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#F6F5F2",
    theme_color: THEME_COLOR.light,
    categories: ["shopping", "lifestyle", "utilities"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
      { src: "/icons/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
  };
}
