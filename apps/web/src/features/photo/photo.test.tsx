/**
 * Photo to list (receipts #61, handwritten lists #68): the entry in the list builder, the consent
 * gate, the progress and the preview, the error paths, the events and the Profile toggle. The
 * server is the phase 3 mock (`POST /parse-image`), whose magic file names pick the case.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse, type JsonBodyType } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { parseImage } from "@/api/client";
import { API_BASE_URL } from "@/api/config";
import { ensureApiAuth, setApiToken } from "@/features/auth/apiAuth";
import { ImageConsentToggle } from "@/features/photo/ImageConsentToggle";
import {
  getImageConsent,
  IMAGE_CONSENT_KEY,
  resetImageConsentForTests,
  setImageConsent,
} from "@/features/consent/imageConsent";
import { ListBuilder } from "@/features/list/ListBuilder";
import { trackEvent } from "@/features/seo/track";
import { server } from "@/mocks/node";
import { getListState, resetListStoreForTests } from "@/state/list";
import { MAX_UPLOAD_BYTES } from "./imageFile";
import { PhotoSheet } from "./PhotoSheet";

vi.mock("@/features/seo/track", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/seo/track")>()),
  trackEvent: vi.fn(),
}));

type Upload = {
  consent: string | null;
  authorization: string | null;
  kind: unknown;
  filename: string;
  size: number;
};
let uploads: Upload[];

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
  cleanup();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetImageConsentForTests();
  resetListStoreForTests();
  vi.mocked(trackEvent).mockClear();
  uploads = [];
  server.events.on("request:start", async ({ request }) => {
    if (!request.url.endsWith("/parse-image")) return;
    // A request the test aborts (a dropped connection) may not finish streaming its body.
    const form = await request
      .clone()
      .formData()
      .catch(() => null);
    if (!form) return;
    const image = form.get("image") as File;
    uploads.push({
      consent: request.headers.get("X-Image-Consent"),
      authorization: request.headers.get("Authorization"),
      kind: form.get("kind"),
      filename: image.name,
      size: image.size,
    });
  });
});

/** Overrides `POST /parse-image` for the next requests (jsdom's File loses its name on the wire). */
function answer(status: number, body: JsonBodyType = { detail: "x" }, options = {}) {
  server.use(
    http.post(`${API_BASE_URL}/parse-image`, () => HttpResponse.json(body, { status }), options),
  );
}

const image = (name = "photo.jpg", type = "image/jpeg", bytes = 2000) =>
  new File([new Uint8Array(bytes)], name, { type });

async function openSheet() {
  const user = userEvent.setup();
  render(<ListBuilder />);
  await user.click(await screen.findByTestId("photo-open"));
  return { user, dialog: screen.getByRole("dialog", { name: "צילום לרשימה" }) };
}

/** Picks a file for a kind through the sheet's own buttons and the hidden input behind them. */
async function pick(
  user: ReturnType<typeof userEvent.setup>,
  kind: "receipt" | "list",
  file: File,
  method: "camera" | "file" = "file",
) {
  await user.click(screen.getByTestId(`photo-${kind}-${method}`));
  fireEvent.change(screen.getByTestId(`photo-input-${method}`), { target: { files: [file] } });
}

describe("the entry and the choices", () => {
  it("opens from the list builder with the two kinds, each with camera and file", async () => {
    const { dialog } = await openSheet();
    expect(within(dialog).getByRole("heading", { name: "קבלה" })).toBeVisible();
    expect(within(dialog).getByRole("heading", { name: "רשימה בכתב יד" })).toBeVisible();
    for (const what of ["קבלה", "רשימה בכתב יד"]) {
      expect(within(dialog).getByRole("button", { name: `צילום ${what}` })).toBeVisible();
      expect(within(dialog).getByRole("button", { name: `בחירת קובץ: ${what}` })).toBeVisible();
    }
    expect(within(dialog).getByTestId("photo-privacy")).toHaveTextContent("נמחקת מיד");
  });

  it("the camera input captures the back camera and the file input does not", async () => {
    await openSheet();
    const camera = screen.getByTestId("photo-input-camera");
    const file = screen.getByTestId("photo-input-file");
    expect(camera).toHaveAttribute("accept", "image/*");
    expect(camera).toHaveAttribute("capture", "environment");
    expect(file).toHaveAttribute("accept", "image/*");
    expect(file).not.toHaveAttribute("capture");
    // The inputs sit outside the dialog, so the sheet's focus trap never counts them.
    expect(screen.getByRole("dialog")).not.toContainElement(camera);
  });

  it("each button opens its own input", async () => {
    const { user } = await openSheet();
    const camera = vi.spyOn(screen.getByTestId("photo-input-camera") as HTMLInputElement, "click");
    const file = vi.spyOn(screen.getByTestId("photo-input-file") as HTMLInputElement, "click");
    await user.click(screen.getByTestId("photo-list-camera"));
    expect(camera).toHaveBeenCalledTimes(1);
    expect(file).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("photo-list-file"));
    expect(file).toHaveBeenCalledTimes(1);
  });
});

