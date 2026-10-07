import { expect, test } from "@playwright/test";
import {
  API_BASE_URL,
  DEMO_LIST,
  DISCLAIMER,
  SHUFERSAL,
  nearestStore,
  pasteList,
  seedShopper,
  stubSupabase,
} from "./helpers";

/**
 * A close substitute from the real catalog: the demo's Machsanei Hashuk sells a 1 kg standard
 * loaf (a different pack size than the 750 g canonical, so the judge maps it at "close"). With the
 * bread row at "תחליף קרוב" the recommended plan carries it as a labeled substitute.
 */
test.use({ viewport: { width: 1280, height: 900 } });

test("a close substitute is labeled, explained, and keeping the original pins the exact item", async ({
  page,
  request,
}) => {
  const home = await nearestStore(request, SHUFERSAL);
  await stubSupabase(page);
  await seedShopper(page, home.store_id);
  const feedback: unknown[] = [];
  page.on("request", (req) => {
    if (req.url() === `${API_BASE_URL}/feedback/substitution` && req.method() === "POST") {
      feedback.push(req.postDataJSON());
    }
  });

  await page.goto("/");
  await pasteList(page, DEMO_LIST);
  const bread = page.getByTestId("list-row").filter({ hasText: "לחם אחיד" });
  const chip = bread.getByRole("button", { name: /^רמת גמישות/ });
  await expect(chip).toHaveAccessibleName("רמת גמישות: כל מותג");
  await chip.click();
  const sheet = page.getByRole("dialog", { name: "לחם אחיד" });
  await sheet.getByRole("radio", { name: /תחליף קרוב/ }).check();
  await sheet.getByRole("button", { name: "שמרי" }).click();
  await expect(chip).toHaveAccessibleName("רמת גמישות: תחליף קרוב");

  await page.getByRole("link", { name: "השווי" }).click();
  const split = page.getByTestId("plan-split");
  await expect(split).toHaveAttribute("data-recommended", "true");
  const link = split.getByRole("link", { name: /פריט הוחלף/ });
  await expect(link).toBeVisible();
  // The basket details label the substitute too.
  await expect(page.getByTestId("disclaimer")).toContainText(DISCLAIMER);
  await page.getByText(/^פירוט הסל/).click();
  await expect(
    page.getByTestId("basket-details").getByRole("link", { name: /^תחליף:/ }),
  ).toHaveCount(1);

  await link.click();
  await expect(page).toHaveURL(/\/compare\/substitution\/\d+\?plan=split$/);
  await expect(page.getByRole("heading", { level: 1, name: "פרטי החלפה" })).toBeVisible();
  const card = page.getByTestId("sub-card");
  await expect(card).toContainText("החלפה 1 מתוך 1 · מחסני השוק");
  await expect(card.getByRole("heading", { level: 2 })).toContainText('לחם אחיד פרוס שדות 1 ק"ג');
  // Original versus substitute, each with its price and its update time.
  await expect(page.getByTestId("sub-original")).toContainText("לחם אחיד פרוס אנג'ל 750 גרם");
  await expect(page.getByTestId("sub-substitute")).toContainText(/₪\s5\.90/);
  for (const side of ["sub-original", "sub-substitute"]) {
    await expect(page.getByTestId(side).locator("time[datetime]")).toHaveCount(1);
  }
  // Why it is a substitute: the confidence and attribute tags, each with an icon.
  await expect(page.getByTestId("sub-source")).toContainText("ביטחון");
  const tags = card.getByRole("list", { name: "השוואת תכונות" }).locator("[data-variant]");
  expect(await tags.count()).toBeGreaterThan(0);
  for (const tag of await tags.all()) await expect(tag.locator("svg")).toHaveCount(1);
  // The card itself has no checkout disclaimer (docs/fullstack.md, known gaps); the results do.

  // Keep the original: recorded as feedback, and the row is pinned to the exact item.
  await card.getByRole("button", { name: "השאירי את המקורי" }).click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.getByTestId("flash")).toContainText("השארנו את המוצר המקורי");
  await expect.poll(() => feedback.length).toBeGreaterThan(0);
  expect(feedback[0]).toMatchObject({ verdict: "kept_original" });
  // The new comparison prices the exact original; the split no longer carries a substitute.
  await expect(page.getByTestId("plan-split")).toBeVisible();
  await expect(
    page.getByTestId("plan-split").getByRole("link", { name: /פריט הוחלף/ }),
  ).toHaveCount(0);

  await page.getByRole("link", { name: "חזרה לרשימה" }).click();
  await expect(
    page
      .getByTestId("list-row")
      .filter({ hasText: "לחם אחיד" })
      .getByRole("button", { name: /^רמת גמישות/ }),
  ).toHaveAccessibleName("רמת גמישות: מוצר מדויק");
});
