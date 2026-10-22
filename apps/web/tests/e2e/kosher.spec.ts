import { expect, test, type Page } from "@playwright/test";
import { mockApi, pasteList, WEEKLY_TEXT } from "./core-helpers";

/**
 * The kosher filter end to end against the mock API (src/mocks/kosher.ts mirrors what the real
 * API answers): the Profile setting, the request it makes, the labels on the lines, the note on
 * the results, what a filter that leaves nothing says, and the same in Arabic.
 */

const UNKNOWN = "כשרות לא ידועה — בדקו על האריזה";

/**
 * The shopper profile the onboarding would write (the same as `seedProfile` in core-helpers), stored
 * once: that helper stores it again on every navigation, which would undo the setting the test just
 * made.
 */
async function seedProfile(page: Page) {
  await page.addInitScript(() => {
    if (localStorage.getItem("sc-profile-v1") !== null) return;
    localStorage.setItem(
      "sc-profile-v1",
      JSON.stringify({
        neighborhood_lat: 31.898,
        neighborhood_lon: 35.01,
        city_label: "מודיעין",
        radius_m: 5000,
        home_store_id: 103,
        travel_mode: "car",
        extra_stop_value: 25,
      }),
    );
  });
}

async function openResults(page: Page) {
  await page.goto("/");
  await pasteList(page, WEEKLY_TEXT);
  await page.getByRole("link", { name: "השווי" }).click();
  await page.getByTestId("plan-single").waitFor();
}

test("a level set in Profile filters the next comparison and every line says what its name states", async ({
  page,
}) => {
  const calls = await mockApi(page);
  await seedProfile(page);
  await page.goto("/profile");
  const diet = page.getByRole("region", { name: "כשרות ותזונה" });
  await expect(diet.getByTestId("kosher-notice")).toContainText("לא מניחים כשרות לפי יצרן או מותג");
  await diet.getByRole("radio", { name: "מהדרין" }).click();
  await expect(diet.getByRole("radio", { name: "מהדרין" })).toHaveAttribute("aria-checked", "true");

  await openResults(page);
  await expect(page.getByTestId("kosher-active")).toContainText("סינון כשרות פעיל: מהדרין");
  const optimize = calls.filter((c) => c.path === "/optimize").at(-1)!;
  expect(optimize.body).toMatchObject({
    kosher: { level: "mehadrin", only_stated: false, passover: false },
  });

  await page.getByTestId("basket-details").locator("summary").click();
  const notes = page.getByTestId("basket-details").getByTestId("kosher-note");
  // Rami Levy's milk states מהדרין; the lines that state nothing are labelled, not hidden
  await expect(notes.filter({ hasText: "כשרות לפי שם המוצר: מהדרין" })).toHaveCount(1);
  expect(await notes.filter({ hasText: UNKNOWN }).count()).toBeGreaterThan(3);
  // every substitute keeps its own label next to the kosher one
  const substitute = page
    .getByTestId("basket-details")
    .getByRole("link", { name: /^תחליף:/ })
    .first();
  await expect(substitute.locator("xpath=ancestor::li[1]").getByTestId("kosher-note")).toHaveCount(
    1,
  );
});

test("only items whose name states it: a store with nothing left is not listed, and a missing item says why", async ({
  page,
}) => {
  const calls = await mockApi(page);
  await seedProfile(page);
  await page.goto("/profile");
  const diet = page.getByRole("region", { name: "כשרות ותזונה" });
  await diet.getByRole("radio", { name: "כשר" }).click();
  await diet.getByRole("switch", { name: /רק מוצרים שהכשרות/ }).click();

  await openResults(page);
  expect(calls.filter((c) => c.path === "/optimize").at(-1)!.body).toMatchObject({
    kosher: { level: "regular", only_stated: true },
  });
  await expect(page.getByTestId("kosher-active")).toContainText(
    "מוצגים רק מוצרים שהכשרות שלהם מצוינת בשם",
  );
  const single = page.getByTestId("plan-single");
  await single.getByRole("button", { name: /פריט חסר|פריטים חסרים/ }).click();
  await expect(single.getByRole("list", { name: "פריטים חסרים" })).toContainText(
    "יש בסניף, אבל לא במוצר שעומד בסינון הכשרות שלך",
  );
  // no line states nothing: the warning has nothing to label
  await page.getByTestId("basket-details").locator("summary").click();
  await expect(
    page.getByTestId("basket-details").getByTestId("kosher-note").filter({ hasText: UNKNOWN }),
  ).toHaveCount(0);
});

test("a named hechsher can be chosen, and the request carries it", async ({ page }) => {
  const calls = await mockApi(page);
  await seedProfile(page);
  await page.goto("/profile");
  const diet = page.getByRole("region", { name: "כשרות ותזונה" });
  await diet.getByRole("radio", { name: 'בד"ץ' }).click();
  await diet.getByLabel("השגחה מסוימת").selectOption({ label: 'בד"ץ בית יוסף' });
  await expect(diet.getByRole("radio", { name: 'בד"ץ' })).toHaveAttribute("aria-checked", "true");
  await openResults(page);
  expect(calls.filter((c) => c.path === "/optimize").at(-1)!.body).toMatchObject({
    kosher: { level: "badatz_beit_yosef" },
  });
  // the Yohananof olive oil states a different hechsher: it is never offered, whatever it costs
  await page.getByTestId("basket-details").locator("summary").click();
  await expect(
    page
      .getByTestId("basket-details")
      .getByTestId("kosher-note")
      .filter({ hasText: "העדה החרדית" }),
  ).toHaveCount(0);
});

test("without a filter nothing about kashrut is shown or sent", async ({ page }) => {
  const calls = await mockApi(page);
  await seedProfile(page);
  await openResults(page);
  await expect(page.getByTestId("kosher-active")).toHaveCount(0);
  await expect(page.getByTestId("kosher-note")).toHaveCount(0);
  expect(calls.filter((c) => c.path === "/optimize").at(-1)!.body).not.toHaveProperty("kosher");
});

test("the setting and the labels are in Arabic too", async ({ page, baseURL }) => {
  await mockApi(page);
  await seedProfile(page);
  await page.context().addCookies([{ name: "sc-locale", value: "ar", url: baseURL! }]);
  await page.goto("/profile");
  const radios = page.getByRole("radiogroup", { name: "مستوى الكاشير" });
  await expect(radios).toBeVisible();
  await radios.getByRole("radio", { name: "مهدرين" }).click();
  await expect(page.getByTestId("kosher-notice")).toContainText("لا نفترض الكاشير");
});
