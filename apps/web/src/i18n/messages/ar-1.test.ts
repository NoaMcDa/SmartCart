import { describe, expect, it } from "vitest";
import { formatUpdatedAt } from "@/components/ui/UpdatedAt";
import { CHAINS, chainName, clubLabel } from "@/features/profile/chains";
import { CITIES, cityName, findCity } from "@/features/profile/cities";
import { categoryLabel, departmentLabel } from "@/features/profile/dietOptions";
import { attributeTagText, perUnitLabel, uomText } from "@/lib/attributes";
import { formatDistance, formatTime } from "@/lib/format";
import { levelCopy, rememberLabel, softAttributes } from "@/state/flex";
import { translate, type MessageSet } from "../messages";
import { appMessages } from "./app";
import { attributeMessages } from "./attributes";
import { authMessages } from "./auth";
import { formatMessages } from "./format";
import { onboardingMessages } from "./onboarding";
import { profileMessages } from "./profile";
import { shellMessages } from "./shell";
import { stateMessages } from "./state";
import { themeMessages } from "./theme";
import { uiMessages } from "./ui";

/** Workstream AR-1 (#73): the modules for profile, onboarding, auth, ui, theme, shell and friends. */
const MODULES: Record<string, MessageSet<string>> = {
  app: appMessages,
  attributes: attributeMessages,
  auth: authMessages,
  format: formatMessages,
  onboarding: onboardingMessages,
  profile: profileMessages,
  shell: shellMessages,
  state: stateMessages,
  theme: themeMessages,
  ui: uiMessages,
};

const HEBREW = /[֐-׿]/;
const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]!).sort();

describe("AR-1 message modules", () => {
  for (const [name, set] of Object.entries(MODULES)) {
    describe(name, () => {
      it("has the same keys in Hebrew and Arabic, and no placeholder Hebrew lacks", () => {
        expect(Object.keys(set.ar).sort()).toEqual(Object.keys(set.he).sort());
        for (const key of Object.keys(set.he)) {
          // Arabic may drop one ("قبل يومين" needs no number), never add one.
          const hebrew = placeholders(set.he[key]!);
          for (const name of placeholders(set.ar[key]!)) expect(hebrew, key).toContain(name);
        }
      });

      it("has no empty strings and no Hebrew letters in Arabic", () => {
        for (const [key, text] of Object.entries(set.ar)) {
          expect(text.trim().length, key).toBeGreaterThan(0);
          expect(HEBREW.test(text), key).toBe(false);
        }
      });
    });
  }
});

describe("Hebrew stays byte-identical", () => {
  it("keeps the chain names the API matches clubs against", () => {
    for (const chain of CHAINS) {
      expect(chainName(chain, "he")).toBe(chain.name);
      expect(translate(profileMessages, "he", `chain_${chain.id}` as never)).toBe(chain.name);
    }
    expect(clubLabel("שופרסל")).toBe("מועדון שופרסל");
  });

  it("keeps the Hebrew city and department names", () => {
    for (const city of CITIES) {
      expect(translate(profileMessages, "he", `city_${city.id}` as never)).toBe(city.name);
    }
    expect(departmentLabel("dairy")).toBe("מוצרי חלב וביצים");
    expect(categoryLabel("dairy.milk")).toBe("חלב ומשקאות חלב");
    expect(categoryLabel("something.else")).toBe("something.else");
  });

  it("formats units, distances and update times as before", () => {
    expect(formatDistance(4200)).toBe('4.2 ק"מ');
    expect(formatDistance(800)).toBe("800 מ'");
    expect(uomText("100g")).toBe("100 ג׳");
    expect(perUnitLabel("100ml")).toBe("ל-100 מ״ל");
    expect(perUnitLabel("kg")).toBe("לק״ג");
    expect(attributeTagText({ key: "pack_size", value: "1000 g", status: "matched" })).toBe(
      "גודל אריזה, 1000 ג׳",
    );
    expect(attributeTagText({ key: "fat_pct", value: "3", status: "unverified" })).toBe(
      "אחוז שומן 3% · לא מאומת",
    );
    const now = new Date("2026-10-07T12:00:00Z");
    expect(formatUpdatedAt("2026-10-07T03:40:00Z", now)).toBe("היום 06:40");
    expect(formatUpdatedAt("2026-10-06T15:20:00Z", now)).toBe("אתמול 18:20");
    expect(formatUpdatedAt("2026-10-04T08:00:00Z", now)).toBe("לפני 3 ימים");
    expect(formatUpdatedAt("2026-10-05T08:00:00Z", now)).toBe("לפני 2 ימים");
    expect(formatTime("2026-10-07T03:40:00Z")).toBe("06:40");
  });

  it("keeps the flexibility copy", () => {
    expect(rememberLabel({ category_path_he: ["מוצרי חלב", "חלב"] } as never)).toBe(
      "זכרי בחירה זו לכל סוגי החלב",
    );
    expect(levelCopy("dairy.milk.fresh", "exact").example).toBe("לדוגמה: תנובה, 3%, קרטון 1 ליטר.");
    expect(softAttributes("produce")).toEqual([{ key: "variety", label: "זן אחר" }]);
  });
});

describe("Arabic output", () => {
  it("uses Latin digits and Arabic words for times, distances and units", () => {
    const now = new Date("2026-10-07T12:00:00Z");
    expect(formatUpdatedAt("2026-10-07T03:40:00Z", now, "ar")).toBe("اليوم 06:40");
    expect(formatUpdatedAt("2026-10-06T15:20:00Z", now, "ar")).toBe("أمس 18:20");
    expect(formatUpdatedAt("2026-10-05T08:00:00Z", now, "ar")).toBe("قبل يومين");
    expect(formatUpdatedAt("2026-10-04T08:00:00Z", now, "ar")).toBe("قبل 3 أيام");
    expect(formatUpdatedAt("2026-09-12T08:00:00Z", now, "ar")).toMatch(
      /^\d{2}[./-]\d{2}[./-]\d{4}$/,
    );
    expect(formatTime("2026-10-07T03:40:00Z", "ar")).toBe("06:40");
    expect(formatDistance(4200, "ar")).toBe("4.2 كم");
    expect(formatDistance(800, "ar")).toBe("800 م");
    expect(perUnitLabel("100g", "ar")).toBe("لكل 100 غ");
  });

  it("translates cities and finds them by an Arabic name", () => {
    expect(cityName(CITIES[0]!, "ar")).toBe("تل أبيب-يافا");
    expect(findCity("موديعين")?.name).toBe("מודיעין-מכבים-רעות");
    expect(findCity("القدس")?.name).toBe("ירושלים");
    expect(findCity("ירושלים")?.name).toBe("ירושלים");
    expect(chainName(CHAINS[1]!, "ar")).toBe("Rami Levy");
  });
});