describe("client-side checks", () => {
  it("rejects a file that is not an image, with no request and no consent question", async () => {
    const { user } = await openSheet();
    await pick(user, "list", image("notes.pdf", "application/pdf"));
    expect(await screen.findByTestId("photo-problem")).toHaveTextContent("אינו תמונה");
    expect(uploads).toEqual([]);
    expect(screen.queryByTestId("photo-consent")).not.toBeInTheDocument();
    expect(screen.getByTestId("photo-list-file")).toBeVisible(); // still on the choices
    expect(trackEvent).toHaveBeenCalledWith("image_parsed", { kind: "list", outcome: "refused" });
  });

  it("rejects an image over 8 MB with its size limit in the message", async () => {
    const { user } = await openSheet();
    await pick(user, "receipt", image("big.jpg", "image/jpeg", MAX_UPLOAD_BYTES + 1));
    expect(await screen.findByTestId("photo-problem")).toHaveTextContent("8 מ״ב");
    expect(uploads).toEqual([]);
  });
});

describe("consent", () => {
  it("asks before the first upload and makes no request until the person agrees", async () => {
    const { user } = await openSheet();
    await pick(user, "receipt", image("r.jpg"));
    const consent = await screen.findByTestId("photo-consent");
    expect(consent).toHaveTextContent("נמחקת מיד");
    expect(consent).toHaveTextContent("לא נשמר");
    expect(uploads).toEqual([]);
    expect(getImageConsent()).toBe(false);

    await user.click(screen.getByTestId("photo-consent-agree"));
    expect(await screen.findByTestId("photo-preview")).toBeVisible();
    expect(window.localStorage.getItem(IMAGE_CONSENT_KEY)).toBe("1");
    expect(uploads).toMatchObject([{ consent: "1", kind: "receipt", size: 2000 }]);
  });

  it("'לא עכשיו' closes the sheet with no request and nothing stored", async () => {
    const { user } = await openSheet();
    await pick(user, "list", image());
    await user.click(await screen.findByTestId("photo-consent-decline"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(uploads).toEqual([]);
    expect(getImageConsent()).toBe(false);
    expect(window.localStorage.getItem(IMAGE_CONSENT_KEY)).toBeNull();
  });

  it("does not ask again once agreed", async () => {
    setImageConsent(true);
    const { user } = await openSheet();
    await pick(user, "list", image());
    expect(await screen.findByTestId("photo-preview")).toBeVisible();
    expect(screen.queryByTestId("photo-consent")).not.toBeInTheDocument();
    expect(uploads).toHaveLength(1);
  });

  it("the upload carries the bearer token like the other helpers, and none when signed out", async () => {
    ensureApiAuth();
    try {
      await parseImage("list", image(), true);
      setApiToken("session-token");
      await parseImage("receipt", image(), true);
    } finally {
      setApiToken(null);
    }
    expect(uploads.map((u) => u.authorization)).toEqual([null, "Bearer session-token"]);
  });

  it("the API helper itself refuses to send without consent", async () => {
    await expect(parseImage("list", image(), false)).rejects.toMatchObject({ status: 403 });
    expect(uploads).toEqual([]);
  });

  it("a 403 from the server goes back to the consent step and retries after the yes", async () => {
    setImageConsent(true);
    server.use(
      http.post(`${API_BASE_URL}/parse-image`, () => HttpResponse.json({}, { status: 403 }), {
        once: true,
      }),
    );
    const { user } = await openSheet();
    await pick(user, "receipt", image());
    expect(await screen.findByTestId("photo-error")).toHaveAttribute("data-kind", "consent");
    await user.click(screen.getByTestId("photo-reconsent"));
    expect(screen.getByTestId("photo-consent")).toHaveTextContent("השרת ביקש אישור");
    await user.click(screen.getByTestId("photo-consent-agree"));
    expect(await screen.findByTestId("photo-preview")).toBeVisible();
  });
});

describe("the preview of a receipt", () => {
  async function readReceipt() {
    setImageConsent(true);
    const ctx = await openSheet();
    await pick(ctx.user, "receipt", image("receipt.jpg"));
    await screen.findByTestId("photo-preview");
    return ctx;
  }

  it("shows the summary, the groups and the deletion line, and adds nothing yet", async () => {
    await readReceipt();
    const summary = screen.getByTestId("photo-receipt-summary");
    expect(within(summary).getByTestId("photo-chain")).toHaveTextContent(
      "שופרסל · שופרסל דיל מודיעין",
    );
    expect(within(summary).getByTestId("photo-total")).toHaveTextContent(/187\.40/);
    expect(within(summary).getByTestId("photo-line-count")).toHaveTextContent("6");
    expect(screen.getByTestId("photo-deleted")).toHaveTextContent("התמונה נמחקה מהשרת");
    expect(screen.getAllByTestId("photo-row")).toHaveLength(3);
    expect(getListState().items).toEqual([]);
  });

  it("marks the uncertain match in amber, unticked, and the unresolved lines apart", async () => {
    await readReceipt();
    const unsure = screen.getByTestId("photo-unsure");
    expect(within(unsure).getByText("לאישור")).toBeVisible();
    expect(within(unsure).getByRole("checkbox")).not.toBeChecked();
    for (const box of within(screen.getAllByTestId("photo-row")[0]!.parentElement!).getAllByRole(
      "checkbox",
    )) {
      expect(box).toBeChecked();
    }
    const lines = screen.getByTestId("photo-unresolved");
    expect(within(lines).getByRole("heading")).toHaveTextContent("לא זוהו (2)");
    expect(within(lines).getAllByRole("textbox")).toHaveLength(2);
    for (const box of within(lines).getAllByRole("checkbox")) expect(box).not.toBeChecked();
    await waitFor(() =>
      expect(screen.getByTestId("photo-add")).toHaveTextContent("הוסיפי 3 פריטים לרשימה"),
    );
  });

  it("adds only what is ticked, and the uncertain match arrives for the list's own confirmation", async () => {
    const { user } = await readReceipt();
    await user.click(within(screen.getByTestId("photo-unsure")).getByRole("checkbox"));
    expect(screen.getByTestId("photo-add")).toHaveTextContent("הוסיפי 4 פריטים לרשימה");
    await user.click(screen.getByTestId("photo-add"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("list-row")).toHaveLength(4);
    expect(screen.getByRole("group", { name: "אישור הפריט שמן זית" })).toBeVisible();
    expect(screen.getByText(/נוספו 4 פריטים מהצילום/)).toBeVisible();
    expect(screen.queryByTestId("not-found-row")).not.toBeInTheDocument();
  });

  it("an unticked match is not added", async () => {
    const { user } = await readReceipt();
    await user.click(within(screen.getAllByTestId("photo-row")[0]!).getByRole("checkbox"));
    await user.click(screen.getByTestId("photo-add"));
    expect(screen.getAllByTestId("list-row")).toHaveLength(2);
  });

  it("'חזרה' returns to the choices without adding anything", async () => {
    const { user } = await readReceipt();
    await user.click(screen.getByTestId("photo-back"));
    expect(screen.getByTestId("photo-receipt-camera")).toBeVisible();
    expect(getListState().items).toEqual([]);
  });
});

describe("the preview of a handwritten list", () => {
  async function readList() {
    setImageConsent(true);
    const ctx = await openSheet();
    await pick(ctx.user, "list", image("list.jpg"), "camera");
    await screen.findByTestId("photo-preview");
    return ctx;
  }

  it("has no receipt summary, and keeps each line next to what it was matched to", async () => {
    await readList();
    expect(screen.queryByTestId("photo-receipt-summary")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "מה זוהה ברשימה" })).toBeVisible();
    expect(screen.getByTestId("photo-deleted")).toBeVisible();
  });

  it("lets a line that was not recognized be corrected and added; a rewrite goes through /parse-list", async () => {
    const { user } = await readList();
    const rows = screen.getAllByTestId("photo-unresolved-row");
    const field = within(rows[0]!).getByRole("textbox");
    await user.clear(field);
    await user.type(field, "קוטג");
    expect(within(rows[0]!).getByRole("checkbox")).toBeChecked(); // typing means "I want it"
    await user.click(within(rows[1]!).getByRole("checkbox")); // left as read

    await user.click(screen.getByTestId("photo-add"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // Two sure matches, the corrected line matched by /parse-list, the other kept as free text.
    const listed = screen.getAllByTestId("list-row").map((r) => r.textContent ?? "");
    expect(listed.some((t) => t.includes("קוטג"))).toBe(true);
    expect(screen.getByTestId("not-found-row")).toHaveTextContent("סבון כלים");
  });

  it("a rewrite that /parse-list cannot take still joins the list as the person's own words", async () => {
    server.use(http.post(`${API_BASE_URL}/parse-list`, () => HttpResponse.error()));
    const { user } = await readList();
    const field = within(screen.getAllByTestId("photo-unresolved-row")[0]!).getByRole("textbox");
    await user.clear(field);
    await user.type(field, "פלפל חריף");
    await user.click(screen.getByTestId("photo-add"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByTestId("not-found-row")).toHaveTextContent("פלפל חריף");
  });
});

describe("empty and failed reads", () => {
  it("says so when nothing was read and offers a new photo or typing", async () => {
    setImageConsent(true);
    answer(200, {
      kind: "list",
      provider: "fake",
      items: [],
      unresolved: [],
      receipt: null,
      deleted: true,
    });
    const { user } = await openSheet();
    await pick(user, "list", image("empty.jpg"));
    expect(await screen.findByTestId("photo-empty")).toHaveTextContent("לא מצאנו פריטים בתמונה");
    expect(trackEvent).toHaveBeenCalledWith(
      "image_parsed",
      expect.objectContaining({ kind: "list", outcome: "empty", item_count: 0 }),
    );
    await user.click(screen.getByTestId("photo-another"));
    expect(screen.getByTestId("photo-list-camera")).toBeVisible();
  });

  const cases: Array<[number, string, string]> = [
    [413, "too-large", "גדולה מדי"],
    [415, "type", "סוג הקובץ לא נתמך"],
    [429, "quota", "הגענו למכסה החודשית, נסו שוב בחודש הבא"],
    [503, "unavailable", "לא זמינה כרגע"],
    [501, "unavailable", "לא זמינה כרגע"],
    [500, "generic", "משהו השתבש"],
  ];
  it.each(cases)(
    "a %i answer shows its own message and the way back to typing",
    async (status, kind, text) => {
      setImageConsent(true);
      answer(status);
      const typed = vi.fn();
      const user = userEvent.setup();
      render(<PhotoSheet open onClose={() => {}} onAdd={() => {}} onTypeInstead={typed} />);
      await pick(user, "receipt", image());
      const error = await screen.findByTestId("photo-error");
      expect(error).toHaveAttribute("data-kind", kind);
      expect(error).toHaveTextContent(text);
      await user.click(screen.getByTestId("photo-type"));
      await waitFor(() => expect(typed).toHaveBeenCalledTimes(1));
    },
  );

  it("the monthly cap offers no retry; a failure that may pass offers one that works", async () => {
    setImageConsent(true);
    answer(429, { detail: "x" }, { once: true });
    const { user } = await openSheet();
    await pick(user, "receipt", image());
    await screen.findByTestId("photo-error");
    expect(screen.queryByTestId("photo-retry")).not.toBeInTheDocument();
    expect(screen.queryByTestId("photo-another")).not.toBeInTheDocument();
    expect(screen.getByTestId("photo-type")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "סגירה" }));

    // A dropped connection, then the same photo again.
    await user.click(screen.getByTestId("photo-open"));
    server.use(
      http.post(`${API_BASE_URL}/parse-image`, () => HttpResponse.error(), { once: true }),
    );
    await pick(user, "receipt", image("fine.jpg"));
    expect(await screen.findByTestId("photo-error")).toHaveAttribute("data-kind", "network");
    expect(screen.getByTestId("photo-error")).toHaveTextContent("לא הצלחנו להתחבר לשרת");
    await user.click(screen.getByTestId("photo-retry"));
    expect(await screen.findByTestId("photo-preview")).toBeVisible();
  });

  it("'להקליד במקום' puts the cursor in the list input", async () => {
    setImageConsent(true);
    answer(503);
    const { user } = await openSheet();
    await pick(user, "list", image());
    await screen.findByTestId("photo-error");
    await user.click(screen.getByTestId("photo-type"));
    await waitFor(() => expect(screen.getByLabelText("הוסיפי פריטים לרשימה")).toHaveFocus());
  });
});

describe("progress and cancelling", () => {
  it("shows a progress state, and cancelling sends nothing further to the list", async () => {
    setImageConsent(true);
    server.use(http.post(`${API_BASE_URL}/parse-image`, () => delay("infinite")));
    const { user } = await openSheet();
    await pick(user, "list", image());
    const reading = await screen.findByTestId("photo-reading");
    expect(within(reading).getByRole("status")).toHaveTextContent("קוראים את התמונה");
    await user.click(screen.getByTestId("photo-cancel"));
    expect(screen.getByTestId("photo-list-camera")).toBeVisible();
    expect(getListState().items).toEqual([]);
  });
});

describe("events", () => {
  it("sends the kind, the outcome and counts, never the text or the file name", async () => {
    setImageConsent(true);
    const { user } = await openSheet();
    await pick(user, "receipt", image("secret-name.jpg"));
    try {
      await screen.findByTestId("photo-preview");
    } catch (err) {
      const dialog = document.querySelector('[role="dialog"]');
      const html = (dialog?.innerHTML ?? "NO DIALOG").replace(/<svg[\s\S]*?<\/svg>/g, "");
      console.error("DEBUGFLAKE uploads", JSON.stringify(uploads));
      console.error("DEBUGFLAKE events", JSON.stringify(vi.mocked(trackEvent).mock.calls));
      console.error("DEBUGFLAKE testids", JSON.stringify([...(dialog?.querySelectorAll("[data-testid]") ?? [])].map((e) => e.getAttribute("data-testid"))));
      console.error("DEBUGFLAKE html", html.slice(0, 3000));
      throw err;
    }
    const calls = vi.mocked(trackEvent).mock.calls.filter(([name]) => name === "image_parsed");
    expect(calls).toHaveLength(1);
    const props = calls[0]![1] as Record<string, unknown>;
    expect(props).toEqual({
      kind: "receipt",
      outcome: "parsed",
      item_count: 4,
      duration_ms: expect.any(Number),
    });
    expect(JSON.stringify(calls)).not.toContain("secret-name");
  });

  it("reports a refusal for the monthly cap and an error for an outage", async () => {
    setImageConsent(true);
    answer(429, { detail: "x" }, { once: true });
    const { user } = await openSheet();
    await pick(user, "list", image());
    await screen.findByTestId("photo-error");
    await user.click(screen.getByTestId("photo-type"));
    await user.click(await screen.findByTestId("photo-open"));
    answer(503, { detail: "x" }, { once: true });
    await pick(user, "list", image());
    await screen.findByTestId("photo-error");
    const outcomes = vi
      .mocked(trackEvent)
      .mock.calls.filter(([name]) => name === "image_parsed")
      .map(([, p]) => (p as { outcome: string }).outcome);
    expect(outcomes).toEqual(["refused", "error"]);
  });
});

describe("the Profile toggle", () => {
  it("shows the consent, withdraws it at once, and the next photo asks again", async () => {
    setImageConsent(true);
    const user = userEvent.setup();
    const { unmount } = render(<ImageConsentToggle />);
    const toggle = screen.getByRole("switch", { name: "קריאת תמונות של קבלות ורשימות" });
    expect(toggle).toBeChecked();
    await user.click(toggle);
    expect(toggle).not.toBeChecked();
    expect(window.localStorage.getItem(IMAGE_CONSENT_KEY)).toBeNull();
    unmount();

    const next = await openSheet();
    await pick(next.user, "list", image());
    expect(await screen.findByTestId("photo-consent")).toBeVisible();
    expect(uploads).toEqual([]);
  });

  it("turning it on is the same yes as the sheet's", async () => {
    const user = userEvent.setup();
    render(<ImageConsentToggle />);
    const toggle = screen.getByRole("switch", { name: "קריאת תמונות של קבלות ורשימות" });
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    expect(toggle).toBeChecked();
    expect(getImageConsent()).toBe(true);
  });
});
