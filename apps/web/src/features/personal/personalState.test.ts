import { beforeEach, describe, expect, it } from "vitest";
import { resetListStoreForTests, listActions } from "@/state/list";
import { parseRow } from "@/mocks/parseRow";
import { clearLocalData, LOCAL_DATA_KEYS } from "@/features/profile/storage";
import { LIMITS } from "./personalDoc";
import {
  PERSONAL_KEY,
  getPersonal,
  personalActions,
  resetPersonalStoreForTests,
} from "./personalState";
import { MIN_LIST_LINES, recordBrandSignal, recordClearedList, recordFinishedShop } from "./record";
import { COTTAGE, EGGS, MILK, PASTA, NOW } from "./fixtures";
import { getListState } from "@/state/list";

beforeEach(() => {
  window.localStorage.clear();
  resetPersonalStoreForTests();
  resetListStoreForTests();
});

const stored = () => JSON.parse(window.localStorage.getItem(PERSONAL_KEY) ?? "null");

describe("recording", () => {
  it("records a trip with its products and quantities, on the device only", () => {
    expect(
      personalActions.recordTrip({
        kind: "finished",
        lines: [
          { ref: MILK, quantity: 2 },
          { ref: COTTAGE, quantity: 1 },
        ],
        at: NOW,
      }),
    ).toBe(true);
    const doc = getPersonal();
    expect(doc.trips).toHaveLength(1);
    expect(doc.trips[0]).toMatchObject({ kind: "finished", at: NOW.toISOString() });
    expect(doc.trips[0]!.lines).toEqual([
      { canonical_id: MILK.canonical_id, quantity: 2 },
      { canonical_id: COTTAGE.canonical_id, quantity: 1 },
    ]);
    expect(doc.refs.map((r) => r.canonical_id).sort()).toEqual(
      [MILK.canonical_id, COTTAGE.canonical_id].sort(),
    );
    expect(stored().trips).toHaveLength(1); // persisted
  });

  it("stores nothing but ids, quantities, names, categories and dates", () => {
    personalActions.recordTrip({ kind: "list", lines: [{ ref: MILK, quantity: 1 }], at: NOW });
    const text = JSON.stringify(stored());
    expect(text).not.toMatch(/price|store|shelf|lat|lon|₪/i);
    expect(Object.keys(stored()).sort()).toEqual(
      ["dismissals", "prefs", "refs", "signals", "trips", "version"].sort(),
    );
  });

  it("ignores a repeated product, a bad quantity and an empty trip", () => {
    expect(
      personalActions.recordTrip({
        kind: "list",
        lines: [
          { ref: MILK, quantity: 2 },
          { ref: MILK, quantity: 9 },
          { ref: COTTAGE, quantity: 0 },
          { ref: PASTA, quantity: Number.NaN },
          { ref: EGGS, quantity: 5000 },
        ],
      }),
    ).toBe(true);
    expect(getPersonal().trips[0]!.lines).toEqual([
      { canonical_id: MILK.canonical_id, quantity: 2 },
    ]);
    expect(personalActions.recordTrip({ kind: "list", lines: [] })).toBe(false);
    expect(getPersonal().trips).toHaveLength(1);
  });

  it("keeps at most 40 trips", () => {
    for (let i = 0; i < 45; i += 1) {
      personalActions.recordTrip({
        kind: "list",
        lines: [{ ref: MILK, quantity: 1 }],
        at: new Date(NOW.getTime() - (45 - i) * 3_600_000),
      });
    }
    expect(getPersonal().trips).toHaveLength(LIMITS.trips);
  });

  it("records nothing while learning is off, and again when it is back on", () => {
    personalActions.setPrefs({ learn: false });
    expect(
      personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] }),
    ).toBe(false);
    expect(personalActions.recordSignal("dairy.milk", "kept_brand")).toBe(false);
    expect(getPersonal().trips).toEqual([]);
    expect(getPersonal().signals).toEqual([]);
    personalActions.setPrefs({ learn: true });
    expect(personalActions.recordSignal("dairy.milk", "kept_brand")).toBe(true);
  });

  it("records a brand signal with its category and kind", () => {
    personalActions.recordSignal("dairy.milk", "rejected_substitute", NOW);
    expect(getPersonal().signals).toEqual([
      expect.objectContaining({
        taxonomy_id: "dairy.milk",
        kind: "rejected_substitute",
        at: NOW.toISOString(),
      }),
    ]);
  });
});

describe("preferences", () => {
  it("start with learning on and value packs off", () => {
    expect(getPersonal().prefs).toEqual({ learn: true, value_packs: false, updated_at: null });
  });

  it("stamp the change so the account copy can tell which side is newer", () => {
    personalActions.setPrefs({ value_packs: true }, NOW);
    expect(getPersonal().prefs).toEqual({
      learn: true,
      value_packs: true,
      updated_at: NOW.toISOString(),
    });
  });
});

