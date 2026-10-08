import { describe, expect, it } from "vitest";
import { photoMessages } from "./photo";

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("photo messages", () => {
  it("has the same keys and placeholders in Hebrew and Arabic", () => {
    expect(Object.keys(photoMessages.ar).sort()).toEqual(Object.keys(photoMessages.he).sort());
    for (const [key, he] of Object.entries(photoMessages.he)) {
      expect(placeholders(photoMessages.ar[key as keyof typeof photoMessages.ar]), key).toEqual(
        placeholders(he),
      );
    }
  });

  it("keeps the wording the product asks for", () => {
    expect(photoMessages.he.errQuota).toBe("הגענו למכסה החודשית, נסו שוב בחודש הבא");
    expect(photoMessages.he.deletedLine).toBe("התמונה נמחקה מהשרת");
    expect(photoMessages.he.consentAgree).toBe("מסכים/ה");
    expect(photoMessages.he.consentDecline).toBe("לא עכשיו");
    expect(photoMessages.he.entryButton).toBe("מצילום");
  });
});
