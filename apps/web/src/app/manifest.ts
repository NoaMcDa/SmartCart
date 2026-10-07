import type { MetadataRoute } from "next";
import { THEME_COLOR } from "@/components/theme/theme-constants";

/** Web app manifest, served at /manifest.webmanifest. Hebrew, RTL, standalone. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "SmartCart",
    short_name: "סמארטקארט",
    description: "השוואת מחירי סופר לכל הרשימה, עם חיסכון נטו לעומת הסופר שלך.",
    lang: "he",
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
