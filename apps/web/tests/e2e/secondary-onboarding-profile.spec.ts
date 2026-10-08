import { expect, test, type Page } from "@playwright/test";
import { KEYS, mockApi, noHorizontalScroll } from "./secondary.helpers";

const readProfile = (page: Page) =>
  page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null"), KEYS.profile);

test.describe("onboarding, phone at 390 px", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
    geolocation: { latitude: 32.0853123, longitude: 34.7818123 },
    permissions: ["geolocation"],
  });

  test("three steps, each with a why-we-ask, end with the answers saved and the location rounded", async ({
    page,
  }) => {
    await mockApi(page);
    await page.goto("/onboarding");
    await expect(page.getByRole("heading", { level: 1, name: "ברוכים הבאים" })).toBeVisible();

    // Step 1: location. The device is asked only after the click, and the result is rounded.
    await expect(page.getByTestId("step-count")).toContainText("שלב 1 מתוך 3");
    await expect(page.getByLabel("למה אנחנו שואלים")).toBeVisible();
    expect(await readProfile(page)).toBeNull();
    await page.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }).click();
    await expect(page.getByTestId("location-summary")).toContainText("מעוגל לשכונה");
    await page.getByRole("slider", { name: "רדיוס חיפוש" }).fill("9");
    await noHorizontalScroll(page);
    const stored = await readProfile(page);
    expect(stored.location).toMatchObject({ lat: 32.085, lon: 34.782, source: "device" });
    expect(stored.radiusKm).toBe(9);
    // Nothing finer than 3 decimals anywhere in storage.
    const raw = await page.evaluate((k) => localStorage.getItem(k)!, KEYS.profile);
    expect(raw).not.toContain("32.0853");
    expect(raw).not.toContain("34.7818");
    await page.getByTestId("onboarding-next").click();

    // Step 2: my store and clubs.
    await expect(page.getByTestId("step-count")).toContainText("שלב 2 מתוך 3");
    await expect(page.getByLabel("למה אנחנו שואלים")).toContainText("חנות בסיס");
    await page.getByRole("button", { name: "הסופר שלי: שופרסל" }).click();
    await page.getByRole("button", { name: "הסופר שלי: רמי לוי" }).click();
    await expect(page.getByRole("button", { name: "הסופר שלי: שופרסל" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await expect(page.getByRole("button", { name: "הסופר שלי: רמי לוי" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await page.getByRole("button", { name: "מועדון רמי לוי" }).click();
    // The selected card shows a check icon as well as the colored state.
    await expect(
      page.getByRole("button", { name: "הסופר שלי: רמי לוי" }).locator('svg[data-icon="check"]'),
    ).toBeVisible();
    await noHorizontalScroll(page);
    await page.getByTestId("onboarding-next").click();

    // Step 3: travel and the extra stop.
    await expect(page.getByTestId("step-count")).toContainText("שלב 3 מתוך 3");
    await page.getByRole("radio", { name: "הליכה או תחבורה" }).click();
    await page.getByRole("slider", { name: "כמה שווה לך עצירה נוספת?" }).fill("30");
    await expect(page.locator("output").filter({ hasText: "₪" })).toContainText("30");
    await noHorizontalScroll(page);
    await page.getByTestId("onboarding-next").click();
    await expect(page).toHaveURL(/\/$/);

    const done = await readProfile(page);
    expect(done).toMatchObject({
      onboardingDone: true,
      radiusKm: 9,
      homeChainId: "rami_levy",
      clubs: ["רמי לוי"],
      travelMode: "walk_transit",
      extraStopValue: 30,
    });

    // The answers are readable from Profile.
    await page.goto("/profile");
    await expect(page.getByRole("slider", { name: "רדיוס חיפוש" })).toHaveValue("9");
    await expect(page.getByRole("button", { name: "הסופר שלי: רמי לוי" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByRole("radio", { name: "הליכה או תחבורה" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});

test.describe("onboarding, location declined", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("declining falls back to city and neighborhood; skipping all steps leaves the defaults", async ({
    page,
  }) => {
    await mockApi(page);
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "geolocation", {
        configurable: true,
        value: {
          getCurrentPosition: (
            _ok: unknown,
            fail: (e: { code: number; message: string }) => void,
          ) => fail({ code: 1, message: "denied" }),
        },
      });
    });
    await page.goto("/onboarding");
    await page.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }).click();
    await expect(page.getByText(/לא קיבלנו הרשאת מיקום/)).toBeVisible();
    await page.getByLabel("עיר").fill("מודיעין");
    await page.getByLabel("שכונה (לא חובה)").fill("בויאר");
    await page.getByRole("button", { name: "שמירת העיר" }).click();
    await expect(page.getByTestId("location-summary")).toContainText("מודיעין-מכבים-רעות, בויאר");
    expect((await readProfile(page)).location).toMatchObject({ lat: 31.897, lon: 35.01 });

    // Skip the other two steps.
    await page.getByTestId("onboarding-skip").click();
    await page.getByTestId("onboarding-skip").click();
    await expect(page.getByTestId("step-count")).toContainText("שלב 3 מתוך 3");
    await page.getByTestId("onboarding-skip").click();
    await expect(page).toHaveURL(/\/$/);
    const p = await readProfile(page);
    expect(p).toMatchObject({
      onboardingDone: true,
      homeChainId: null,
      homeStoreId: null,
      travelMode: "car",
      extraStopValue: 25,
      radiusKm: 5,
    });
    // A hint that a baseline is needed shows up later, in Profile.
    await page.goto("/profile");
    await expect(page.getByTestId("baseline-banner")).toBeVisible();
  });

  test("skipping everything without a location leaves no location stored", async ({ page }) => {
    await page.goto("/onboarding");
    for (let i = 0; i < 3; i++) await page.getByTestId("onboarding-skip").click();
    await expect(page).toHaveURL(/\/$/);
    expect((await readProfile(page)).location).toBeNull();
  });
});

test.describe("profile", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("edits persist across a reload, the theme section stays, delete my data clears everything", async ({
    page,
  }) => {
    await mockApi(page);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { level: 1, name: "פרופיל" })).toBeVisible();
    await expect(page.getByRole("radiogroup", { name: "ערכת צבעים" })).toBeVisible();

    await page.getByRole("button", { name: "הסופר שלי: ויקטורי" }).click();
    await page.getByRole("button", { name: "מועדון ויקטורי" }).click();
    await page.getByRole("slider", { name: "כמה שווה לך עצירה נוספת?" }).fill("40");
    await page.getByRole("radio", { name: 'בד"צ' }).click();
    await page.getByRole("switch", { name: "טבעוני" }).click();
    await page.getByRole("button", { name: "אגוזים" }).click();
    await page.getByLabel("מוצרי חלב וביצים").selectOption("close");
    await page.getByRole("slider", { name: "רדיוס חיפוש" }).fill("12");
    await expect(page.getByText("לא מאומת").first()).toBeVisible();
    await noHorizontalScroll(page);

    await page.reload();
    await expect(page.getByRole("button", { name: "הסופר שלי: ויקטורי" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByRole("button", { name: "מועדון ויקטורי" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByRole("slider", { name: "כמה שווה לך עצירה נוספת?" })).toHaveValue("40");
    await expect(page.getByRole("slider", { name: "רדיוס חיפוש" })).toHaveValue("12");
    await expect(page.getByRole("radio", { name: 'בד"צ' })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("switch", { name: "טבעוני" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByRole("button", { name: "אגוזים" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByLabel("מוצרי חלב וביצים")).toHaveValue("close");
    expect(await readProfile(page)).toMatchObject({
      homeChainId: "victory",
      extraStopValue: 40,
      radiusKm: 12,
      diet: { vegan: true, kosherLevel: "badatz", allergens: ["tree_nuts"] },
    });
    // The next comparison reads the same answers from the core screens' shopper context and list.
    const core = await page.evaluate((keys) => {
      return {
        shopper: JSON.parse(localStorage.getItem(keys.shopper) ?? "null"),
        list: JSON.parse(localStorage.getItem(keys.list) ?? "null"),
      };
    }, KEYS);
    expect(core.shopper).toMatchObject({
      radius_m: 12000,
      extra_stop_value: "40",
      clubs: ["ויקטורי"],
      // Picking the chain resolved its nearest store through GET /stores/nearest (ויקטורי, 105).
      home_store_id: 105,
    });
    expect(core.list.flexDefaults).toEqual({ dairy: "close" });

    // Reset the flexibility defaults.
    await page.getByRole("button", { name: "איפוס לברירות המחדל החכמות" }).click();
    await expect(page.getByLabel("מוצרי חלב וביצים")).toHaveValue("any_brand");

    // Delete my data: confirmation first, then everything is gone.
    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    await expect(page.getByRole("dialog", { name: "למחוק את כל הנתונים שלי?" })).toBeVisible();
    await page.getByRole("button", { name: "ביטול" }).click();
    expect((await readProfile(page)).homeChainId).toBe("victory");
    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByTestId("delete-done")).toBeVisible();
    const leftovers = await page.evaluate(
      (keys) => keys.filter((k) => localStorage.getItem(k) !== null),
      Object.values(KEYS),
    );
    expect(leftovers).toEqual([]);
    await page.reload();
    await expect(page.getByTestId("baseline-banner")).toBeVisible();
  });

  test("the privacy policy is linked from onboarding and Profile and states the no-sale commitment", async ({
    page,
  }) => {
    await page.goto("/profile");
    await page.getByRole("link", { name: "למדיניות הפרטיות המלאה" }).click();
    await expect(page).toHaveURL(/\/privacy$/);
    await expect(page.getByRole("heading", { level: 1, name: "מדיניות פרטיות" })).toBeVisible();
    await expect(page.getByText("לא מוכרים ולא מעבירים מידע על משתמשים")).toBeVisible();
    await page.goto("/onboarding");
    await expect(page.getByRole("link", { name: "מדיניות הפרטיות" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});

test.describe("dark theme and 1280 px", () => {
  test("onboarding and profile render in dark mode on desktop without horizontal scroll", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.setViewportSize({ width: 1280, height: 900 });
    for (const path of ["/onboarding", "/profile", "/privacy"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      expect(bg).toBe("rgb(20, 20, 19)");
      await noHorizontalScroll(page);
      const width = await page.evaluate(
        () => document.querySelector("main")!.getBoundingClientRect().width,
      );
      expect(width).toBeLessThanOrEqual(1200);
    }
  });
});

test.describe("home store from the chain", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("picking a chain in onboarding resolves its nearest store, and the results compare against it", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await page.goto("/onboarding");
    await page.getByTestId("onboarding-next").click(); // step 1 is skippable
    await expect(page.getByTestId("step-count")).toContainText("שלב 2 מתוך 3");
    await page.getByRole("button", { name: "הסופר שלי: יוחננוף" }).click();

    // The chain became a store through GET /stores/nearest, with the chain's API id.
    await expect
      .poll(() => calls.find((c) => c.path === "/stores/nearest")?.search ?? "")
      .toContain("chain_id=7290803800003");
    await expect.poll(async () => (await readProfile(page)).homeStoreId).toBe(104);
    const shopper = await page.evaluate((k) => JSON.parse(localStorage.getItem(k)!), KEYS.shopper);
    expect(shopper.home_store_id).toBe(104);
    await page.getByTestId("onboarding-next").click();
    await page.getByTestId("onboarding-next").click();

    // The list builder and the results use it: "versus <the home store>, your store".
    await page.goto("/");
    await page.getByLabel("הוסיפי פריטים לרשימה").fill("חלב, קוטג'");
    await page.getByLabel("הוסיפי פריטים לרשימה").press("Enter");
    await page.getByTestId("list-row").first().waitFor();
    await page.getByRole("link", { name: "השווי" }).click();
    await page.getByTestId("plan-single").waitFor();
    await expect(page.getByTestId("plan-single")).toContainText("לעומת יוחננוף");
    // The first results page after onboarding already has the net saving: a concrete baseline
    // store, no "what is your store?" prompt, and the app never needed /split to adopt one
    // (docs/fullstack.md gap 1, closed in #101).
    await expect(page.getByTestId("no-home-store")).toHaveCount(0);
    await expect(page.getByTestId("plan-single-saving")).toContainText(/חוסך\s*₪/);
    expect(page.url()).not.toContain("/split");
    const optimize = calls.filter((c) => c.path === "/optimize").at(-1);
    expect(optimize?.body).toMatchObject({ home_store_id: 104 });
    expect(
      calls
        .filter((c) => c.path === "/optimize")
        .every((c) => (c.body as { home_store_id?: number }).home_store_id === 104),
    ).toBe(true);
  });

  test("a chain without a store in the API stays selected, with no saving shown", async ({
    page,
  }) => {
    const calls = await mockApi(page);
    await page.goto("/profile");
    await page.getByRole("button", { name: "הסופר שלי: קינג סטור" }).click();
    await expect(page.getByRole("button", { name: "הסופר שלי: קינג סטור" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect.poll(() => calls.some((c) => c.path === "/stores/nearest")).toBe(true);
    expect(await readProfile(page)).toMatchObject({ homeChainId: "king_store", homeStoreId: null });
  });
});
