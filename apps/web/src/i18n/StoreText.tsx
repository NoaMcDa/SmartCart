"use client";

import { Fragment } from "react";
import { chainLabel, storeLabel } from "@/lib/storeName";
import { DataText } from "./DataText";
import { useLocale } from "./LocaleProvider";

const HEBREW = /[֐-׿]/;

/**
 * A chain or store name from the data, in the UI language. `chainLabel` and `storeLabel` translate
 * what the tables know (brands in Latin letters, cities in Arabic); a part they do not know stays
 * Hebrew and is marked `lang="he"` through `DataText`, one part at a time, so a Latin brand next
 * to an unknown Hebrew city is not tagged Hebrew as a whole. In Hebrew it is the plain text.
 * Where a string is needed (an `aria-label`, an `<option>`), call `chainLabel` / `storeLabel`.
 */
export function StoreText({ name, kind = "store" }: { name: string; kind?: "chain" | "store" }) {
  const { locale } = useLocale();
  const label = kind === "chain" ? chainLabel(name, locale) : storeLabel(name, locale);
  if (locale !== "ar") return <>{label}</>;
  return (
    <>
      {label.split(" · ").map((part, i) => (
        <Fragment key={i}>
          {i > 0 ? " · " : null}
          {HEBREW.test(part) ? <DataText>{part}</DataText> : part}
        </Fragment>
      ))}
    </>
  );
}
