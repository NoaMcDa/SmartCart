import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { promoAudience } from "@/features/history/series";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import { MOCK_CHAIN_CLUBS } from "@/mocks/handlers.phase3";
import { CHAINS } from "./chains";
import { ClubName } from "./ClubName";
import {
  chainsWithClubs,
  chainsWithoutClubs,
  clubIdsOnly,
  clubRuleParts,
  clubRuleText,
  clubsOfChain,
  isClubId,
  toggleClubId,
} from "./clubs";

afterEach(() => {
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
});

describe("club ids", () => {
  it("accepts the API's ids and nothing else", () => {
    for (const id of ["ramilevy:club", "king_store:wholesale", "tivtaam:new"]) {
      expect(isClubId(id), id).toBe(true);
    }
    for (const bad of [
      "רמי לוי",
      "מועדון רמי לוי",
      "",
      "ramilevy",
      "a:b:c",
      "Rami:club",
      3,
      null,
    ]) {
      expect(isClubId(bad), String(bad)).toBe(false);
    }
  });

  it("drops the chain names a profile saved by the first picker holds", () => {
    expect(clubIdsOnly(["שופרסל", "רמי לוי", "ramilevy:club", "mega:app"])).toEqual([
      "ramilevy:club",
      "mega:app",
    ]);
  });

  it("toggles an id on and off, keeping the order of picking", () => {
    expect(toggleClubId(["a:b"], "c:d")).toEqual(["a:b", "c:d"]);
    expect(toggleClubId(["a:b", "c:d"], "a:b")).toEqual(["c:d"]);
  });

  it("the mock list follows the API: valid unique ids, each starting with its chain's slug", () => {
    const ids = MOCK_CHAIN_CLUBS.flatMap((row) => row.clubs.map((c) => c.id));
    expect(ids.every(isClubId)).toBe(true);
    expect(new Set(ids).size).toBe(ids.length);
    for (const row of MOCK_CHAIN_CLUBS) {
      const slug = row.clubs[0]!.id.split(":")[0];
      expect(row.clubs.every((c) => c.id.startsWith(`${slug}:`))).toBe(true);
      expect(CHAINS.some((c) => c.apiId === row.chain_id)).toBe(true);
    }
  });
});

describe("the club list by chain", () => {
  it("groups the clubs under the web chains, in their order, and lists the chains with none", () => {
    const groups = chainsWithClubs(MOCK_CHAIN_CLUBS);
    expect(groups.map((g) => g.key)).toEqual([
      "rami_levy",
      "yeinot_bitan",
      "tiv_taam",
      "yochananof",
      "king_store",
    ]);
    expect(groups[0]!.clubs.map((c) => c.id)).toContain("ramilevy:isracard");
    expect(groups[0]!.name("he")).toBe("רמי לוי");
    expect(groups[0]!.name("ar")).toBe("Rami Levy");
    expect(chainsWithoutClubs(MOCK_CHAIN_CLUBS).map((c) => c.id)).toEqual([
      "shufersal",
      "victory",
      "hazi_hinam",
      "osher_ad",
      "machsanei_hashuk",
    ]);
    expect(clubsOfChain(CHAINS[0]!, MOCK_CHAIN_CLUBS)).toEqual([]);
  });

  it("keeps a chain the web does not list, after the ones it does", () => {
    const rows = [
      ...MOCK_CHAIN_CLUBS,
      {
        chain_id: "7299999999999",
        chain_name: "רשת חדשה",
        clubs: [{ id: "new:a", label: "א", kind: "club" as const }],
      },
      { chain_id: "7298888888888", chain_name: "בלי מועדונים", clubs: [] },
    ];
    const groups = chainsWithClubs(rows);
    expect(groups.at(-1)).toMatchObject({ key: "7299999999999" });
    expect(groups.some((g) => g.key === "7298888888888")).toBe(false);
  });
});

describe("a promo's club", () => {
  it("shows one club by its name", () => {
    expect(clubRuleText("המועדון החדש")).toBe("המועדון החדש");
    expect(clubRuleParts("המועדון החדש")).toEqual([{ text: "המועדון החדש", name: true }]);
  });

  it("reads | as or and & as and, with the brackets of the rule", () => {
    expect(clubRuleText("מועדון קרפור אשראי | מועדון אפליקציה")).toBe(
      "מועדון קרפור אשראי או מועדון אפליקציה",
    );
    expect(
      clubRuleText("(מועדון רמי לוי | מועדון לקוחות אשראי) & (ישראכרט מגנטי | תווי זיכוי מימוש)"),
    ).toBe("(מועדון רמי לוי או מועדון לקוחות אשראי) וגם (ישראכרט מגנטי או תווי זיכוי מימוש)");
    expect(clubRuleText("א | ב", "ar")).toBe("א أو ב");
    expect(clubRuleText("א & ב", "ar")).toBe("א و ב");
  });

  it("shows nothing for a club the API cannot name", () => {
    for (const rule of ["אחר", " אחר ", "", null, undefined]) {
      expect(clubRuleText(rule), String(rule)).toBeNull();
    }
    expect(promoAudience({ clubOnly: true, clubName: "אחר" })).toBe("מבצע מועדון");
    expect(promoAudience({ clubOnly: true, clubName: "המועדון החדש" })).toBe(
      "מבצע מועדון · המועדון החדש",
    );
    expect(promoAudience({ clubOnly: true, clubName: "א | ב" })).toBe("מבצע מועדון · א או ב");
  });

  it("marks the club names as Hebrew data runs on an Arabic screen, not the words between", () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    const { container } = render(
      <LocaleProvider>
        <ClubName rule="(מועדון רמי לוי | מועדון חברתי) & ישראכרט מגנטי" />
      </LocaleProvider>,
    );
    const runs = [...container.querySelectorAll('[lang="he"]')].map((el) => el.textContent);
    expect(runs).toEqual(["מועדון רמי לוי", "מועדון חברתי", "ישראכרט מגנטי"]);
    expect(container.textContent).toBe("(מועדון רמי לוי أو מועדון חברתי) و ישראכרט מגנטי");
  });

  it("renders nothing for an unknown club", () => {
    const { container } = render(
      <LocaleProvider>
        <ClubName rule="אחר" />
      </LocaleProvider>,
    );
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("אחר")).not.toBeInTheDocument();
  });
});
