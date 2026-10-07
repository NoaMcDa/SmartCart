import { expect, test } from "@playwright/test";

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 900 },
]) {
  test.describe(`/design-system at ${viewport.width} px`, () => {
    test.use({ viewport });

    test("renders every component in both themes", async ({ page }, testInfo) => {
      await page.goto("/design-system");
      for (const t of ["light", "dark"] as const) {
        const panel = page.getByTestId(`ds-panel-${t}`);
        await expect(panel).toBeVisible();
        const bg = await panel.evaluate((el) => getComputedStyle(el).backgroundColor);
        expect(bg).toBe(t === "light" ? "rgb(246, 245, 242)" : "rgb(20, 20, 19)");
        await expect(panel.getByRole("button", { name: "השווי" })).toBeVisible();
        await expect(
          panel.getByRole("button", { name: "רמת גמישות: כל מותג" }).first(),
        ).toBeVisible();
        await expect(
          panel.getByRole("switch", { name: "זכרי בחירה זו לכל סוגי החלב" }),
        ).toBeVisible();
        await expect(panel.getByRole("radiogroup", { name: "תצוגה" })).toBeVisible();
        await expect(panel.getByRole("group", { name: "כמות: חלב טרי 3%, 1 ליטר" })).toBeVisible();
        for (const text of [
          "אותו סוג מוצר",
          "28% מוצקים · לא מאומת",
          "מותג פרטי במקום אסם",
          "1 פריט חסר",
        ]) {
          await expect(panel.getByText(text)).toBeVisible();
        }
      }
      // Touch targets: every button in the showcase is at least 44 px tall (chips use a 44 px hit area).
      const small = await page.evaluate(() =>
        [
          ...document.querySelectorAll<HTMLElement>(
            "[data-testid^=ds-panel] button:not([role=radio]):not([role=switch])",
          ),
        ]
          .filter((b) => !b.dataset.flexLevel && !b.hasAttribute("aria-pressed"))
          .filter((b) => b.getBoundingClientRect().height < 44)
          .map((b) => b.textContent),
      );
      expect(small).toEqual([]);
      await testInfo.attach(`design-system-${viewport.width}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    });

    test("prices are LTR islands: ₪ sits left of the digits inside Hebrew text", async ({
      page,
    }) => {
      await page.goto("/design-system");
      const island = page.getByTestId("price-sentence-light").locator('span[dir="ltr"]').first();
      await expect(island).toHaveText("₪ 389");
      const order = await island.evaluate((el) => {
        const text = el.firstChild as Text;
        const range = document.createRange();
        range.setStart(text, 0);
        range.setEnd(text, 1);
        const shekel = range.getBoundingClientRect().x;
        range.setStart(text, 2);
        range.setEnd(text, 3);
        const firstDigit = range.getBoundingClientRect().x;
        return { shekel, firstDigit };
      });
      expect(order.shekel).toBeLessThan(order.firstDigit);
      // The comma after the price stays outside the island, to its left in RTL.
      const sentence = page.getByTestId("price-sentence-light");
      await expect(sentence).toContainText("₪ 389, חוסך");
    });

    test("bottom sheet: opens as a dialog, traps focus, closes on Escape", async ({ page }) => {
      await page.goto("/design-system");
      const opener = page
        .getByTestId("ds-panel-light")
        .getByRole("button", { name: "פתיחת גיליון גמישות" });
      await opener.click();
      const dialog = page.getByRole("dialog", { name: "חלב טרי 3%, 1 ליטר" });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole("button", { name: "סגירה" })).toBeFocused();
      for (let i = 0; i < 6; i++) await page.keyboard.press("Tab");
      const inside = await page.evaluate(
        () => !!document.activeElement?.closest('[role="dialog"]'),
      );
      expect(inside).toBe(true);
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
      await expect(opener).toBeFocused();
    });
  });
}
