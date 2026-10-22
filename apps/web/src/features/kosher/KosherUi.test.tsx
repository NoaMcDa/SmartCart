import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResultsContent } from "@/features/compare/ResultsView";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import { applyKosherToOptimize } from "@/mocks/kosher";
import { optimizeFixture } from "@/mocks/fixtures";
import { buildCompareInput, buildOptimizeInput } from "@/state/comparison";
import { readShopper } from "@/state/shopper";
import { fromServerProfile, toProfileUpdate } from "@/features/profile/profileApi";
import {
  DEFAULT_PROFILE,
  getProfile,
  resetProfileCache,
  updateProfile,
} from "@/features/profile/profileState";
import { KosherActiveNote } from "./KosherActiveNote";
import { KosherControls } from "./KosherControls";
import { KosherHitNote } from "./KosherHitNote";
import { KosherNote, KosherNoteItems } from "./KosherNote";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
});
afterEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  document.documentElement.lang = "he";
});

const ITEMS = [{ canonical_id: 1001, quantity: 1 }];

describe("the kosher setting (Profile and onboarding)", () => {
  it("sets the level, a named hechsher and the two switches, and every change reaches the requests", async () => {
    const user = userEvent.setup();
    render(<KosherControls />);
    expect(screen.queryByLabelText("השגחה מסוימת")).toBeNull(); // no level, nothing to specify
    expect(screen.queryByRole("switch", { name: /רק מוצרים שהכשרות/ })).toBeNull();
    // nothing set: the request is what it was before the filter existed
    expect(buildOptimizeInput(ITEMS, readShopper())).not.toHaveProperty("kosher");

    await user.click(screen.getByRole("radio", { name: "מהדרין" }));
    expect(getProfile().diet.kosherLevel).toBe("mehadrin");
    expect(buildCompareInput(ITEMS, readShopper())!.kosher).toEqual({
      level: "mehadrin",
      only_stated: false,
      passover: false,
    });

    await user.selectOptions(screen.getByLabelText("השגחה מסוימת"), 'בד"ץ העדה החרדית');
    expect(getProfile().diet.kosherLevel).toBe("badatz_eida");
    // a named hechsher shows as the general "בד"ץ" on the segmented control
    expect(screen.getByRole("radio", { name: 'בד"ץ' })).toBeChecked();

    await user.click(screen.getByRole("switch", { name: /רק מוצרים שהכשרות/ }));
    await user.click(screen.getByRole("switch", { name: "כשר לפסח" }));
    expect(buildOptimizeInput(ITEMS, readShopper())!.kosher).toEqual({
      level: "badatz_eida",
      only_stated: true,
      passover: true,
    });

    // choosing a general level again forgets the named one; "none" clears the level
    await user.selectOptions(screen.getByLabelText("השגחה מסוימת"), "");
    expect(getProfile().diet.kosherLevel).toBe("badatz");
    await user.click(screen.getByRole("radio", { name: "ללא" }));
    expect(getProfile().diet.kosherLevel).toBeNull();
    // Passover alone still filters
    expect(buildCompareInput(ITEMS, readShopper())!.kosher).toEqual({
      level: null,
      only_stated: true,
      passover: true,
    });
  });

  it("says what it reads: only words the name states, never a brand", () => {
    render(<KosherControls />);
    expect(screen.getByTestId("kosher-notice")).toHaveTextContent(
      "לא מניחים כשרות לפי יצרן או מותג",
    );
  });

  it("is offered in Arabic with the same options", async () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    render(
      <LocaleProvider>
        <KosherControls />
      </LocaleProvider>,
    );
    expect(screen.getByRole("radiogroup", { name: "مستوى الكاشير" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "مهدرين" })).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "بداتس" }));
    expect(screen.getByLabelText("إشراف محدد")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "كاشير للفصح" })).toBeInTheDocument();
  });
});

describe("the setting and the account", () => {
  it("the level and the two switches go to the profile and come back", () => {
    const local = {
      ...DEFAULT_PROFILE,
      diet: {
        ...DEFAULT_PROFILE.diet,
        kosherLevel: "badatz_beit_yosef" as const,
        kosherOnlyStated: true,
        kosherPassover: true,
      },
    };
    const update = toProfileUpdate(local);
    expect(update.kosher_level).toBe("badatz_beit_yosef");
    expect(update.diet_flags).toEqual(["kosher:only_stated", "kosher:passover"]);
    const back = fromServerProfile(
      { ...update, user_id: "u", exists: true } as Parameters<typeof fromServerProfile>[0],
      local,
    );
    expect(back.diet).toMatchObject({
      kosherLevel: "badatz_beit_yosef",
      kosherOnlyStated: true,
      kosherPassover: true,
    });
  });

  it("a level this app does not know comes back as no preference, never as a filter", () => {
    const back = fromServerProfile(
      {
        ...toProfileUpdate(DEFAULT_PROFILE),
        kosher_level: "super",
        user_id: "u",
        exists: true,
      } as Parameters<typeof fromServerProfile>[0],
      DEFAULT_PROFILE,
    );
    expect(back.diet!.kosherLevel).toBeNull();
  });

  it("the profile is mirrored to the shopper the requests read", () => {
    updateProfile((p) => ({
      diet: { ...p.diet, kosherLevel: "regular", kosherOnlyStated: true },
    }));
    expect(readShopper().kosher).toEqual({ level: "regular", onlyStated: true, passover: false });
  });
});

