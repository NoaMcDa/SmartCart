/**
 * Recipe to list (issue #71, UI half): scaling, the sheet, and the path into the list builder's
 * normal rows and confirmations. `POST /parse-recipe` is answered by the phase 3 mock.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import type { ParsedRow } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { ListBuilder } from "@/features/list/ListBuilder";
import { parseRow } from "@/mocks/parseRow";
import { server } from "@/mocks/node";
import { resetListStoreForTests } from "@/state/list";
import { scaledQuantity, scaleRows, unresolvedRow } from "./scale";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetListStoreForTests();
});

describe("scaling", () => {
  const pasta = parseRow("פסטה"); // 1 pack
  const paste = parseRow("2 רסק עגבניות");
  const tomatoes = parseRow("עגבניות"); // weighed

  it("returns the recipe's own quantities when the servings are unchanged", () => {
    expect(scaledQuantity(paste, 4, 4)).toBe(2);
    expect(scaleRows([pasta, paste], 4, 4).map((r) => r.quantity)).toEqual(["1", "2"]);
  });

  it("rounds countable items up to whole packs", () => {
    expect(scaledQuantity(pasta, 4, 6)).toBe(2); // 1.5 packs -> 2
    expect(scaledQuantity(paste, 4, 6)).toBe(3);
    expect(scaledQuantity(paste, 4, 2)).toBe(1);
    expect(scaledQuantity(pasta, 4, 1)).toBe(1); // never zero
    expect(scaledQuantity(paste, 4, 8)).toBe(4);
  });

  it("scales weighed goods smoothly, in 50 g steps", () => {
    expect(tomatoes.is_weighed).toBe(true);
    expect(scaledQuantity(tomatoes, 4, 6)).toBe(1.5);
    expect(scaledQuantity({ ...tomatoes, quantity: "0.5" }, 4, 5)).toBe(0.65);
    expect(scaledQuantity({ ...tomatoes, quantity: "0.5" }, 4, 1)).toBe(0.15);
  });

  it("does not change the other fields of a row and tolerates a bad quantity", () => {
    const [row] = scaleRows([{ ...paste, quantity: "x" }], 4, 8);
    expect(row).toMatchObject({ input_text: paste.input_text, canonical: paste.canonical });
    expect(row!.quantity).toBe("2");
  });

  it("an unmatched line becomes a not-found row for the list's editing group", () => {
    expect(unresolvedRow("חופן בזיליקום")).toMatchObject({
      input_text: "חופן בזיליקום",
      not_found: true,
      canonical: null,
    });
  });
});

async function openRecipe() {
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(await screen.findByTestId("recipe-open"));
  const dialog = screen.getByRole("dialog", { name: "מתכון לרשימה" });
  // BottomSheet moves focus into itself one animation frame after opening. Wait for that, or on a
  // slow runner it lands after the test focused the text field and the paste goes elsewhere.
  await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
  return { user, dialog };
}

const RECIPE_TEXT = "פסטה ברוטב עגבניות\n500 גרם פסטה\n2 רסק עגבניות\nעגבניות\nחופן בזיליקום";

describe("the recipe sheet", () => {
  it("opens from the list builder and is closed again by cancel", async () => {
    const { user, dialog } = await openRecipe();
    expect(within(dialog).getByRole("radio", { name: "הדבקת טקסט" })).toBeChecked();
    await user.click(within(dialog).getByRole("button", { name: "ביטול" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("reads pasted text, scales to the servings, and adds the rows to the list", async () => {
    const bodies: unknown[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.url.endsWith("/parse-recipe")) bodies.push(await request.clone().json());
    });
    const { user, dialog } = await openRecipe();
    await user.click(within(dialog).getByLabelText("המתכון או רשימת המצרכים"));
    await user.paste(RECIPE_TEXT);
    await user.click(screen.getByTestId("recipe-read"));

    expect(await screen.findByTestId("recipe-title")).toHaveTextContent("פסטה ברוטב עגבניות");
    expect(bodies).toEqual([{ text: RECIPE_TEXT }]); // no servings in the request: scaling is local
    const quantities = () =>
      screen.getAllByTestId("recipe-item").map((li) => li.textContent?.replace(/\s+/g, " ").trim());
    expect(quantities()).toEqual([
      expect.stringMatching(/^1\s*פסטה פנה/),
      expect.stringMatching(/^2\s*רסק עגבניות/),
      expect.stringMatching(/^1 ק״ג\s*עגבניות/),
    ]);
    expect(screen.getByTestId("recipe-unresolved")).toHaveTextContent("חופן בזיליקום");

    // 4 -> 6 servings: the paste goes 2 -> 3, the tomatoes 1 kg -> 1.5 kg, the pasta 1 -> 2 packs.
    const stepper = screen.getByRole("group", { name: "כמות: מנות" });
    await user.click(within(stepper).getByRole("button", { name: "הוסיפי כמות של מנות" }));
    await user.click(within(stepper).getByRole("button", { name: "הוסיפי כמות של מנות" }));
    expect(quantities()).toEqual([
      expect.stringMatching(/^2\s*פסטה פנה/),
      expect.stringMatching(/^3\s*רסק עגבניות/),
      expect.stringMatching(/^1\.5 ק״ג\s*עגבניות/),
    ]);

    await user.click(screen.getByTestId("recipe-add"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const rows = screen.getAllByTestId("list-row");
    expect(rows).toHaveLength(3);
    const paste = rows.find((r) => r.textContent?.includes("רסק"))!;
    expect(within(paste).getByRole("group")).toHaveTextContent("3");
    // The unmatched line lands where the list builder already lets the person edit or remove it.
    expect(screen.getByTestId("not-found-row")).toHaveTextContent("חופן בזיליקום");
    expect(screen.getByText(/נוספו 4 פריטים מהמתכון "פסטה ברוטב עגבניות" ל-6 מנות/)).toBeVisible();
  });

  it("reads a link, and rejects one that is not http(s) without a request", async () => {
    const bodies: unknown[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.url.endsWith("/parse-recipe")) bodies.push(await request.clone().json());
    });
    const { user, dialog } = await openRecipe();
    await user.click(within(dialog).getByRole("radio", { name: "קישור למתכון" }));
    const field = within(dialog).getByLabelText("קישור למתכון");
    await user.type(field, "ftp://example.com/x");
    await user.click(screen.getByTestId("recipe-read"));
    expect(await screen.findByRole("alert")).toHaveTextContent("https://");
    expect(bodies).toEqual([]);

    await user.clear(field);
    await user.type(field, "https://example.com/pasta");
    await user.click(screen.getByTestId("recipe-read"));
    expect(await screen.findByTestId("recipe-title")).toHaveTextContent("פסטה ברוטב עגבניות");
    expect(bodies).toEqual([{ url: "https://example.com/pasta" }]);
    expect(screen.getByTestId("recipe-unresolved")).toHaveTextContent("מלח");
  });

  it("uncertain rows land in the list with the normal amber confirmation", async () => {
    server.use(
      http.post(`${API_BASE_URL}/parse-recipe`, () =>
        HttpResponse.json({
          title: "סלט",
          servings: 2,
          items: [parseRow("שמן זית")] satisfies ParsedRow[],
          unresolved: [],
        }),
      ),
    );
    const { user, dialog } = await openRecipe();
    await user.click(within(dialog).getByLabelText("המתכון או רשימת המצרכים"));
    await user.paste("שמן זית");
    await user.click(screen.getByTestId("recipe-read"));
    expect(await screen.findByTestId("recipe-item")).toHaveTextContent("לאישור");
    await user.click(screen.getByTestId("recipe-add"));
    await screen.findAllByTestId("list-row");
    expect(screen.getByRole("group", { name: "אישור הפריט שמן זית" })).toBeVisible();
  });

  it("says so when nothing could be read, and when the server is down", async () => {
    server.use(
      http.post(`${API_BASE_URL}/parse-recipe`, () =>
        HttpResponse.json({ title: "מתכון", servings: 4, items: [], unresolved: [] }),
      ),
    );
    const { user, dialog } = await openRecipe();
    await user.click(within(dialog).getByLabelText("המתכון או רשימת המצרכים"));
    await user.paste("בלה בלה");
    expect(within(dialog).getByLabelText("המתכון או רשימת המצרכים")).toHaveValue("בלה בלה");
    await user.click(screen.getByTestId("recipe-read"));
    // Wait for the server's answer, not the first alert: on a slow runner the empty-input hint can
    // still be the alert on screen when findByRole resolves.
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("לא מצאנו מצרכים"));

    server.use(http.post(`${API_BASE_URL}/parse-recipe`, () => HttpResponse.error()));
    await user.click(screen.getByTestId("recipe-read"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("לא הצלחנו להתחבר לשרת"),
    );
  });
});
