import { expect, test, type Page } from "@playwright/test";
import { regularDoc, signal, doc, trip, MILK, EGGS } from "../../src/features/personal/fixtures";
import { mockApi, seedProfile } from "./core-helpers";
import { noHorizontalScroll, seed } from "./secondary.helpers";

/**
 * Personalization (phase 3): "my usual", "buy again", the exact-brand offer, value packs, and what
 * Profile, the export and "delete my data" do with it. Everything runs on the device against the
 * mock API; the signed-in account sync is covered by the unit tests (`PersonalSync.test.tsx`).
 * The browser clock is frozen at noon in Israel on 8 October 2026 so "n days ago" is exact.
 */

const BASE = new Date("2026-10-08T09:00:00Z");
const KEY = "sc-personal-v1";

async function freeze(page: Page) {
  await page.clock.setFixedTime(BASE);
}

async function start(page: Page, personal: unknown = regularDoc(BASE)) {
  await freeze(page);
  const calls = await mockApi(page);
  await seedProfile(page);
  await seed(page, { [KEY]: personal });
  return calls;
}

const stored = (page: Page) =>
  page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null"), KEY);

const quantityOf = (row: import("@playwright/test").Locator) => row.locator("output");

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`personalization at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("buy again explains itself from the person's own history and adds with the usual quantity", async ({
      page,
    }) => {
      await start(page);
      await page.goto("/");
      const card = page.getByTestId("buy-again");
      await expect(card.getByRole("heading", { name: "לקנות שוב?" })).toBeVisible();
      await expect(card.getByTestId("buy-again-item")).toHaveCount(1);
      await expect(card.getByTestId("buy-again-why")).toContainText("לרוב את קונה כל ~10 ימים");
      await noHorizontalScroll(page);

      await page.getByRole("button", { name: /הוסיפי קוטג.*לקנות שוב/ }).click();
      await expect(page.getByTestId("list-row")).toHaveCount(1);
      await expect(page.getByTestId("list-row")).toContainText("קוטג'");
      await expect(page.getByTestId("buy-again")).toHaveCount(0);
      await expect(page.getByTestId("personal-status")).toContainText("נוסף לרשימה");
    });

    test("buy again is dismissible: remembered across a reload, and undone from the status line", async ({
      page,
    }) => {
      await start(page);
      await page.goto("/");
      const card = page.getByTestId("buy-again");
      await card.getByRole("button", { name: /לא עכשיו: קוטג/ }).click();
      await expect(card).toHaveCount(0);
      await expect(page.getByTestId("personal-status")).toContainText("הסתרנו את קוטג'");

      await page.getByTestId("personal-status").getByRole("button", { name: "ביטול" }).click();
      await expect(page.getByTestId("buy-again")).toBeVisible();
      expect((await stored(page)).dismissals).toEqual([]);

      await page
        .getByTestId("buy-again")
        .getByRole("button", { name: /לא עכשיו: קוטג/ })
        .click();
      await page.reload();
      await page.getByLabel("הוסיפי פריטים לרשימה").waitFor();
      await expect(page.getByTestId("buy-again")).toHaveCount(0);
      expect((await stored(page)).dismissals).toHaveLength(1);
    });

    test("my usual: add one, then the rest, with the usual quantity and the 'you usually take' line", async ({
      page,
    }) => {
      await start(page);
      await page.goto("/");
      const usual = page.getByTestId("usual");
      await expect(usual.getByTestId("usual-item")).toHaveCount(2);
      await expect(usual.getByTestId("usual-item").first()).toContainText("5 פעמים · בדרך כלל 2");

      await usual.getByRole("button", { name: /הוסיפי חלב טרי/ }).click();
      const milk = page.getByTestId("list-row").filter({ hasText: "חלב טרי" });
      await expect(milk).toHaveCount(1);
      await expect(quantityOf(milk)).toHaveText("2");
      await expect(milk.getByTestId("usual-quantity")).toContainText("בדרך כלל את לוקחת 2");
      await expect(milk.getByRole("button", { name: /קבעי/ })).toHaveCount(0);

      await page.getByTestId("usual-add-all").click();
      await expect(page.getByTestId("list-row")).toHaveCount(2);
      await expect(page.getByTestId("usual-all-on-list")).toBeVisible();

      // Lower the milk, then one tap puts the usual quantity back.
      await milk.getByRole("button", { name: /^הוסיפי כמות של/ }).click();
      await expect(quantityOf(milk)).toHaveText("3");
      await milk.getByRole("button", { name: /^הפחיתי כמות של/ }).click();
      await milk.getByRole("button", { name: /^הפחיתי כמות של/ }).click();
      await expect(quantityOf(milk)).toHaveText("1");
      await milk.getByRole("button", { name: /קבעי את הכמות של חלב טרי.*ל-2/ }).click();
      await expect(quantityOf(milk)).toHaveText("2");
      await noHorizontalScroll(page);
    });

    test("the exact-brand offer is only an offer: applied on a tap, shown in Profile, undone", async ({
      page,
    }) => {
      const signals = [
        signal(40, "dairy.milk", "kept_brand", BASE),
        signal(20, "dairy.milk", "rejected_substitute", BASE),
        signal(2, "dairy.milk", "kept_brand", BASE),
      ];
      await start(page, doc({ trips: [trip(2, [[MILK]], "finished", BASE)], signals }, [MILK]));
      await page.goto("/");
      const offer = page.getByTestId("brand-offer");
      await expect(offer).toContainText("בקטגוריה “חלב”");
      await expect(offer).toContainText("3 פעמים");
      // Nothing was applied by showing it.
      expect(
        (await page.evaluate(() => localStorage.getItem("sc-list-v1")))?.includes("exact"),
      ).not.toBe(true);
      await page.getByTestId("brand-apply").click();
      await expect(offer).toHaveCount(0);
      await expect(page.getByTestId("personal-status")).toContainText("עכשיו מותג מדויק");

      await page.goto("/profile");
      const row = page
        .getByTestId("flex-defaults")
        .getByRole("listitem")
        .filter({ hasText: "חלב ומשקאות חלב" });
      await expect(row.getByRole("combobox")).toHaveValue("exact");

      await page.goto("/");
      await expect(page.getByTestId("brand-offer")).toHaveCount(0); // already exact
    });

    test("the undo of the offer puts the old default back and does not ask again", async ({
      page,
    }) => {
      const signals = [
        signal(40, "dairy.milk", "kept_brand", BASE),
        signal(20, "dairy.milk", "rejected_substitute", BASE),
        signal(2, "dairy.milk", "kept_brand", BASE),
      ];
      await start(page, doc({ trips: [trip(2, [[MILK]], "finished", BASE)], signals }, [MILK]));
      await page.goto("/");
      await page.getByTestId("brand-apply").click();
      await page.getByTestId("personal-status").getByRole("button", { name: "ביטול" }).click();
      await expect(page.getByTestId("personal-status")).toContainText("חזרה למה שהייתה");
      await expect(page.getByTestId("brand-offer")).toHaveCount(0);
      await page.goto("/profile");
      // The saved default is gone again: the category is back to the department's own level.
      await expect(page.getByTestId("flex-defaults")).not.toContainText("חלב ומשקאות חלב");
    });
  });
}

test.describe("value packs", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("off by default; the Profile switch turns it on and the list builder suggests the larger pack", async ({
    page,
  }) => {
    await start(page, doc({}, []));
    await page.goto("/profile");
    const packs = page.getByRole("switch", { name: "להעדיף אריזות גדולות (משפחה גדולה)" });
    await expect(packs).toHaveAttribute("aria-checked", "false");

    await page.goto("/");
    await page.getByLabel("הוסיפי פריטים לרשימה").fill("ביצים");
    await page.getByLabel("הוסיפי פריטים לרשימה").press("Enter");
    await page.getByTestId("list-row").waitFor();
    await expect(page.getByTestId("value-packs")).toHaveCount(0);

    await page.goto("/profile");
    await page.getByRole("switch", { name: "להעדיף אריזות גדולות (משפחה גדולה)" }).click();
    expect((await stored(page)).prefs.value_packs).toBe(true);

    await page.goto("/");
    const card = page.getByTestId("value-packs");
    await expect(card).toBeVisible();
    const pack = card.getByTestId("value-pack");
    await expect(pack).toContainText("אריזה גדולה: 30");
    await expect(pack).toContainText("המחיר הקובע הוא בקופה");
    expect(await pack.locator("time[datetime]").count()).toBeGreaterThanOrEqual(2);
    await noHorizontalScroll(page);

    const row = page.getByTestId("list-row");
    await expect(quantityOf(row)).toHaveText("1");
    await pack.getByRole("button", { name: /עברי לאריזה הגדולה/ }).click();
    await expect(quantityOf(row)).toHaveText("2.5");
    await expect(page.getByTestId("value-pack")).toHaveCount(0);
    await page.getByTestId("value-pack-status").getByRole("button", { name: "ביטול" }).click();
    await expect(quantityOf(row)).toHaveText("1");
    await expect(page.getByTestId("value-pack")).toBeVisible();
  });

  test("no thanks hides the pack for a month and survives a reload", async ({ page }) => {
    await start(
      page,
      doc({ prefs: { learn: true, value_packs: true, updated_at: BASE.toISOString() } }, [EGGS]),
    );
    await page.goto("/");
    await page.getByLabel("הוסיפי פריטים לרשימה").fill("ביצים");
    await page.getByLabel("הוסיפי פריטים לרשימה").press("Enter");
    await page.getByRole("button", { name: /לא, תודה: ביצים/ }).click();
    await expect(page.getByTestId("value-packs")).toHaveCount(0);
    await page.reload();
    await page.getByTestId("list-row").waitFor();
    await expect(page.getByTestId("value-packs")).toHaveCount(0);
  });
});

test.describe("privacy and control", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("anonymous: nothing about habits ever reaches the API", async ({ page }) => {
    const calls = await start(page);
    await page.goto("/");
    await page.getByRole("button", { name: /הוסיפי קוטג.*לקנות שוב/ }).click();
    await page.getByTestId("usual-add-all").click();
    await page.goto("/profile");
    await page.getByRole("switch", { name: "להעדיף אריזות גדולות (משפחה גדולה)" }).click();
    await page.getByTestId("personal-clear").click();
    await page.waitForTimeout(1200);
    expect(calls.filter((c) => c.path.startsWith("/me/"))).toEqual([]);
    expect(JSON.stringify(calls)).not.toContain("personal");
  });

  test("learning off hides every suggestion and stops recording; clearing empties what was kept", async ({
    page,
  }) => {
    await start(page);
    await page.goto("/profile");
    const section = page.getByRole("region", { name: "התאמה אישית" });
    await expect(section.getByTestId("personal-stats")).toContainText("קניות ורשימות שנשמרו: 7");
    await section.getByRole("switch", { name: "ללמוד מהקניות שלי" }).click();
    await expect(section.getByTestId("learn-off-note")).toBeVisible();

    await page.goto("/");
    await page.getByLabel("הוסיפי פריטים לרשימה").waitFor();
    await expect(page.getByTestId("buy-again")).toHaveCount(0);
    await expect(page.getByTestId("usual")).toHaveCount(0);

    await page.goto("/profile");
    await page.getByTestId("personal-clear").click();
    await expect(page.getByTestId("personal-stats")).toContainText("קניות ורשימות שנשמרו: 0");
    await expect(page.getByTestId("personal-clear")).toBeDisabled();
    const after = await stored(page);
    expect(after.trips).toEqual([]);
    expect(after.prefs.learn).toBe(false); // the preference stays
  });

  test("the export has the habits, and delete my data removes them", async ({ page }) => {
    await start(page);
    await page.goto("/profile");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "ייצוא הנתונים שלי" }).click();
    const file = await download;
    const path = await file.path();
    const exported = JSON.parse(await (await import("node:fs/promises")).readFile(path, "utf8"));
    expect(exported.personalization.trips).toHaveLength(7);
    expect(exported.personalization.refs.length).toBeGreaterThan(0);
    expect(exported.personalization.prefs).toMatchObject({ learn: true, value_packs: false });

    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByTestId("delete-done")).toBeVisible();
    expect(await page.evaluate((k) => localStorage.getItem(k), KEY)).toBeNull();
    await page.goto("/");
    await page.getByLabel("הוסיפי פריטים לרשימה").waitFor();
    await expect(page.getByTestId("usual")).toHaveCount(0);
  });

  test("the privacy page has the paragraph, marked as awaiting legal review", async ({ page }) => {
    await mockApi(page);
    await page.goto("/privacy");
    const section = page.locator('section[aria-labelledby="p-personal"]');
    await expect(section.getByRole("heading", { level: 2 })).toContainText("התאמה אישית");
    await expect(section).toContainText("אין בזה מחירים, חנויות, מיקום או טקסט חופשי");
    await expect(section.getByTestId("personal-privacy-legal")).toContainText(
      "ממתין לבדיקה משפטית",
    );
    await expect(page.getByTestId("privacy-draft")).toContainText("טיוטה, ממתינה לבדיקה משפטית");
  });
});

test.describe("195 px (200% zoom)", () => {
  test.use({ viewport: { width: 195, height: 700 } });

  test("every card and the Profile section fit without horizontal scrolling", async ({ page }) => {
    const signals = [
      signal(40, "dairy.milk", "kept_brand", BASE),
      signal(20, "dairy.milk", "rejected_substitute", BASE),
      signal(2, "dairy.milk", "kept_brand", BASE),
    ];
    const history = regularDoc(BASE);
    await start(page, {
      ...history,
      signals,
      prefs: { learn: true, value_packs: true, updated_at: BASE.toISOString() },
      refs: [...history.refs, EGGS],
    });
    await page.goto("/");
    await expect(page.getByTestId("buy-again")).toBeVisible();
    await expect(page.getByTestId("usual")).toBeVisible();
    await expect(page.getByTestId("brand-offer")).toBeVisible();
    await noHorizontalScroll(page);
    await page.getByLabel("הוסיפי פריטים לרשימה").fill("ביצים");
    await page.getByLabel("הוסיפי פריטים לרשימה").press("Enter");
    await expect(page.getByTestId("value-pack")).toBeVisible();
    await noHorizontalScroll(page);
    await page.goto("/profile");
    await expect(page.getByTestId("personal-stats")).toBeVisible();
    await noHorizontalScroll(page);
  });
});