describe("the label on a line, a swap, a substitute and a search hit", () => {
  it("shows what the name states, or the unknown warning, with an icon and the text", () => {
    render(
      <>
        <KosherNote label={{ level: "meets", passover: null, stated: ["badatz", "badatz_eida"] }} />
        <KosherNote label={{ level: "unknown", passover: "unknown", stated: [] }} />
      </>,
    );
    const notes = screen.getAllByTestId("kosher-note");
    expect(notes.map((n) => n.getAttribute("data-kosher"))).toEqual([
      "level-meets",
      "level-unknown",
      "passover-unknown",
    ]);
    expect(notes[0]).toHaveTextContent('כשרות לפי שם המוצר: בד"ץ העדה החרדית');
    expect(notes[1]).toHaveTextContent("כשרות לא ידועה — בדקו על האריזה");
    for (const n of notes) expect(n.querySelector("svg")).not.toBeNull();
  });

  it("renders nothing without a label, and list items for a tag list", () => {
    const { container } = render(<KosherNote label={null} />);
    expect(container).toBeEmptyDOMElement();
    render(
      <ul>
        <KosherNoteItems label={{ level: "unknown", passover: null, stated: [] }} />
      </ul>,
    );
    expect(screen.getByRole("listitem")).toHaveTextContent("כשרות לא ידועה");
  });

  it("a search hit says whether anything can be offered", () => {
    render(
      <>
        <KosherHitNote label={{ status: "meets", meets: 1, unknown: 2, fails: 0 }} />
        <KosherHitNote label={{ status: "unknown", meets: 0, unknown: 2, fails: 0 }} />
        <KosherHitNote label={{ status: "none", meets: 0, unknown: 0, fails: 3 }} />
        <KosherHitNote label={null} />
      </>,
    );
    expect(screen.getAllByTestId("kosher-hit").map((n) => n.getAttribute("data-kosher"))).toEqual([
      "meets",
      "unknown",
      "none",
    ]);
  });

  it("the results say a filter is on, and each line, the missing list and the substitute card show what it did", async () => {
    const res = applyKosherToOptimize(optimizeFixture(), {
      level: "mehadrin",
      only_stated: false,
      passover: false,
    });
    const names = new Map<number, string>();
    render(<ResultsContent res={res} names={names} onReportGap={() => {}} />);
    // every line of the recommended plan carries a label; the one that states מהדרין says so
    const single = screen.getByTestId("basket-details");
    const notes = within(single).getAllByTestId("kosher-note");
    expect(notes.length).toBeGreaterThan(3);
    expect(notes.some((n) => n.textContent?.includes("מהדרין"))).toBe(true);
    expect(notes.some((n) => n.textContent?.includes("כשרות לא ידועה — בדקו על האריזה"))).toBe(
      true,
    );
    // a substitute line keeps its substitute tag AND its kosher label
    const subs = within(single).getAllByText(/תחליף/);
    expect(subs.length).toBeGreaterThan(0);
    const substituteLine = subs[0]!.closest("li")!;
    expect(within(substituteLine).getByTestId("kosher-note")).toBeInTheDocument();
  });

  it("a missing item says whether the store lacks it or the filter left it out", async () => {
    const res = applyKosherToOptimize(optimizeFixture(), {
      level: "regular",
      only_stated: true,
      passover: false,
    });
    const user = userEvent.setup();
    render(
      <ResultsContent res={res} names={new Map([[1002, "קוטג' 5%"]])} onReportGap={() => {}} />,
    );
    const single = screen.getByTestId("plan-single");
    await user.click(within(single).getByRole("button", { name: /פריט חסר|פריטים חסרים/ }));
    const list = within(single).getByRole("list", { name: "פריטים חסרים" });
    expect(list).toHaveTextContent("יש בסניף, אבל לא במוצר שעומד בסינון הכשרות שלך");
  });

  it("the note on the results names the filter and links to the setting", () => {
    render(<KosherActiveNote prefs={{ level: "mehadrin", onlyStated: false, passover: false }} />);
    const note = screen.getByTestId("kosher-active");
    expect(note).toHaveTextContent("סינון כשרות פעיל: מהדרין");
    expect(within(note).getByRole("link", { name: "שינוי בפרופיל" })).toHaveAttribute(
      "href",
      "/profile",
    );
    const { container } = render(<KosherActiveNote prefs={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
