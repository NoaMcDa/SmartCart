import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { ServiceWorkerRegistrar } from "@/components/pwa/ServiceWorkerRegistrar";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { THEME_COLOR, THEME_INIT_SCRIPT } from "@/components/theme/theme-constants";
import { heebo } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  applicationName: "SmartCart",
  title: { default: "SmartCart · השוואת מחירי סופר", template: "%s · SmartCart" },
  description:
    "משווים את כל רשימת הקניות בסופרים הקרובים, עם חיסכון נטו לעומת הסופר שלך. המחיר הקובע הוא בקופה.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "סמארטקארט", statusBarStyle: "default" },
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
    // data-theme is set before first paint by THEME_INIT_SCRIPT, so the server markup differs.
    <html lang="he" dir="rtl" className={heebo.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
