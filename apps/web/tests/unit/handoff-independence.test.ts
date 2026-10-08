// @vitest-environment node
/**
 * Issue #72: "keep ranking, savings numbers and substitutions independent of the referral".
 * The cart handoff may read a plan (to know which store and items it sits on); nothing that ranks,
 * prices or orders plans may read handoff data. Both directions are checked on the source, next to
 * the API test that proves /compare and /optimize are byte-identical with the flags on or off
 * (services/api/tests/test_api_handoff_independence.py).
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));
const SRC = join(ROOT, "src");

const read = (rel: string) => readFileSync(join(SRC, rel), "utf8");
const lsTs = (rel: string) =>
  readdirSync(join(SRC, rel))
    .filter((f) => /\.tsx?$/.test(f) && !/\.test\.tsx?$/.test(f))
    .map((f) => `${rel}/${f}`);

/** Ranking, pricing and savings code: the state that builds the requests and reads the plans. */
const RANKING_FILES = [
  ...lsTs("state"),
  "features/split/savings.ts",
  "features/split/lastResult.ts",
  "features/compare/substitutionLevels.ts",
  "features/compare/ResultsView.tsx", // orderedPlans(): which plan is shown first
  "features/swaps/swapState.ts",
  "features/swaps/useSwaps.ts",
  "lib/format.ts",
];

const HANDOFF_READS =
  /features\/handoff|handoff\/|ChainOnline|chains\/online|useChainsOnline|\breferral\b|online_referral|search_url_template|online_url|messages\/handoff/i;

/** What the handoff must never look at: money and ranking. */
const MONEY_AND_RANKING =
  /shelf_price|line_total|effective_unit_price|net_saving|basket_saving|breakdown|recommended|\btotal\b|travel_cost|state\/comparison|split\/savings|promo_/;

describe("handoff and ranking are independent", () => {
  it("lists real ranking files", () => {
    for (const rel of RANKING_FILES) expect(read(rel).length, rel).toBeGreaterThan(50);
    expect(RANKING_FILES.length).toBeGreaterThan(8);
  });

  it("no ranking, pricing or savings file reads handoff data", () => {
    const hits = RANKING_FILES.filter((rel) => HANDOFF_READS.test(read(rel)));
    expect(hits).toEqual([]);
  });

  it("the only places that import the handoff are the two store cards", () => {
    const importers: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
          if (/from "@\/features\/handoff\//.test(readFileSync(full, "utf8"))) {
            importers.push(relative(SRC, full));
          }
        }
      }
    };
    walk(SRC);
    expect(importers.sort()).toEqual([
      "features/compare/PlanCard.tsx",
      "features/split/SplitView.tsx",
    ]);
  });

  it("the handoff reads no price, saving or ranking field", () => {
    for (const rel of lsTs("features/handoff")) {
      expect(MONEY_AND_RANKING.test(read(rel)), rel).toBe(false);
    }
    expect(MONEY_AND_RANKING.test(read("i18n/messages/handoff.ts"))).toBe(false);
  });
});
