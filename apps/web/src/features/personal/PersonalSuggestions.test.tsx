/**
 * The home screen's personalization (phase 3) on the real list builder, against the mock API:
 * "buy again" with its explanation, dismiss and undo; "my usual" one by one and all at once; the
 * "you usually take N" line of a row; the exact-brand offer with its undo; and nothing at all
 * without history or with learning off.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ListBuilder } from "@/features/list/ListBuilder";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import { server } from "@/mocks/node";
import { parseRow } from "@/mocks/parseRow";
import { getListState, listActions, resetListStoreForTests } from "@/state/list";
import { clearComparisonCache } from "@/state/comparison";
import { resetBetaEventsForTests } from "@/features/consent/betaEvents";
import { COTTAGE, MILK, doc, regularDoc, signal, trip } from "./fixtures";
import {
  PERSONAL_KEY,
  getPersonal,
  personalActions,
  resetPersonalStoreForTests,
} from "./personalState";
import type { PersonalDoc } from "./personalDoc";

const events = vi.hoisted(() => ({ calls: [] as Array<[string, Record<string, unknown>]> }));
vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: (name: string, props: Record<string, unknown>) => {
    events.calls.push([name, props]);
  },
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** 11:00 in Israel today, so "n days ago" is the same calendar day count in both time zones. */
function midday(): Date {
  const d = new Date();
  d.setUTCHours(9, 0, 0, 0);
  return d;
}

function seed(d: PersonalDoc) {
  window.localStorage.setItem(PERSONAL_KEY, JSON.stringify(d));
  resetPersonalStoreForTests();
}

beforeEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  resetListStoreForTests();
  resetPersonalStoreForTests();
  resetBetaEventsForTests();
  clearComparisonCache();
  events.calls.length = 0;
});

const renderBuilder = () => render(<ListBuilder />);

describe("nothing to say", () => {
  it("shows no suggestion card without history", async () => {
    renderBuilder();
    await screen.findByLabelText("הוסיפי פריטים לרשימה");
    expect(screen.queryByTestId("buy-again")).toBeNull();
    expect(screen.queryByTestId("usual")).toBeNull();
    expect(screen.queryByTestId("brand-offer")).toBeNull();
  });

  it("shows none while learning is off, and shows them again when it is on", async () => {
    seed({
      ...regularDoc(midday()),
      prefs: { learn: false, value_packs: false, updated_at: null },
    });
    renderBuilder();
    await screen.findByLabelText("הוסיפי פריטים לרשימה");
    expect(screen.queryByTestId("usual")).toBeNull();
    personalActions.setPrefs({ learn: true });
    expect(await screen.findByTestId("usual")).toBeInTheDocument();
  });
});

describe("buy again", () => {
  beforeEach(() => seed(regularDoc(midday())));

  it("offers what is due, with the person's own interval as the explanation", async () => {
    renderBuilder();
    const card = await screen.findByTestId("buy-again");
    expect(within(card).getByRole("heading", { name: "לקנות שוב?" })).toBeInTheDocument();
    const items = within(card).getAllByTestId("buy-again-item");
    expect(items).toHaveLength(1); // cottage: due. Milk was bought 3 days ago: not due
    expect(items[0]).toHaveTextContent("קוטג'");
    expect(within(items[0]!).getByTestId("buy-again-why")).toHaveTextContent(
      "לרוב את קונה כל ~10 ימים",
    );
    expect(within(items[0]!).getByTestId("buy-again-why")).toHaveTextContent("לפני 10 ימים");
  });

  it("adds the item to the list with its usual quantity, and the card goes with it", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await user.click(await screen.findByRole("button", { name: /הוסיפי קוטג.*לקנות שוב/ }));
    await waitFor(() => expect(getListState().items).toHaveLength(1));
    const row = getListState().items[0]!;
    expect(row.canonical?.canonical_id).toBe(COTTAGE.canonical_id);
    expect(row.quantity).toBe(1);
    expect(row.needsConfirmation).toBe(false);
    await waitFor(() => expect(screen.queryByTestId("buy-again")).toBeNull());
    expect(screen.getByTestId("personal-status")).toHaveTextContent("נוסף לרשימה");
    expect(events.calls).toContainEqual([
      "personalization",
      { kind: "buy_again", action: "shown" },
    ]);
    expect(events.calls).toContainEqual([
      "personalization",
      { kind: "buy_again", action: "accepted" },
    ]);
  });

  it("is dismissible: it hides, says what happens next, and the dismissal can be undone", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await user.click(await screen.findByRole("button", { name: /לא עכשיו: קוטג/ }));
    expect(screen.queryByTestId("buy-again")).toBeNull();
    expect(getPersonal().dismissals).toEqual([
      expect.objectContaining({ kind: "buy_again", key: String(COTTAGE.canonical_id) }),
    ]);
    const status = screen.getByTestId("personal-status");
    expect(status).toHaveTextContent("הסתרנו את קוטג'");
    await user.click(within(status).getByRole("button", { name: "ביטול" }));
    expect(getPersonal().dismissals).toEqual([]);
    expect(await screen.findByTestId("buy-again")).toBeInTheDocument();
    expect(events.calls.map(([, p]) => p.action)).toEqual(
      expect.arrayContaining(["dismissed", "undone"]),
    );
  });

  it("does not offer what is already on the list", async () => {
    listActions.add([parseRow("קוטג'")]);
    renderBuilder();
    await screen.findByLabelText("הוסיפי פריטים לרשימה");
    expect(screen.queryByTestId("buy-again")).toBeNull();
  });
});

