import localFont from "next/font/local";

/**
 * Heebo, self-hosted. The woff2 files in public/fonts were downloaded once from Google Fonts
 * (scripts/fetch-heebo.sh) and are committed with their SIL OFL license, so the app never calls
 * fonts.googleapis.com and the font works offline. next/font copies them into /_next/static/media
 * with hashed names and preloads them.
 */
const heeboFont = localFont({
  src: [
    { path: "../../public/fonts/Heebo-400.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/Heebo-500.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/Heebo-600.woff2", weight: "600", style: "normal" },
    { path: "../../public/fonts/Heebo-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-heebo",
  display: "swap",
  // No generic fallbacks here, and no Arial-based metric fallback face: next/font would put them
  // inside --font-heebo, BEFORE Noto Sans Arabic in --sc-font, and any system font with Arabic
  // glyphs (Arial on Windows and macOS, system-ui on Android and Linux) would then render Arabic
  // text instead of Noto. The generic fallbacks are listed once, after both faces, in tokens.css.
  fallback: [],
  adjustFontFallback: false,
});

/**
 * Noto Sans Arabic (SIL OFL), self-hosted the same way (scripts/fetch-noto-arabic.sh). Heebo has no
 * Arabic glyphs, so `--sc-font` lists it second: Hebrew and Latin text renders in Heebo and Arabic
 * letters fall through to Noto per glyph. No per-locale font swap, so switching language does not
 * shift the layout. `preload: false` keeps the ~270 KB of Arabic weights off Hebrew page loads; the
 * browser fetches a weight only when an Arabic glyph needs it.
 */
export const notoArabic = localFont({
  src: [
    { path: "../../public/fonts/NotoSansArabic-400.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/NotoSansArabic-500.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/NotoSansArabic-600.woff2", weight: "600", style: "normal" },
    { path: "../../public/fonts/NotoSansArabic-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-noto-arabic",
  display: "swap",
  preload: false,
  fallback: [],
  adjustFontFallback: false,
});

/**
 * `heebo.variable` is what the root layout puts on `<html>`; it carries both font variables, so
 * the layout needs no change and the Arabic stack applies to every page.
 */
export const heebo = {
  ...heeboFont,
  variable: `${heeboFont.variable} ${notoArabic.variable}`,
};
