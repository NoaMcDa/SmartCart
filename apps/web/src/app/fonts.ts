import localFont from "next/font/local";

/**
 * Heebo, self-hosted. The woff2 files in public/fonts were downloaded once from Google Fonts
 * (scripts/fetch-heebo.sh) and are committed with their SIL OFL license, so the app never calls
 * fonts.googleapis.com and the font works offline. next/font copies them into /_next/static/media
 * with hashed names and preloads them.
 */
export const heebo = localFont({
  src: [
    { path: "../../public/fonts/Heebo-400.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/Heebo-500.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/Heebo-600.woff2", weight: "600", style: "normal" },
    { path: "../../public/fonts/Heebo-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-heebo",
  display: "swap",
  fallback: ["system-ui", "Arial", "sans-serif"],
});
