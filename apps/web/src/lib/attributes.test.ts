import { describe, expect, it } from "vitest";
import type { AttributeTag } from "@/api/client";
import {
  attributeLabel,
  attributeTagText,
  attributeValue,
  foldTags,
  perUnitLabel,
  uomText,
  unitName,
} from "./attributes";

const tag = (key: string, status: AttributeTag["status"], value: string | null): AttributeTag => ({
  key,
  status,
  value,
});

describe("units", () => {
  it("names the unit codes the API sends", () => {
    expect(unitName("g")).toBe("ג׳");
    expect(unitName("ml")).toBe("מ״ל");
    expect(unitName("unit")).toBe("יח׳");
    expect(unitName("kg")).toBe("ק״ג");
    expect(unitName("ק״ג")).toBe("ק״ג"); // already Hebrew: untouched
    expect(unitName("pallet")).toBe("pallet"); // unknown: never guessed
  });

  it("writes a price unit (uom) in Hebrew and as 'per unit'", () => {
    expect(uomText("100g")).toBe("100 ג׳");
    expect(uomText("100ml")).toBe("100 מ״ל");
    expect(uomText("unit")).toBe("יח׳");
    expect(uomText("kg")).toBe("ק״ג");
    expect(uomText('100 מ"ל')).toBe('100 מ"ל');
    expect(perUnitLabel("100g")).toBe("ל-100 ג׳");
    expect(perUnitLabel("100ml")).toBe("ל-100 מ״ל");
    expect(perUnitLabel("unit")).toBe("ליח׳");
    expect(perUnitLabel("kg")).toBe("לק״ג");
    expect(perUnitLabel('100 מ"ל')).toBe('ל-100 מ"ל');
  });
});

describe("labels and values", () => {
  it("labels the keys the real API sends, and leaves Hebrew keys alone", () => {
    expect(attributeLabel("unit")).toBe("יחידה");
    expect(attributeLabel("pack_size")).toBe("גודל אריזה");
    expect(attributeLabel("base")).toBe("בסיס");
    expect(attributeLabel("fat_pct")).toBe("אחוז שומן");
    expect(attributeLabel("state")).toBe("מצב");
    expect(attributeLabel("flavor")).toBe("טעם");
    expect(attributeLabel("product_type")).toBe("סוג מוצר");
    expect(attributeLabel("אותו סוג מוצר")).toBe("אותו סוג מוצר");
  });

  it("translates the plant-milk bases", () => {
    expect(attributeValue("base", "soy")).toBe("סויה");
    expect(attributeValue("base", "almond")).toBe("שקדים");
    expect(attributeValue("base", "oat")).toBe("שיבולת שועל");
    expect(attributeValue("base", "rice")).toBe("אורז");
    expect(attributeValue("base", "coconut")).toBe("קוקוס");
    expect(attributeValue("base", "hemp")).toBe("hemp");
  });

  it("puts the unit inside a pack size in Hebrew", () => {
    expect(attributeValue("pack_size", "1000 g")).toBe("1000 ג׳");
    expect(attributeValue("pack_size", "1 ml")).toBe("1 מ״ל");
    expect(attributeValue("pack_size", "6 unit")).toBe("6 יח׳");
    expect(attributeValue("pack_size", "1000")).toBe("1000");
    expect(attributeValue("pack_size", "260 ג'")).toBe("260 ג'");
  });

  it("adds a percent sign to a bare fat value, keeps the rest", () => {
    expect(attributeValue("fat_pct", "3")).toBe("3%");
    expect(attributeValue("fat_pct", "3%")).toBe("3%");
    expect(attributeValue("state", "frozen")).toBe("קפוא");
    expect(attributeValue("flavor", "וניל")).toBe("וניל");
    expect(attributeValue("brand", null)).toBeNull();
    expect(attributeValue("brand", "")).toBeNull();
  });
});

describe("folding the unit into the pack size", () => {
  it("a unit tag next to pack_size becomes part of it, not a chip of its own", () => {
    const folded = foldTags([
      tag("product_type", "matched", "קמח"),
      tag("pack_size", "matched", "1000"),
      tag("unit", "matched", "g"),
    ]);
    expect(folded).toEqual([
      tag("product_type", "matched", "קמח"),
      tag("pack_size", "matched", "1000 g"),
    ]);
    expect(folded.map((t) => attributeTagText(t))).toEqual([
      "סוג מוצר, קמח",
      "גודל אריזה, 1000 ג׳",
    ]);
  });

  it("takes the worse status of the two", () => {
    expect(foldTags([tag("pack_size", "matched", "1000"), tag("unit", "differs", "ml")])).toEqual([
      tag("pack_size", "differs", "1000 ml"),
    ]);
    expect(foldTags([tag("unit", "unverified", "g"), tag("pack_size", "matched", "500")])).toEqual([
      tag("pack_size", "unverified", "500 g"),
    ]);
  });

  it("does not add the unit twice when the API already folded it", () => {
    expect(foldTags([tag("pack_size", "matched", "1000 g"), tag("unit", "matched", "g")])).toEqual([
      tag("pack_size", "matched", "1000 g"),
    ]);
  });

  it("a unit alone stays a tag, and nothing else changes", () => {
    const tags = [tag("unit", "matched", "g"), tag("brand", "differs", "תנובה")];
    expect(foldTags(tags)).toEqual(tags);
    expect(attributeTagText(tags[0]!)).toBe("יחידה, ג׳");
    const copy = foldTags(tags);
    expect(copy).not.toBe(tags); // a copy, the input is not modified
  });
});

describe("the text of a chip", () => {
  it("matched: label, value; unverified: with לא מאומת; differs: label and value", () => {
    expect(attributeTagText(tag("base", "matched", "soy"))).toBe("בסיס, סויה");
    expect(attributeTagText(tag("fat_pct", "unverified", "3"))).toBe("אחוז שומן 3% · לא מאומת");
    expect(attributeTagText(tag("brand", "differs", "מותג פרטי"))).toBe("מותג: מותג פרטי");
    expect(attributeTagText(tag("kosher", "matched", null))).toBe("כשרות");
  });

  it("plainDiffers keeps the substitution card's value-only chip for a free-text key only", () => {
    expect(
      attributeTagText(tag("מותג", "differs", "יטבתה במקום תנובה"), { plainDiffers: true }),
    ).toBe("יטבתה במקום תנובה");
    expect(attributeTagText(tag("pack_size", "differs", "1000 g"), { plainDiffers: true })).toBe(
      "גודל אריזה: 1000 ג׳",
    );
  });
});
