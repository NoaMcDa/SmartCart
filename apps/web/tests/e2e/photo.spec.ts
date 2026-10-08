import { expect, test, type Page } from "@playwright/test";
import { mockApi, seedProfile } from "./core-helpers";
import { bigPhoto, imageFile, jpegSize, mockPhotoApi, TINY_PNG } from "./photo-helpers";
import { noHorizontalScroll } from "./secondary.helpers";

/**
 * Photo to list (receipts #61, handwritten lists #68): the entry in the list builder, the consent
 * gate, the preview and the confirmation, the failure cases, and the Profile withdrawal. The
 * server is the phase 3 mock; file names pick the case (tests/e2e/photo-helpers.ts).
 */

const CONSENT_KEY = "sc-image-consent-v1";

test.use({ viewport: { width: 390, height: 844 } });

async function setup(page: Page) {
  await mockApi(page);
  const photo = await mockPhotoApi(page);
  await seedProfile(page);
  await page.goto("/");
  return photo;
}

async function openSheet(page: Page) {
  await page.getByTestId("photo-open").click();
  return page.getByRole("dialog", { name: "צילום לרשימה" });
}

/** Clicks the sheet's own button and hands the file to the input it opens. */
async function choose(
  page: Page,
  kind: "receipt" | "list",
  method: "camera" | "file",
  file: Parameters<ReturnType<Page["locator"]>["setInputFiles"]>[0],
) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByTestId(`photo-${kind}-${method}`).click();
  await (await chooser).setFiles(file);
}

test.describe("receipt to list", () => {
  test("consent first, then the preview, and only the ticked lines join the list", async ({
    page,
  }) => {
    const photo = await setup(page);
    const dialog = await openSheet(page);
    await expect(dialog.getByTestId("photo-privacy")).toContainText("נמחקת מיד");

    await choose(page, "receipt", "file", imageFile("receipt.png"));
    await expect(page.getByTestId("photo-consent")).toBeVisible();
    expect(photo.calls).toHaveLength(0); // nothing leaves the device before the yes
    expect(await page.evaluate((k) => localStorage.getItem(k), CONSENT_KEY)).toBeNull();

    await page.getByTestId("photo-consent-agree").click();
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    expect(await page.evaluate((k) => localStorage.getItem(k), CONSENT_KEY)).toBe("1");
    expect(photo.calls).toHaveLength(1);
    expect(photo.calls[0]).toMatchObject({
      consent: "1",
      kind: "receipt",
      filename: "receipt.png",
    });
    expect(photo.calls[0]!.contentType).toMatch(/^multipart\/form-data; boundary=/);

    const summary = page.getByTestId("photo-receipt-summary");
    await expect(summary.getByTestId("photo-chain")).toContainText("שופרסל");
    await expect(summary.getByTestId("photo-total")).toHaveText(/₪\s187\.40/);
    await expect(summary.getByTestId("photo-line-count")).toHaveText("6");
    await expect(page.getByTestId("photo-deleted")).toHaveText("התמונה נמחקה מהשרת");
    await expect(page.getByTestId("photo-row")).toHaveCount(3);
    await expect(page.getByTestId("photo-unsure")).toContainText("לאישור");
    await expect(page.getByTestId("photo-unresolved")).toContainText("לא זוהו (2)");
    await expect(page.getByTestId("photo-add")).toHaveText("הוסיפי 3 פריטים לרשימה");
    await expect(page.getByTestId("list-row")).toHaveCount(0); // nothing yet
    await noHorizontalScroll(page);

    await page.getByTestId("photo-unsure").getByRole("checkbox").check();
    await page.getByTestId("photo-add").click();
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("list-row")).toHaveCount(4);
    await expect(page.getByRole("group", { name: "אישור הפריט שמן זית" })).toBeVisible();
    await expect(page.getByText(/נוספו 4 פריטים מהצילום/)).toBeVisible();
  });

  test("the second photo does not ask again", async ({ page }) => {
    const photo = await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    await openSheet(page);
    await choose(page, "receipt", "camera", imageFile("again.png"));
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    await expect(page.getByTestId("photo-consent")).toHaveCount(0);
    expect(photo.calls).toHaveLength(1);
  });

  test("'לא עכשיו' sends nothing and closes the sheet", async ({ page }) => {
    const photo = await setup(page);
    const dialog = await openSheet(page);
    await choose(page, "list", "file", imageFile("list.png"));
    await page.getByTestId("photo-consent-decline").click();
    await expect(dialog).toBeHidden();
    expect(photo.calls).toHaveLength(0);
    expect(await page.evaluate((k) => localStorage.getItem(k), CONSENT_KEY)).toBeNull();
  });

  test("the progress state shows while the server reads, and cancelling goes back", async ({
    page,
  }) => {
    const photo = await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    photo.hold();
    await openSheet(page);
    await choose(page, "receipt", "file", imageFile("held.png"));
    await expect(page.getByTestId("photo-reading")).toContainText("קוראים את התמונה");
    await expect(page.getByTestId("photo-reading").getByRole("status")).toBeFocused();
    await page.getByTestId("photo-cancel").click();
    await expect(page.getByTestId("photo-receipt-camera")).toBeVisible();
    photo.release();
    await expect(page.getByTestId("photo-preview")).toHaveCount(0); // the late answer is dropped
  });
});

