import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider, __resetThemeStoreForTests } from "@/components/theme/ThemeProvider";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { setSupabaseForTests } from "@/features/auth/supabaseClient";
import { server } from "@/mocks/node";
import { ProfileScreen } from "./ProfileScreen";
import { recordSaving } from "./savingsHistory";
import { getProfile, resetProfileCache, updateProfile } from "./profileState";
import { STORAGE_KEYS } from "./storage";
import { getListState, listActions, resetListStoreForTests } from "@/state/list";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  resetListStoreForTests();
  __resetThemeStoreForTests();
  setSupabaseForTests(null); // signed out, no Supabase project (mock mode)
});

function renderProfile() {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <ProfileScreen />
      </AuthProvider>
    </ThemeProvider>,
  );
}

describe("profile", () => {
  it("shows every section, including the theme control (issue #63)", () => {
    renderProfile();
    expect(screen.getByRole("heading", { level: 1, name: "פרופיל" })).toBeInTheDocument();
    for (const name of [
      "חשבון",
      "החיסכון שלי",
      "מיקום ורדיוס",
      "רשתות ומועדונים",
      "איך אני קונה",
      "כשרות ותזונה",
      "ברירות מחדל לגמישות",
      "ערכת צבעים",
      "פרטיות ונתונים",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    const themeSection = screen.getByRole("region", { name: "ערכת צבעים" });
    expect(
      within(themeSection).getByRole("radiogroup", { name: "ערכת צבעים" }),
    ).toBeInTheDocument();
  });

  it("onboarding answers are shown and edits persist for the next comparison", async () => {
    updateProfile({
      radiusKm: 9,
      homeChainId: "yochananof",
      clubs: ["יוחננוף"],
      extraStopValue: 40,
    });
    const user = userEvent.setup();
    renderProfile();
    expect(screen.getByRole("slider", { name: "רדיוס חיפוש" })).toHaveValue("9");
    expect(screen.getByRole("button", { name: "הסופר שלי: יוחננוף" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "מועדון יוחננוף" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("slider", { name: "כמה שווה לך עצירה נוספת?" })).toHaveValue("40");

    await user.click(screen.getByRole("button", { name: "הסופר שלי: שופרסל" }));
    expect(getProfile().homeChainId).toBe("shufersal");
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEYS.profile)!).homeChainId).toBe(
      "shufersal",
    );
  });

  it("shows the baseline banner until a home chain is chosen", async () => {
    const user = userEvent.setup();
    renderProfile();
    expect(screen.getByTestId("baseline-banner")).toHaveTextContent("חיסכון נטו");
    await user.click(screen.getByRole("button", { name: "הסופר שלי: שופרסל" }));
    expect(screen.queryByTestId("baseline-banner")).not.toBeInTheDocument();
  });

  it("diet, kosher and allergens are stored and marked unverified", async () => {
    const user = userEvent.setup();
    renderProfile();
    const diet = screen.getByRole("region", { name: "כשרות ותזונה" });
    expect(within(diet).getByText("לא מאומת")).toBeInTheDocument();
    await user.click(within(diet).getByRole("radio", { name: "מהדרין" }));
    await user.click(within(diet).getByRole("switch", { name: "טבעוני" }));
    await user.click(within(diet).getByRole("button", { name: "שומשום" }));
    expect(getProfile().diet).toEqual({
      vegan: true,
      glutenFree: false,
      kosherLevel: "mehadrin",
      allergens: ["sesame"],
    });
  });

  it("flexibility defaults are listed with smart defaults, editable and resettable", async () => {
    const user = userEvent.setup();
    renderProfile();
    const section = screen.getByRole("region", { name: "ברירות מחדל לגמישות" });
    const toiletries = within(section).getByLabelText("טיפוח והיגיינה");
    const dairy = within(section).getByLabelText("מוצרי חלב וביצים");
    expect(toiletries).toHaveValue("exact"); // cosmetics default to exact (D4)
    expect(dairy).toHaveValue("any_brand"); // staples default to any brand
    const reset = within(section).getByRole("button", { name: "איפוס לברירות המחדל החכמות" });
    expect(reset).toBeDisabled();

    await user.selectOptions(dairy, "close");
    expect(getListState().flexDefaults).toEqual({ dairy: "close" });
    expect(reset).toBeEnabled();
    await user.selectOptions(toiletries, "any_brand");
    expect(getListState().flexDefaults).toEqual({ dairy: "close", toiletries: "any_brand" });
    // Choosing the smart default again stores nothing.
    await user.selectOptions(dairy, "any_brand");
    expect(getListState().flexDefaults).toEqual({ toiletries: "any_brand" });

    await user.click(reset);
    expect(getListState().flexDefaults).toEqual({});
    expect(within(section).getByLabelText("טיפוח והיגיינה")).toHaveValue("exact");
  });

  it("includes categories saved from the list builder ('remember this for all milk')", () => {
    listActions.setFlexDefault("dairy.milk", "exact");
    renderProfile();
    const section = screen.getByRole("region", { name: "ברירות מחדל לגמישות" });
    expect(within(section).getByLabelText(/חלב ומשקאות חלב/)).toHaveValue("exact");
  });

  it("my savings: an empty state first, then only realized savings, never an inflated figure", () => {
    const { unmount } = renderProfile();
    expect(screen.getByTestId("savings-empty")).toHaveTextContent("אנחנו לא מציגים הערכות");
    unmount();
    recordSaving({ storeName: "רמי לוי · מודיעין", listName: null, net: 41 });
    recordSaving({ storeName: "אושר עד · מודיעין", listName: null, net: 12.5 });
    renderProfile();
    expect(screen.getByTestId("savings-total")).toHaveTextContent("₪ 53.50");
    expect(screen.getByTestId("savings-total")).toHaveTextContent("מול החנות שלך, אחרי נסיעה");
  });

  it("privacy: statement, consent toggle, link to the policy", async () => {
    updateProfile({
      consentLocation: true,
      location: { lat: 31.9, lon: 35.0, city: null, neighborhood: null, source: "manual" },
    });
    const user = userEvent.setup();
    renderProfile();
    const privacy = screen.getByRole("region", { name: "פרטיות ונתונים" });
    expect(within(privacy).getByTestId("privacy-statement")).toHaveTextContent("לא מוכרים מידע");
    expect(within(privacy).getByRole("link", { name: "למדיניות הפרטיות המלאה" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    const consent = within(privacy).getByRole("switch", { name: "שימוש במיקום" });
    expect(consent).toHaveAttribute("aria-checked", "true");
    await user.click(consent);
    expect(getProfile().consentLocation).toBe(false);
    expect(getProfile().location).toBeNull();
  });

  it("delete my data needs confirmation, then clears the device", async () => {
    updateProfile({ homeChainId: "shufersal", radiusKm: 11 });
    recordSaving({ storeName: "x", listName: null, net: 5 });
    const user = userEvent.setup();
    renderProfile();
    await user.click(screen.getByRole("button", { name: "מחקי את הנתונים שלי" }));
    const dialog = screen.getByRole("dialog", { name: "למחוק את כל הנתונים שלי?" });
    // Cancelling changes nothing.
    await user.click(within(dialog).getByRole("button", { name: "ביטול" }));
    expect(getProfile().radiusKm).toBe(11);

    await user.click(screen.getByRole("button", { name: "מחקי את הנתונים שלי" }));
    await user.click(screen.getByTestId("confirm-delete"));
    expect(await screen.findByTestId("delete-done")).toHaveTextContent("הנתונים נמחקו מהמכשיר");
    expect(getProfile().radiusKm).toBe(5);
    expect(getProfile().homeChainId).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEYS.savings)).toBeNull();
  });

  it("signed out without Supabase: the sign-in sheet explains, the app still works", async () => {
    const user = userEvent.setup();
    renderProfile();
    await user.click(screen.getByRole("button", { name: "התחברות עם אימייל" }));
    expect(await screen.findByTestId("auth-unavailable")).toHaveTextContent("בלי חשבון");
  });
});
