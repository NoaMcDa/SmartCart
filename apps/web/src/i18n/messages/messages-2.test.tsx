import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VOICE_LANG, voiceLangs } from "@/features/voice/speech";
import { CHECKOUT_GOVERNS } from "@/features/seo/config";
import { formatDate, monthLabel } from "@/features/seo/format";
import { formatDay } from "@/features/history/series";
import { INTL_LOCALE } from "../locales";
import { rich, attributeTag, perUnit } from "../format-2";
import type { MessageSet } from "../messages";
import { feedbackMessages } from "./feedback";
import { historyMessages } from "./history";
import { mapMessages } from "./map";
import { methodologyMessages } from "./methodology";
import { phase2Messages } from "./phase2";
import { productMessages } from "./product";
import { recipeMessages } from "./recipe";
import { scanMessages } from "./scan";
import { seoMessages } from "./seo";
import { shareMessages } from "./share";
import { substitutionMessages } from "./substitution";
import { voiceMessages } from "./voice";

const MODULES: Record<string, MessageSet<string>> = {
  feedback: feedbackMessages,
  history: historyMessages,
  map: mapMessages,
  methodology: methodologyMessages,
  phase2: phase2Messages,
  product: productMessages,
  recipe: recipeMessages,
  scan: scanMessages,
  seo: seoMessages,
  share: shareMessages,
  substitution: substitutionMessages,
  voice: voiceMessages,
};

const tokens = (s: string) => [...s.matchAll(/\{\w+\}|<\/?\w+\/?>/g)].map((m) => m[0]).sort();

describe("message modules (AR-2)", () => {
  for (const [name, set] of Object.entries(MODULES)) {
    it(`${name}: Arabic has the keys, placeholders and markup of the Hebrew`, () => {
      expect(Object.keys(set.ar).sort()).toEqual(Object.keys(set.he).sort());
      for (const key of Object.keys(set.he)) {
        expect(tokens(set.ar[key]!), `${name}.${key}`).toEqual(tokens(set.he[key]!));
        expect(set.ar[key]!.trim(), `${name}.${key}`).not.toBe("");
      }
    });

    it(`${name}: Arabic text is Arabic, not a copy of the Hebrew`, () => {
      for (const key of Object.keys(set.he)) {
        const ar = set.ar[key]!;
        const letters = ar.replace(/<[^>]*>|\{\w+\}|[^\p{L}]/gu, "");
        // A message with no letters (a separator) or only brand names may match; others must differ.
        if (letters.length > 0 && /[֐-׿]/.test(set.he[key]!)) {
          expect(/[؀-ۿ]/.test(ar) || /^[A-Za-z]+$/.test(letters), `${name}.${key}`).toBe(true);
          expect(/[֐-׿]/.test(ar), `${name}.${key} has Hebrew`).toBe(false);
        }
      }
    });
  }

  it("the Hebrew checkout line is the one in config.ts", () => {
    expect(seoMessages.he.checkoutGoverns).toBe(CHECKOUT_GOVERNS);
    expect(mapMessages.he.checkoutGoverns).toBe(CHECKOUT_GOVERNS);
    expect(historyMessages.he.checkoutGoverns).toBe(CHECKOUT_GOVERNS);
    expect(substitutionMessages.he.checkoutGoverns).toBe(CHECKOUT_GOVERNS);
  });
});

describe("rich", () => {
  const tags = { b: (c: React.ReactNode) => <b>{c}</b>, x: <i>X</i> };

  it("wraps tagged text, inserts self-closing nodes and fills placeholders in text only", () => {
    const { container } = render(<p>{rich("a <b>{n}</b> c <x/> d", tags, { n: 5 })}</p>);
    expect(container.innerHTML).toBe("<p>a <b>5</b> c <i>X</i> d</p>");
  });

  it("leaves unknown tags and unbalanced markup as text", () => {
    const { container } = render(<p>{rich("1 <u>2</u> </b> 3", tags)}</p>);
    expect(container.textContent).toBe("1 <u>2</u> </b> 3");
  });
});

describe("locale helpers", () => {
  it("Arabic voice asks for ar-IL then ar; Hebrew keeps he-IL", () => {
    expect(voiceLangs("ar")).toEqual(["ar-IL", "ar"]);
    expect(voiceLangs("he")).toEqual([VOICE_LANG]);
  });

  it("formats dates with Latin digits, day first", () => {
    const iso = "2026-10-07T10:00:00Z";
    expect(formatDay(Date.parse(iso), INTL_LOCALE.he)).toBe("07.10");
    expect(formatDay(Date.parse(iso), INTL_LOCALE.ar)).toBe("07.10");
    expect(formatDate(iso, "he")).toBe("7 באוקטובר 2026");
    expect(formatDate(iso, "ar")).toBe("7 تشرين الأول 2026");
    expect(monthLabel("2026-01", "ar")).toBe("كانون الثاني 2026");
  });

  it("unit labels: Hebrew is lib/attributes unchanged, Arabic has its own", () => {
    expect(perUnit("100g", "he")).toBe("ל-100 ג׳");
    expect(perUnit("100g", "ar")).toBe("لكل 100 غ");
    expect(perUnit("unit", "ar")).toBe("للوحدة");
    expect(attributeTag({ key: "fat_pct", value: "3", status: "matched" }, "ar")).toBe(
      "نسبة الدسم، 3%",
    );
    expect(attributeTag({ key: "fat_pct", value: "3", status: "matched" }, "he")).toBe(
      "אחוז שומן, 3%",
    );
  });
});
