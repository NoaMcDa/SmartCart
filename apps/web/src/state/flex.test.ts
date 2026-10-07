import { describe, expect, it } from "vitest";
import {
  levelCopy,
  lookupDefault,
  rememberLabel,
  resolveFlexLevel,
  softAttributes,
  taxonomyAncestors,
} from "./flex";

describe("flexibility defaults", () => {
  it("walks the taxonomy from the node to the department", () => {
    expect(taxonomyAncestors("dairy.milk.fresh")).toEqual([
      "dairy.milk.fresh",
      "dairy.milk",
      "dairy",
    ]);
    expect(lookupDefault("dairy.milk.fresh", { dairy: "close" })).toBe("close");
    expect(lookupDefault("dairy.milk.fresh", { "dairy.milk": "exact", dairy: "close" })).toBe(
      "exact",
    );
    expect(lookupDefault("pantry.pasta", { dairy: "close" })).toBeUndefined();
  });

  it("prefers the user's default, then the smart default, then the server's level", () => {
    expect(resolveFlexLevel("dairy.milk", { "dairy.milk": "close" }, "any_brand")).toBe("close");
    expect(resolveFlexLevel("toiletries.hair", {}, "any_brand")).toBe("exact");
    expect(resolveFlexLevel("toiletries.hair", { toiletries: "any_brand" }, "exact")).toBe(
      "any_brand",
    );
    expect(resolveFlexLevel("pantry.pasta", {}, "exact")).toBe("exact");
    expect(resolveFlexLevel("pantry.pasta", {}, undefined)).toBe("any_brand");
    expect(resolveFlexLevel(null, { dairy: "close" }, undefined)).toBe("any_brand");
  });

  it("names the category in the remember switch", () => {
    const milk = {
      canonical_id: 1,
      display_name_he: "חלב",
      taxonomy_id: "dairy.milk",
      base_unit: "100ml" as const,
      category_path_he: ["מוצרי חלב", "חלב"],
    };
    expect(rememberLabel(milk)).toBe("זכרי בחירה זו לכל סוגי החלב");
    expect(rememberLabel({ ...milk, category_path_he: ["מזווה", "רסק עגבניות"] })).toBe(
      "זכרי בחירה זו לכל סוגי רסק עגבניות",
    );
    expect(rememberLabel(null)).toBe("זכרי בחירה זו לכל המוצרים מהסוג הזה");
  });

  it("has an explanation and an example for every level, with milk-specific copy", () => {
    for (const level of ["exact", "any_brand", "close"] as const) {
      const copy = levelCopy("pantry.pasta", level);
      expect(copy.explanation.length).toBeGreaterThan(5);
      expect(copy.example.length).toBeGreaterThan(5);
    }
    expect(levelCopy("dairy.milk.fresh", "any_brand").example).toContain("יטבתה");
    expect(softAttributes("dairy.milk").map((a) => a.label)).toEqual([
      "גודל אריזה אחר",
      "קרטון או שקית",
      "אחוז שומן אחר",
    ]);
    expect(softAttributes(null).length).toBeGreaterThan(0);
  });
});
