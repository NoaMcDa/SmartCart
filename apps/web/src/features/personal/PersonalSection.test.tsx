/**
 * Profile "התאמה אישית", the export and "delete my data" for the habits, and the privacy page's
 * paragraph (phase 3 personalization).
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import PrivacyPage from "@/app/(secondary)/privacy/page";
import { API_BASE_URL } from "@/api/config";
import { setApiToken } from "@/features/auth/apiAuth";
import { deleteMyData } from "@/features/profile/deleteData";
import { PrivacySection } from "@/features/profile/PrivacySection";
import { resetProfileCache } from "@/features/profile/profileState";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { LOCALE_KEY } from "@/i18n/locales";
import { resetMeMock } from "@/mocks/handlers";
import { mockPersonal, resetPersonalMock, seedPersonalMock } from "@/mocks/handlers.personal";
import { server } from "@/mocks/node";
import type { PersonalData } from "@/api/client";
import { PersonalSection } from "./PersonalSection";
import {
  PERSONAL_KEY,
  getPersonal,
  personalActions,
  resetPersonalStoreForTests,
} from "./personalState";
import { MILK, regularDoc, signal } from "./fixtures";

let authStatus: "signed-in" | "signed-out" = "signed-out";
const signOut = vi.fn(async () => {});
vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    status: authStatus,
    email: "a@b.co",
    configured: true,
    openSignIn: () => {},
    signOut,
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  document.cookie = `${LOCALE_KEY}=; path=/; max-age=0`;
  resetPersonalStoreForTests();
  resetPersonalMock();
  resetProfileCache();
  resetMeMock();
  setApiToken("test-token");
  authStatus = "signed-out";
  signOut.mockClear();
});

function withHistory() {
  personalActions.recordTrip({ kind: "finished", lines: [{ ref: MILK, quantity: 2 }] });
  personalActions.recordSignal("dairy.milk", "kept_brand");
}

describe("the Profile section", () => {
  it("has the two switches: learning on by default, value packs off", () => {
    render(<PersonalSection />);
    expect(screen.getByRole("heading", { name: "התאמה אישית" })).toBeInTheDocument();
    const learn = screen.getByRole("switch", { name: "ללמוד מהקניות שלי" });
    const packs = screen.getByRole("switch", { name: "להעדיף אריזות גדולות (משפחה גדולה)" });
    expect(learn).toHaveAttribute("aria-checked", "true");
    expect(packs).toHaveAttribute("aria-checked", "false");
  });

  it("each switch writes the preference, and turning learning off says what that means", async () => {
    const user = userEvent.setup();
    render(<PersonalSection />);
    await user.click(screen.getByRole("switch", { name: "להעדיף אריזות גדולות (משפחה גדולה)" }));
    expect(getPersonal().prefs.value_packs).toBe(true);
    expect(screen.queryByTestId("learn-off-note")).toBeNull();
    await user.click(screen.getByRole("switch", { name: "ללמוד מהקניות שלי" }));
    expect(getPersonal().prefs.learn).toBe(false);
    expect(screen.getByTestId("learn-off-note")).toHaveTextContent(
      "מה שכבר נשמר נשאר עד שתנקי אותו",
    );
    expect(JSON.parse(window.localStorage.getItem(PERSONAL_KEY)!).prefs).toMatchObject({
      learn: false,
      value_packs: true,
    });
  });

  it("says what is kept, and that it stays on the device without an account", () => {
    withHistory();
    render(<PersonalSection />);
    expect(screen.getByTestId("personal-stats")).toHaveTextContent(
      "קניות ורשימות שנשמרו: 1. סימוני מותג: 1.",
    );
    expect(screen.getByText("בלי חשבון, כל זה נשאר במכשיר הזה בלבד.")).toBeInTheDocument();
  });

  it("signed in, says it is also on the account and only the person can read it", () => {
    authStatus = "signed-in";
    render(<PersonalSection />);
    expect(screen.getByText(/נשמרים גם בחשבון שלך.*רק את יכולה לקרוא אותם/)).toBeInTheDocument();
  });

  it("clears what was learned, keeps the preferences, and announces it", async () => {
    const user = userEvent.setup();
    withHistory();
    personalActions.setPrefs({ value_packs: true });
    render(<PersonalSection />);
    await user.click(screen.getByTestId("personal-clear"));
    expect(getPersonal().trips).toEqual([]);
    expect(getPersonal().signals).toEqual([]);
    expect(getPersonal().prefs.value_packs).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent("מה שנלמד נמחק.");
    expect(screen.getByTestId("personal-clear")).toBeDisabled(); // nothing left to clear
  });

  it("signed in, clearing also empties the account copy", async () => {
    const user = userEvent.setup();
    authStatus = "signed-in";
    seedPersonalMock(regularDoc() as unknown as PersonalData);
    personalActions.replace(regularDoc());
    render(<PersonalSection />);
    await user.click(screen.getByTestId("personal-clear"));
    await waitFor(() => expect(mockPersonal()!.trips).toEqual([]));
  });

  it("signed in, a failed account clear says so and keeps the device cleared", async () => {
    const user = userEvent.setup();
    authStatus = "signed-in";
    server.use(
      http.put(`${API_BASE_URL}/me/personal`, () => HttpResponse.json({}, { status: 500 })),
    );
    personalActions.replace(regularDoc());
    render(<PersonalSection />);
    await user.click(screen.getByTestId("personal-clear"));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("לא הצלחנו למחוק את העותק בחשבון"),
    );
    expect(getPersonal().trips).toEqual([]);
  });

  it("is in Arabic too, labelled", () => {
    document.cookie = `${LOCALE_KEY}=ar; path=/`;
    render(
      <LocaleProvider>
        <PersonalSection />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "التخصيص" })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "التعلّم من مشترياتي" })).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: "تفضيل العبوات الكبيرة (عائلة كبيرة)" }),
    ).toBeInTheDocument();
  });
});

describe("the export", () => {
  it("includes the habits and the preferences", async () => {
    const user = userEvent.setup();
    withHistory();
    personalActions.setPrefs({ value_packs: true });
    let exported: unknown = null;
    URL.createObjectURL = vi.fn((blob: Blob) => {
      void blob.text().then((t) => {
        exported = JSON.parse(t);
      });
      return "blob:x";
    });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<PrivacySection />);
    await user.click(screen.getByRole("button", { name: /ייצוא/ }));
    await waitFor(() => expect(exported).not.toBeNull());
    const data = exported as { personalization: ReturnType<typeof getPersonal> };
    expect(data.personalization.prefs.value_packs).toBe(true);
    expect(data.personalization.trips).toHaveLength(1);
    expect(data.personalization.signals).toHaveLength(1);
    expect(data.personalization.refs[0]!.canonical_id).toBe(MILK.canonical_id);
  });
});

describe("delete my data", () => {
  it("anonymous: removes the habits from the device", async () => {
    withHistory();
    personalActions.setPrefs({ value_packs: true });
    const r = await deleteMyData({ signedIn: false, signOut });
    expect(r.ok).toBe(true);
    expect(window.localStorage.getItem(PERSONAL_KEY)).toBeNull();
    expect(getPersonal().trips).toEqual([]);
    expect(getPersonal().prefs.value_packs).toBe(false); // the preferences are personal data too
  });

  it("signed in: erases the account copy first, then the device", async () => {
    seedPersonalMock(regularDoc() as unknown as PersonalData);
    personalActions.replace(regularDoc());
    const r = await deleteMyData({ signedIn: true, signOut });
    expect(r.ok).toBe(true);
    expect(mockPersonal()).toBeNull();
    expect(window.localStorage.getItem(PERSONAL_KEY)).toBeNull();
  });

  it("signed in, when the account copy cannot be erased: nothing is cleared on the device", async () => {
    server.use(
      http.delete(`${API_BASE_URL}/me/personal`, () => HttpResponse.json({}, { status: 500 })),
    );
    personalActions.replace(regularDoc());
    const r = await deleteMyData({ signedIn: true, signOut });
    expect(r.ok).toBe(false);
    expect(getPersonal().trips.length).toBeGreaterThan(0);
  });
});

describe("the privacy page", () => {
  it("has a short paragraph on personalization, marked as awaiting legal review", () => {
    render(<PrivacyPage />);
    const section = document.querySelector('section[aria-labelledby="p-personal"]') as HTMLElement;
    expect(section).not.toBeNull();
    const s = within(section);
    expect(s.getByRole("heading", { level: 2 })).toHaveTextContent("התאמה אישית");
    s.getByText(/אין בזה מחירים, חנויות, מיקום או טקסט חופשי/);
    s.getByText(/בלי חשבון, שום דבר מזה לא יוצא מהמכשיר/);
    s.getByText(/לא משמש לדירוג תוצאות|לא לדירוג תוצאות/);
    s.getByText(/כלול בייצוא.*מחקי את הנתונים שלי/);
    expect(s.getByTestId("personal-privacy-legal")).toHaveTextContent("ממתין לבדיקה משפטית");
  });

  it("says nothing about selling or sponsored ranking beyond the existing promises", () => {
    render(<PrivacyPage />);
    const section = document.querySelector('section[aria-labelledby="p-personal"]') as HTMLElement;
    expect(section.textContent).toMatch(/לא נמכר ולא משותף/);
  });
});

it("a brand signal belongs to a category, never to a product name or a price", () => {
  personalActions.recordSignal("dairy.milk", "rejected_substitute");
  const stored = JSON.stringify(signal(1, "dairy.milk"));
  expect(stored).not.toMatch(/₪|price|store/);
  expect(Object.keys(getPersonal().signals[0]!).sort()).toEqual([
    "at",
    "id",
    "kind",
    "taxonomy_id",
  ]);
});
