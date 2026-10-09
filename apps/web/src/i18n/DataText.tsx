"use client";

import type { ReactNode } from "react";
import { useLocale } from "./LocaleProvider";

/**
 * Text that comes from the data and exists only in Hebrew (a chain's own item name, a promo
 * description, a store name the tables do not know), shown inside Arabic copy. In Arabic it is
 * marked `lang="he"` so a screen reader switches voice and the font stack picks the Hebrew
 * glyphs; in Hebrew it renders exactly as the plain text it always was.
 */
export function DataText({ children }: { children: ReactNode }) {
  const { locale } = useLocale();
  if (locale !== "ar") return <>{children}</>;
  return (
    <span lang="he" dir="rtl">
      {children}
    </span>
  );
}
