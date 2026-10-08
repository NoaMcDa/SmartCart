import type { HTMLAttributes, ReactNode } from "react";

export type BidiProps = Omit<HTMLAttributes<HTMLSpanElement>, "dir" | "lang"> & {
  /**
   * Language of the wrapped run. `en` (default) is for Latin brand names, SKUs and units; `he` or
   * `ar` marks a run of one RTL language inside the other.
   */
  lang?: "en" | "he" | "ar";
  children: ReactNode;
};

/**
 * An isolated run of mixed-direction text inside Hebrew or Arabic copy. Latin runs (brand names
 * such as "Coca-Cola", "3%", "UHT") get `dir="ltr"` plus `unicode-bidi: isolate` so neighbouring
 * Arabic or Hebrew punctuation cannot reorder them, and `lang` so screen readers pick the right
 * voice. Prices already do this in `<Price>`; use `<Bidi>` for everything else.
 *
 *   <Bidi>Coca-Cola</Bidi>              // Latin, ltr
 *   <Bidi lang="ar">حليب</Bidi>         // Arabic name inside Hebrew copy, rtl
 */
export function Bidi({ lang = "en", children, style, ...rest }: BidiProps) {
  return (
    <span
      lang={lang}
      dir={lang === "en" ? "ltr" : "rtl"}
      style={{ unicodeBidi: "isolate", ...style }}
      {...rest}
    >
      {children}
    </span>
  );
}
