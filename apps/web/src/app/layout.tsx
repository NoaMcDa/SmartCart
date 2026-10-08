import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { ServiceWorkerRegistrar } from "@/components/pwa/ServiceWorkerRegistrar";
import { LocaleMeta } from "@/components/shell/PageChrome";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { THEME_COLOR, THEME_INIT_SCRIPT } from "@/components/theme/theme-constants";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { DEFAULT_LOCALE, LOCALE_INIT_SCRIPT } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { appMessages } from "@/i18n/messages/app";
import { heebo } from "./fonts";
import "./globals.css";

// Server-rendered metadata is Hebrew (the static pages stay static). `LocaleMeta` and the pages'
// `DocumentTitle` write the Arabic text in the browser.
const hebrew = (key: "metaTitleDefault" | "metaDescription" | "appleTitle") =>
  translate(appMessages, DEFAULT_LOCALE, key);

export const metadata: Metadata = {
  applicationName: "SmartCart",
  title: { default: hebrew("metaTitleDefault"), template: "%s · SmartCart" },
  description: hebrew("metaDescription"),
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: hebrew("appleTitle"), statusBarStyle: "default" },
  formatDetection: { telephone: false },
  // Next emits the standard mobile-web-app-capable; iOS before 16.4 only reads the apple- prefixed one.
  other: { "apple-mobile-web-app-capable": "yes" },
  icons: {
    icon: [
      { url: "/icons/icon.svg", type: "image/svg+xml" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: THEME_COLOR.light },
    { media: "(prefers-color-scheme: dark)", color: THEME_COLOR.dark },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // data-theme and lang are set before first paint (THEME_INIT_SCRIPT, LOCALE_INIT_SCRIPT), so the
    // server markup differs. Both locales are RTL, so dir never changes.
    <html lang="he" dir="rtl" className={heebo.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: LOCALE_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <LocaleProvider>
            <LocaleMeta />
            <AuthProvider>{children}</AuthProvider>
          </LocaleProvider>
        </ThemeProvider>
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