describe("my usual", () => {
  beforeEach(() => seed(regularDoc(midday())));

  it("lists what is bought most with how often and the usual quantity", async () => {
    renderBuilder();
    const card = await screen.findByTestId("usual");
    const items = within(card).getAllByTestId("usual-item");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("חלב טרי 3%");
    expect(items[0]).toHaveTextContent("5 פעמים · בדרך כלל 2");
    expect(items[1]).toHaveTextContent("3 פעמים · בדרך כלל 1");
  });

  it("adds one item, then all the rest in one tap with their usual quantities", async () => {
    const user = userEvent.setup();
    renderBuilder();
    const card = await screen.findByTestId("usual");
    await user.click(within(card).getByRole("button", { name: /הוסיפי חלב טרי/ }));
    await waitFor(() => expect(getListState().items).toHaveLength(1));
    expect(getListState().items[0]).toMatchObject({ quantity: 2 });
    expect(screen.getByTestId("usual-add-all")).toHaveTextContent("הוסיפי את כל הרגילים (1)");
    await user.click(screen.getByTestId("usual-add-all"));
    await waitFor(() => expect(getListState().items).toHaveLength(2));
    expect(getListState().items.map((i) => i.quantity)).toEqual([2, 1]);
    expect(await screen.findByTestId("usual-all-on-list")).toHaveTextContent(
      "כל הרגילים שלך כבר ברשימה",
    );
    expect(events.calls).toContainEqual(["personalization", { kind: "usual", action: "accepted" }]);
  });

  it("the shown event is sent once however often the card re-renders", async () => {
    const user = userEvent.setup();
    renderBuilder();
    await screen.findByTestId("usual");
    await user.click(screen.getAllByRole("button", { name: /הוסיפי חלב טרי/ })[0]!);
    const shown = events.calls.filter(([, p]) => p.kind === "usual" && p.action === "shown");
    expect(shown).toHaveLength(1);
  });
});

describe('"you usually take N of these"', () => {
  beforeEach(() => seed(regularDoc(midday())));

  it("shows the usual quantity under the row and sets it in one tap when the row differs", async () => {
    const user = userEvent.setup();
    listActions.add([parseRow("חלב")]); // quantity 1; the person usually takes 2
    renderBuilder();
    const row = await screen.findByTestId("list-row");
    const hint = within(row).getByTestId("usual-quantity");
    expect(hint).toHaveTextContent("בדרך כלל את לוקחת 2");
    await user.click(
      within(hint).getByRole("button", { name: /קבעי את הכמות של חלב טרי 3%, 1 ליטר ל-2/ }),
    );
    await waitFor(() => expect(getListState().items[0]!.quantity).toBe(2));
    // At the usual quantity the line stays, without the button.
    expect(within(row).getByTestId("usual-quantity")).toHaveTextContent("בדרך כלל את לוקחת 2");
    expect(within(row).queryByRole("button", { name: /קבעי/ })).toBeNull();
    // Focus did not fall to the page.
    expect(document.body).not.toHaveFocus();
  });

  it("never changes the quantity by itself, and shows nothing for a product without history", async () => {
    listActions.add([parseRow("חלב"), parseRow("פסטה")]);
    renderBuilder();
    const rows = await screen.findAllByTestId("list-row");
    expect(getListState().items[0]!.quantity).toBe(1);
    expect(within(rows[1]!).queryByTestId("usual-quantity")).toBeNull();
  });

  it("is silent while learning is off", async () => {
    personalActions.setPrefs({ learn: false });
    listActions.add([parseRow("חלב")]);
    renderBuilder();
    const row = await screen.findByTestId("list-row");
    expect(within(row).queryByTestId("usual-quantity")).toBeNull();
  });
});

