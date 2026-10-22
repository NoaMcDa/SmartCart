import { describe, expect, it } from "vitest";
import {
  KOSHER_LEVELS,
  activeNoteText,
  generalLevelOf,
  isKosherLevel,
  isSpecificLevel,
  kosherFilter,
  kosherNotes,
  levelLabel,
  statedCertifications,
  statedText,
} from "./kosher";

describe("the preference becomes the API's filter", () => {
  it("sends nothing when nothing is set, so a request is what it was before the filter", () => {
    expect(kosherFilter(null)).toBeNull();
    expect(kosherFilter({ level: null, onlyStated: false, passover: false })).toBeNull();
    // "only stated" alone filters nothing: there is no level and no Passover to state
    expect(kosherFilter({ level: null, onlyStated: true, passover: false })).toBeNull();
  });

  it("sends the level, the switch and Passover", () => {
    expect(kosherFilter({ level: "mehadrin", onlyStated: true, passover: false })).toEqual({
      level: "mehadrin",
      only_stated: true,
      passover: false,
    });
    expect(kosherFilter({ level: null, onlyStated: false, passover: true })).toEqual({
      level: null,
      only_stated: false,
      passover: true,
    });
  });

  it("knows the nine levels the API accepts, and nothing else", () => {
    expect(KOSHER_LEVELS).toHaveLength(9);
    for (const l of KOSHER_LEVELS) expect(isKosherLevel(l)).toBe(true);
    for (const bad of ["none", "super", "", null, undefined, 3, "BADATZ"]) {
      expect(isKosherLevel(bad)).toBe(false);
    }
  });

  it("maps a named hechsher to the general level the segmented control shows", () => {
    expect(generalLevelOf("badatz_eida")).toBe("badatz");
    expect(generalLevelOf("badatz_agudat")).toBe("badatz");
    expect(generalLevelOf("landau")).toBe("regular");
    expect(generalLevelOf("rabbanut_mehadrin")).toBe("mehadrin");
    expect(generalLevelOf("mehadrin")).toBe("mehadrin");
    expect(isSpecificLevel("landau")).toBe(true);
    expect(isSpecificLevel("badatz")).toBe(false);
    expect(isSpecificLevel(null)).toBe(false);
  });
});

describe("what a label says", () => {
  it("names the certification the name states, without the generic marks a named one implies", () => {
    expect(statedCertifications(["badatz", "badatz_eida"])).toEqual(["badatz_eida"]);
    expect(statedCertifications(["rabbanut_mehadrin", "mehadrin", "rabbanut"])).toEqual([
      "rabbanut_mehadrin",
    ]);
    expect(statedCertifications(["kosher", "mehadrin"])).toEqual(["mehadrin"]);
    expect(statedCertifications(["kosher"])).toEqual(["kosher"]);
    expect(statedCertifications(["dairy", "passover"])).toEqual([]);
    expect(statedText(["badatz", "badatz_eida", "mehadrin"], "he")).toBe(
      'בד"ץ העדה החרדית, מהדרין',
    );
    expect(statedText(["badatz"], "ar")).toBe("بداتس");
    expect(statedText([], "he")).toBeNull();
  });

  it("a level that is met says what the name states; an unknown one warns, in both languages", () => {
    const met = { level: "meets" as const, passover: null, stated: ["mehadrin"] };
    expect(kosherNotes(met, "he")).toEqual([
      { variant: "matched", kind: "level-meets", text: "כשרות לפי שם המוצר: מהדרין" },
    ]);
    const unknown = { level: "unknown" as const, passover: null, stated: [] };
    expect(kosherNotes(unknown, "he")).toEqual([
      { variant: "unverified", kind: "level-unknown", text: "כשרות לא ידועה — בדקו על האריזה" },
    ]);
    expect(kosherNotes(unknown, "ar")[0]!.text).toBe("الكاشير غير معروف — تحققوا من العبوة");
  });

  it("Passover has a note of its own, next to the level's", () => {
    const both = { level: "meets" as const, passover: "unknown" as const, stated: ["badatz"] };
    const notes = kosherNotes(both, "he");
    expect(notes.map((n) => n.kind)).toEqual(["level-meets", "passover-unknown"]);
    expect(notes[1]!.text).toBe("כשרות לפסח לא ידועה — בדקו על האריזה");
    expect(kosherNotes({ level: null, passover: "meets", stated: ["passover"] }, "he")).toEqual([
      { variant: "matched", kind: "passover-meets", text: "כשר לפסח, לפי שם המוצר" },
    ]);
  });

  it("shows nothing without a label (no filter)", () => {
    expect(kosherNotes(null)).toEqual([]);
    expect(kosherNotes(undefined)).toEqual([]);
    expect(kosherNotes({ level: null, passover: null, stated: [] })).toEqual([]);
  });

  it("says on the results that a filter is on, and what it does", () => {
    expect(activeNoteText(null)).toBeNull();
    expect(activeNoteText({ level: null, onlyStated: true, passover: false })).toBeNull();
    expect(activeNoteText({ level: "badatz_eida", onlyStated: false, passover: false })).toBe(
      'סינון כשרות פעיל: בד"ץ העדה החרדית. לא מוצג מוצר ששמו מציין כשרות אחרת.',
    );
    expect(activeNoteText({ level: "regular", onlyStated: true, passover: true }, "he")).toBe(
      "סינון כשרות פעיל: כשר, כשר לפסח. מוצגים רק מוצרים שהכשרות שלהם מצוינת בשם.",
    );
    expect(levelLabel(null, "he")).toBe("ללא העדפה");
    expect(levelLabel("badatz", "ar")).toBe("بداتس");
  });
});