describe("dismissals and clearing", () => {
  it("dismisses, undoes a dismissal, and keeps the latest per key", () => {
    personalActions.dismiss("buy_again", "1001", new Date(NOW.getTime() - 86_400_000));
    personalActions.dismiss("buy_again", "1001", NOW);
    expect(getPersonal().dismissals).toHaveLength(1);
    expect(getPersonal().dismissals[0]!.at).toBe(NOW.toISOString());
    personalActions.undismiss("buy_again", "1001");
    expect(getPersonal().dismissals).toEqual([]);
  });

  it("clearLearned empties the history and keeps the preferences", () => {
    personalActions.setPrefs({ value_packs: true });
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] });
    personalActions.recordSignal("dairy.milk", "kept_brand");
    personalActions.dismiss("buy_again", "1001");
    personalActions.clearLearned();
    const doc = getPersonal();
    expect(doc.trips).toEqual([]);
    expect(doc.signals).toEqual([]);
    expect(doc.dismissals).toEqual([]);
    expect(doc.refs).toEqual([]);
    expect(doc.prefs.value_packs).toBe(true);
    expect(stored().trips).toEqual([]);
  });

  it('"delete my data" removes the key, and the in-memory copy follows', () => {
    expect(LOCAL_DATA_KEYS).toContain(PERSONAL_KEY);
    personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 1 }] });
    expect(window.localStorage.getItem(PERSONAL_KEY)).not.toBeNull();
    clearLocalData();
    expect(window.localStorage.getItem(PERSONAL_KEY)).toBeNull();
    personalActions.wipe();
    expect(getPersonal().trips).toEqual([]);
  });
});

describe("reading", () => {
  it("survives damaged storage", () => {
    window.localStorage.setItem(PERSONAL_KEY, "{not json");
    resetPersonalStoreForTests();
    expect(getPersonal().trips).toEqual([]);
    window.localStorage.setItem(PERSONAL_KEY, JSON.stringify({ version: 1, trips: "x", prefs: 3 }));
    resetPersonalStoreForTests();
    expect(getPersonal().prefs.learn).toBe(true);
  });

  it("follows another tab's change", () => {
    getPersonal();
    window.localStorage.setItem(
      PERSONAL_KEY,
      JSON.stringify({ version: 1, prefs: { learn: false, value_packs: true, updated_at: null } }),
    );
    // no subscriber: the next read after a reset sees the stored value
    resetPersonalStoreForTests();
    expect(getPersonal().prefs).toMatchObject({ learn: false, value_packs: true });
  });
});

describe("call sites", () => {
  async function listOf(...names: string[]) {
    listActions.add(names.map((n) => parseRow(n)));
    return getListState().items;
  }

  it("a finished shop records what was ticked as a finished trip", async () => {
    await listOf("חלב", "קוטג'", "פסטה");
    const ok = recordFinishedShop(
      [
        { canonicalId: 1001, quantity: "2", checked: true },
        { canonicalId: 1002, quantity: "1", checked: false },
        { canonicalId: 1006, quantity: "3", checked: true },
      ],
      NOW,
    );
    expect(ok).toBe(true);
    expect(getPersonal().trips[0]).toMatchObject({ kind: "finished" });
    expect(getPersonal().trips[0]!.lines).toEqual([
      { canonical_id: 1001, quantity: 2 },
      { canonical_id: 1006, quantity: 3 },
    ]);
  });

  it("nothing ticked records the plan as a list, never as a finished trip", async () => {
    await listOf("חלב", "קוטג'");
    recordFinishedShop(
      [
        { canonicalId: 1001, quantity: "1", checked: false },
        { canonicalId: 1002, quantity: "1", checked: false },
      ],
      NOW,
    );
    expect(getPersonal().trips[0]).toMatchObject({ kind: "list" });
  });

  it("a line without a known product is left out, and a trip with none records nothing", () => {
    expect(recordFinishedShop([{ canonicalId: 999_999, quantity: "1", checked: true }], NOW)).toBe(
      false,
    );
    expect(getPersonal().trips).toEqual([]);
  });

  it("a cleared list is recorded only when it had at least three recognized rows", async () => {
    expect(MIN_LIST_LINES).toBe(3);
    const two = await listOf("חלב", "קוטג'");
    expect(recordClearedList(two, NOW)).toBe(false);
    const three = await listOf("פסטה");
    expect(three).toHaveLength(3);
    expect(recordClearedList(three, NOW)).toBe(true);
    expect(getPersonal().trips[0]).toMatchObject({ kind: "list" });
    expect(getPersonal().trips[0]!.lines).toHaveLength(3);
  });

  it("a row the parser did not recognize is not part of a past list", async () => {
    const items = await listOf("חלב", "קוטג'", "פסטה", "משהו לא מוכר");
    expect(items.some((i) => i.notFound)).toBe(true);
    recordClearedList(items, NOW);
    expect(getPersonal().trips[0]!.lines).toHaveLength(3);
  });

  it("a brand signal is filed under the category of the product on the list", async () => {
    await listOf("חלב");
    expect(recordBrandSignal(1001, "kept_brand")).toBe(true);
    expect(getPersonal().signals[0]).toMatchObject({
      taxonomy_id: "dairy.milk",
      kind: "kept_brand",
    });
    expect(recordBrandSignal(424242, "kept_brand")).toBe(false); // not on the list
  });
});
