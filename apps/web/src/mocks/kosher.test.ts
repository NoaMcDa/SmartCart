import { describe, expect, it } from "vitest";
import type { PricedItem } from "@/api/client";
import { compareFixture, optimizeFixture } from "./fixtures";
import {
  applyKosherToCompare,
  applyKosherToOptimize,
  judgeLevel,
  kosherActive,
  kosherHitLabel,
  kosherSwap,
} from "./kosher";

const byId = (res: ReturnType<typeof compareFixture>) =>
  new Map(res.stores.map((s) => [s.store_id, s]));
const line = (store: { items: PricedItem[] }, id: number) =>
  store.items.find((i) => i.canonical_id === id);

describe("the mock's kosher filter mirrors the API's answers", () => {
  it("judges a level like smartcart_catalog.kosher.judge", () => {
    expect(judgeLevel([], "badatz")).toBe("unknown");
    expect(judgeLevel(["mehadrin"], "regular")).toBe("meets");
    expect(judgeLevel(["badatz"], "mehadrin")).toBe("meets");
    expect(judgeLevel(["kosher"], "mehadrin")).toBe("unknown");
    expect(judgeLevel(["badatz", "badatz_eida"], "badatz_beit_yosef")).toBe("fails");
    expect(judgeLevel(["badatz"], "badatz_eida")).toBe("unknown");
    expect(judgeLevel(["not_kosher"], "regular")).toBe("fails");
    expect(judgeLevel(["not_kosher"], null)).toBe("meets");
    expect(kosherActive(null)).toBe(false);
    expect(kosherActive({ level: null, only_stated: true, passover: false })).toBe(false);
  });

  it("leaves a response alone without a filter", () => {
    const res = compareFixture();
    expect(applyKosherToCompare(res, null)).toBe(res);
    expect(applyKosherToCompare(res, { level: null, only_stated: false, passover: false })).toBe(
      res,
    );
    const opt = optimizeFixture();
    expect(applyKosherToOptimize(opt, undefined)).toBe(opt);
  });

  it("labels every line, never offers an item that is not kosher, and says what it left out", () => {
    const res = applyKosherToCompare(compareFixture(), {
      level: "mehadrin",
      only_stated: false,
      passover: false,
    });
    const stores = byId(res);
    // Rami Levy's milk states מהדרין; its other lines state nothing: unknown, shown and labelled
    const rami = stores.get(101)!;
    expect(line(rami, 1001)!.kosher).toEqual({
      level: "meets",
      passover: null,
      stated: ["mehadrin"],
    });
    expect(line(rami, 1004)!.kosher).toEqual({ level: "unknown", passover: null, stated: [] });
    // Victory's salmon says it is not kosher: gone, listed as missing and as left out by the filter
    const victory = stores.get(105)!;
    expect(line(victory, 1008)).toBeUndefined();
    expect(victory.missing).toContain(1008);
    expect(victory.kosher_excluded).toEqual([1008]);
    expect(victory.found_count).toBe(victory.items.length);
    // totals are the sum of the lines that remain
    const sum = victory.items.reduce((n, l) => n + Math.round(Number(l.line_total) * 100), 0);
    expect(Number(victory.total)).toBeCloseTo(sum / 100, 2);
    for (const s of res.stores) for (const l of s.items) expect(l.kosher).not.toBeNull();
  });

  it("only_stated drops every item that states nothing, and counts the stores left empty", () => {
    const res = applyKosherToCompare(compareFixture(), {
      level: "mehadrin",
      only_stated: true,
      passover: false,
    });
    const stores = byId(res);
    // rami: the milk (מהדרין); shufersal: the cottage cheese (בד"ץ meets mehadrin); yochananof: the
    // olive oil (בד"ץ העדה החרדית); osher ad and victory state nothing that meets it
    expect([...stores.keys()].sort()).toEqual([101, 103, 104]);
    expect(res.kosher_hidden_stores).toBe(2);
    expect(stores.get(101)!.items.map((l) => l.canonical_id)).toEqual([1001]);
    // the saving against the home store counts only what both stores supply: nothing in common
    expect(stores.get(101)!.saving_vs_home).toBe("0.00");
    expect(res.home_store_total).toBe(stores.get(103)!.total);
  });

  it("a different named hechsher is ruled out, a general one is only unknown", () => {
    const res = applyKosherToCompare(compareFixture(), {
      level: "badatz_beit_yosef",
      only_stated: false,
      passover: false,
    });
    const stores = byId(res);
    // yochananof's olive oil states בד"ץ העדה החרדית: not the one asked for, never offered
    expect(line(stores.get(104)!, 1005)).toBeUndefined();
    expect(stores.get(104)!.kosher_excluded).toEqual([1005]);
    // shufersal's cottage states a general בד"ץ: it may be the one asked for, so it is unknown
    expect(line(stores.get(103)!, 1002)!.kosher!.level).toBe("unknown");
  });

  it("kosher for Passover is its own filter", () => {
    const res = applyKosherToCompare(compareFixture(), {
      level: null,
      only_stated: false,
      passover: true,
    });
    const osher = byId(res).get(102)!;
    expect(line(osher, 1006)!.kosher).toEqual({
      level: null,
      passover: "meets",
      stated: ["passover"],
    });
    expect(line(osher, 1005)!.kosher!.passover).toBe("unknown");
    // not kosher is not kosher for Passover either
    expect(line(byId(res).get(105)!, 1008)).toBeUndefined();
  });

  it("rebuilds the plans from what remains, with the breakdown against the filtered home store", () => {
    const res = applyKosherToOptimize(optimizeFixture(), {
      level: "regular",
      only_stated: true,
      passover: false,
    });
    const single = res.single;
    const lines = single.stores[0]!.store.items;
    expect(lines.map((l) => l.canonical_id)).toEqual([1001]); // rami's milk states מהדרין
    expect(single.total).toBe(single.stores[0]!.store.total);
    expect(single.missing).toContain(1003);
    expect(single.kosher_excluded).toContain(1003); // sold there, left out by the filter
    expect(single.kosher_excluded).not.toContain(1002); // the store never sold it: not the filter's
    // the home store (shufersal) keeps only the cottage cheese; nothing in common: no basket saving
    expect(res.minimum_effort!.stores[0]!.store.items.map((l) => l.canonical_id)).toEqual([1002]);
    expect(single.breakdown!.basket_saving).toBe("0.00");
    expect(Number(single.breakdown!.net_saving)).toBeLessThanOrEqual(0);
  });

  it("labels search hits from the items behind them, and a swap's item", () => {
    const chains = ["rami_levy", "shufersal"];
    expect(
      kosherHitLabel(1001, chains, { level: "mehadrin", only_stated: false, passover: false }),
    ).toEqual({ status: "meets", meets: 1, unknown: 1, fails: 0 });
    expect(
      kosherHitLabel(1004, chains, { level: "mehadrin", only_stated: false, passover: false }),
    ).toEqual({ status: "unknown", meets: 0, unknown: 2, fails: 0 });
    expect(
      kosherHitLabel(1004, chains, { level: "mehadrin", only_stated: true, passover: false })
        .status,
    ).toBe("none");
    expect(
      kosherHitLabel(1008, ["victory"], { level: "regular", only_stated: false, passover: false })
        .status,
    ).toBe("none");
    expect(
      kosherSwap("victory", 1008, { level: "regular", only_stated: false, passover: false }),
    ).toEqual({
      label: { level: "unknown", passover: null, stated: ["not_kosher"] },
      allowed: false,
    });
    expect(kosherSwap("victory", 1008, null)).toEqual({ label: null, allowed: true });
  });
});