test.describe("handwritten list to list", () => {
  test("a corrected line is matched, the others stay as written, nothing is added unasked", async ({
    page,
  }) => {
    const photo = await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    await openSheet(page);
    await choose(page, "list", "camera", imageFile("hand.png"));
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    expect(photo.calls[0]).toMatchObject({ kind: "list", consent: "1" });
    await expect(page.getByRole("heading", { name: "מה זוהה ברשימה" })).toBeVisible();
    await expect(page.getByTestId("photo-receipt-summary")).toHaveCount(0);

    const lines = page.getByTestId("photo-unresolved-row");
    await lines.nth(0).getByRole("textbox").fill("קוטג");
    await expect(lines.nth(0).getByRole("checkbox")).toBeChecked();
    await lines.nth(1).getByRole("checkbox").check();
    await page.getByTestId("photo-add").click();

    await expect(page.getByTestId("not-found-row")).toContainText("סבון כלים");
    await expect(page.getByTestId("list-row").filter({ hasText: "קוטג" })).toHaveCount(1);
  });

  test("a large photo is downscaled to 2400 px before it is sent", async ({ page }) => {
    const photo = await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    const original = await bigPhoto(page, 4000, 3000);
    expect(jpegSize(original)).toEqual({ width: 4000, height: 3000 });
    await openSheet(page);
    await choose(page, "list", "file", imageFile("big.jpg", "image/jpeg", original));
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    const sent = photo.calls[0]!;
    expect(jpegSize(sent.bytes)).toEqual({ width: 2400, height: 1800 });
    expect(sent.size).toBeLessThan(original.length);
    expect(sent.contentType).toContain("multipart/form-data");
  });
});

test.describe("what cannot be read", () => {
  test("a PDF and a file over 8 MB are refused on the device with a clear message", async ({
    page,
  }) => {
    const photo = await setup(page);
    await openSheet(page);
    await choose(page, "receipt", "file", imageFile("a.pdf", "application/pdf"));
    await expect(page.getByTestId("photo-problem")).toContainText("אינו תמונה");
    await expect(page.getByTestId("photo-problem")).toBeFocused();
    await choose(
      page,
      "receipt",
      "file",
      imageFile("huge.jpg", "image/jpeg", Buffer.alloc(8 * 1024 * 1024 + 1)),
    );
    await expect(page.getByTestId("photo-problem")).toContainText("8 מ״ב");
    expect(photo.calls).toHaveLength(0);
    await expect(page.getByTestId("photo-consent")).toHaveCount(0);
  });

  const cases = [
    ["x-429.png", "quota", "הגענו למכסה החודשית, נסו שוב בחודש הבא"],
    ["x-413.png", "too-large", "גדולה מדי"],
    ["x-415.png", "type", "סוג הקובץ לא נתמך"],
    ["x-503.png", "unavailable", "לא זמינה כרגע"],
  ] as const;
  for (const [name, kind, text] of cases) {
    test(`${name} shows its message and a way forward`, async ({ page }) => {
      await setup(page);
      await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
      await openSheet(page);
      await choose(page, "receipt", "file", imageFile(name));
      const error = page.getByTestId("photo-error");
      await expect(error).toHaveAttribute("data-kind", kind);
      await expect(error).toContainText(text);
      await expect(page.getByTestId("photo-type")).toBeVisible();
      await noHorizontalScroll(page);
      await page.getByTestId("photo-type").click();
      await expect(page.getByLabel("הוסיפי פריטים לרשימה")).toBeFocused();
    });
  }

  test("a dropped connection offers a retry that works", async ({ page }) => {
    const photo = await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    photo.failNext();
    await openSheet(page);
    await choose(page, "list", "file", imageFile("net.png"));
    await expect(page.getByTestId("photo-error")).toContainText("לא הצלחנו להתחבר לשרת");
    await page.getByTestId("photo-retry").click();
    await expect(page.getByTestId("photo-preview")).toBeVisible();
    expect(photo.calls).toHaveLength(2);
  });

  test("an image with nothing readable says so", async ({ page }) => {
    await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    await openSheet(page);
    await choose(page, "list", "file", imageFile("empty.png"));
    await expect(page.getByTestId("photo-empty")).toContainText("לא מצאנו פריטים בתמונה");
  });
});

test.describe("withdrawing the consent", () => {
  test("Profile shows the switch, turning it off asks again next time, delete-my-data clears it", async ({
    page,
  }) => {
    const photo = await setup(page);
    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    await page.goto("/profile");
    const toggle = page.getByRole("switch", { name: "קריאת תמונות של קבלות ורשימות" });
    await expect(toggle).toBeChecked();
    await toggle.click();
    await expect(toggle).not.toBeChecked();
    expect(await page.evaluate((k) => localStorage.getItem(k), CONSENT_KEY)).toBeNull();

    await page.goto("/");
    await openSheet(page);
    await choose(page, "receipt", "file", imageFile("r.png"));
    await expect(page.getByTestId("photo-consent")).toBeVisible();
    expect(photo.calls).toHaveLength(0);

    await page.evaluate((k) => localStorage.setItem(k, "1"), CONSENT_KEY);
    await page.goto("/profile");
    await expect(toggle).toBeChecked();
    await page.getByRole("button", { name: "מחקי את הנתונים שלי" }).click();
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByTestId("delete-done")).toBeVisible();
    expect(await page.evaluate((k) => localStorage.getItem(k), CONSENT_KEY)).toBeNull();
    await expect(toggle).not.toBeChecked();
  });
});

test("the tiny PNG fixture decodes (guards the other tests' premise)", async ({ page }) => {
  await page.goto("/");
  const ok = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const bmp = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
    return [bmp.width, bmp.height];
  }, TINY_PNG.toString("base64"));
  expect(ok).toEqual([1, 1]);
});