describe("the exact-brand offer", () => {
  const three = () =>
    seed(
      doc(
        {
          trips: [trip(2, [[MILK]], "finished", midday())],
          signals: [
            signal(40, "dairy.milk", "kept_brand", midday()),
            signal(20, "dairy.milk", "rejected_substitute", midday()),
            signal(2, "dairy.milk", "kept_brand", midday()),
          ],
        },
        [MILK],
      ),
    );

  it("asks, with the count and the category, and applies nothing by itself", async () => {
    three();
    renderBuilder();
    const offer = await screen.findByTestId("brand-offer");
    expect(offer).toHaveTextContent("בקטגוריה “חלב”");
    expect(offer).toHaveTextContent("3 פעמים");
    expect(offer).toHaveTextContent("זו רק הצעה");
    expect(getListState().flexDefaults).toEqual({});
  });

  it("applies the category default on a tap, and the undo puts back what was there", async () => {
    const user = userEvent.setup();
    three();
    listActions.setFlexDefault("dairy.milk", "close");
    renderBuilder();
    await user.click(await screen.findByTestId("brand-apply"));
    expect(getListState().flexDefaults["dairy.milk"]).toBe("exact");
    const status = screen.getByTestId("personal-status");
    expect(status).toHaveTextContent("היא עכשיו מותג מדויק");
    expect(screen.queryByTestId("brand-offer")).toBeNull();
    await user.click(within(status).getByRole("button", { name: "ביטול" }));
    expect(getListState().flexDefaults["dairy.milk"]).toBe("close");
    expect(screen.getByTestId("personal-status")).toHaveTextContent("חזרה למה שהייתה");
    // Undone counts as an answer: not offered again until the signals come back.
    expect(getPersonal().dismissals).toEqual([
      expect.objectContaining({ kind: "brand_default", key: "dairy.milk" }),
    ]);
    expect(screen.queryByTestId("brand-offer")).toBeNull();
  });

  it("undo of a category that had no default removes the default again", async () => {
    const user = userEvent.setup();
    three();
    renderBuilder();
    await user.click(await screen.findByTestId("brand-apply"));
    await user.click(
      within(screen.getByTestId("personal-status")).getByRole("button", { name: "ביטול" }),
    );
    expect(getListState().flexDefaults).toEqual({});
  });

  it("does not touch the rows already on the list", async () => {
    const user = userEvent.setup();
    three();
    listActions.add([parseRow("חלב")]);
    renderBuilder();
    await user.click(await screen.findByTestId("brand-apply"));
    expect(getListState().items[0]!.flexLevel).toBe("any_brand");
  });

  it("a dismissal hides the offer and is not asked again until three new signals", async () => {
    const user = userEvent.setup();
    three();
    renderBuilder();
    await user.click(await screen.findByTestId("brand-dismiss"));
    expect(screen.queryByTestId("brand-offer")).toBeNull();
    expect(getListState().flexDefaults).toEqual({});
    expect(screen.getByTestId("personal-status")).toHaveTextContent("לא נציע את זה שוב");
    personalActions.recordSignal("dairy.milk", "kept_brand");
    personalActions.recordSignal("dairy.milk", "kept_brand");
    await waitFor(() => expect(getPersonal().signals).toHaveLength(5));
    expect(screen.queryByTestId("brand-offer")).toBeNull();
    personalActions.recordSignal("dairy.milk", "kept_brand");
    expect(await screen.findByTestId("brand-offer")).toBeInTheDocument();
  });
});

describe("Arabic", () => {
  it("shows the cards and the explanation in Arabic with the Hebrew product names as data", async () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    seed(regularDoc(midday()));
    render(
      <LocaleProvider>
        <ListBuilder />
      </LocaleProvider>,
    );
    const card = await screen.findByTestId("buy-again");
    expect(within(card).getByRole("heading")).toHaveTextContent("هل تشترين مجددًا؟");
    expect(within(card).getByTestId("buy-again-why")).toHaveTextContent("عادةً تشترين كل ~10 أيام");
    expect(
      within(await screen.findByTestId("usual")).getAllByTestId("usual-item")[0],
    ).toHaveTextContent("عادةً 2");
  });
});
