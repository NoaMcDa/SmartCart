import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getProfile, resetProfileCache } from "@/features/profile/profileState";
import { STORAGE_KEYS } from "@/features/profile/storage";
import { OnboardingFlow } from "./OnboardingFlow";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));

beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  push.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  Object.defineProperty(navigator, "geolocation", { value: undefined, configurable: true });
});

function stubGeolocation(impl: (ok: PositionCallback, fail: PositionErrorCallback) => void) {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition: impl },
  });
}

describe("onboarding", () => {
  it("every step explains why it asks, and the progress is announced", () => {
    render(<OnboardingFlow />);
    expect(screen.getByRole("heading", { level: 1, name: "ברוכים הבאים" })).toBeInTheDocument();
    expect(screen.getByTestId("step-count")).toHaveTextContent("שלב 1 מתוך 3");
    expect(screen.getByLabelText("למה אנחנו שואלים")).toHaveTextContent("מעוגל");
    expect(screen.getByRole("link", { name: "מדיניות הפרטיות" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });

  it("each step can be skipped; skipping all three leaves the defaults and no baseline store", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    for (const why of ["מעוגל", "חנות בסיס", "נסיעה"]) {
      expect(screen.getByLabelText("למה אנחנו שואלים")).toHaveTextContent(why);
      await user.click(screen.getByTestId("onboarding-skip"));
    }
    expect(push).toHaveBeenCalledWith("/");
    const p = getProfile();
    expect(p).toMatchObject({
      onboardingDone: true,
      location: null,
      homeChainId: null,
      homeStoreId: null,
      radiusKm: 5,
      travelMode: "car",
      extraStopValue: 25,
    });
  });

  it("step 1: declining the device location falls back to city and neighborhood", async () => {
    stubGeolocation((_ok, fail) =>
      fail({
        code: 1,
        message: "denied",
        PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2,
        TIMEOUT: 3,
      }),
    );
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    expect(screen.queryByTestId("manual-location")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }));
    expect(await screen.findByText(/לא קיבלנו הרשאת מיקום/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("עיר"), "מודיעין");
    await user.type(screen.getByLabelText("שכונה (לא חובה)"), "בויאר");
    await user.click(screen.getByRole("button", { name: "שמירת העיר" }));
    expect(getProfile().location).toEqual({
      lat: 31.897,
      lon: 35.01,
      city: "מודיעין-מכבים-רעות",
      neighborhood: "בויאר",
      source: "manual",
    });
    expect(getProfile().consentLocation).toBe(true);
    // The next step is still reachable.
    await user.click(screen.getByTestId("onboarding-next"));
    expect(screen.getByTestId("step-count")).toHaveTextContent("שלב 2 מתוך 3");
  });

  it("step 1: the device location is stored rounded to 3 decimals, and only after the click", async () => {
    let asked = 0;
    stubGeolocation((ok) => {
      asked += 1;
      ok({
        coords: { latitude: 32.08531234, longitude: 34.78189876 },
      } as GeolocationPosition);
    });
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    expect(asked).toBe(0); // nothing is requested before the user agrees
    await user.click(screen.getByRole("button", { name: "אישור שימוש במיקום המכשיר" }));
    expect(asked).toBe(1);
    expect(getProfile().location).toMatchObject({ lat: 32.085, lon: 34.782, source: "device" });
    const raw = window.localStorage.getItem(STORAGE_KEYS.profile)!;
    expect(raw).not.toContain("32.08531234");
    expect(raw).not.toContain("34.78189876");
    expect(screen.getByTestId("location-summary")).toHaveTextContent("מעוגל לשכונה");
  });

  it("step 1: the radius slider is 1 to 15 km and is announced", () => {
    render(<OnboardingFlow />);
    const slider = screen.getByRole("slider", { name: "רדיוס חיפוש" });
    expect(slider).toHaveAttribute("min", "1");
    expect(slider).toHaveAttribute("max", "15");
    expect(slider).toHaveAttribute("aria-valuetext", "5 קילומטרים");
    fireEvent.change(slider, { target: { value: "12" } });
    expect(getProfile().radiusKm).toBe(12);
    expect(slider).toHaveAttribute("aria-valuetext", "12 קילומטרים");
    expect(slider.closest("div")?.querySelector("output")).toHaveTextContent("12");
  });

  it("step 2: one home chain at a time, several clubs, selection shown by icon and state", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    await user.click(screen.getByTestId("onboarding-next"));
    const chains = within(screen.getByTestId("home-chain-cards"));
    await user.click(chains.getByRole("button", { name: "הסופר שלי: שופרסל" }));
    expect(chains.getByRole("button", { name: "הסופר שלי: שופרסל" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(chains.getByRole("button", { name: "הסופר שלי: רמי לוי" }));
    expect(chains.getByRole("button", { name: "הסופר שלי: שופרסל" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(chains.getAllByRole("button", { pressed: true })).toHaveLength(1);
    expect(getProfile().homeChainId).toBe("rami_levy");

    const clubs = within(screen.getByTestId("club-cards"));
    await user.click(clubs.getByRole("button", { name: "מועדון שופרסל" }));
    await user.click(clubs.getByRole("button", { name: "מועדון רמי לוי" }));
    expect(getProfile().clubs).toEqual(["שופרסל", "רמי לוי"]);
    await user.click(clubs.getByRole("button", { name: "מועדון שופרסל" }));
    expect(getProfile().clubs).toEqual(["רמי לוי"]);
  });

  it("the baseline hint is visible until a home chain is picked", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    await user.click(screen.getByTestId("onboarding-next"));
    expect(screen.getByTestId("baseline-hint")).toHaveTextContent("חיסכון נטו");
    await user.click(screen.getByRole("button", { name: "הסופר שלי: ויקטורי" }));
    expect(screen.queryByTestId("baseline-hint")).not.toBeInTheDocument();
  });

  it("step 3: travel mode and an extra-stop slider from 0 to 50 shown as a price", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    await user.click(screen.getByTestId("onboarding-next"));
    await user.click(screen.getByTestId("onboarding-next"));
    await user.click(screen.getByRole("radio", { name: "הליכה או תחבורה" }));
    expect(getProfile().travelMode).toBe("walk_transit");
    const slider = screen.getByRole("slider", { name: "כמה שווה לך עצירה נוספת?" });
    expect(slider).toHaveAttribute("min", "0");
    expect(slider).toHaveAttribute("max", "50");
    fireEvent.change(slider, { target: { value: "35" } });
    expect(getProfile().extraStopValue).toBe(35);
    const out = slider.closest("div")!.querySelector("output")!;
    expect(out.querySelector('span[dir="ltr"]')).toHaveTextContent("₪ 35");
    expect(slider).toHaveAttribute("aria-valuetext", "35 שקלים");
    await user.click(screen.getByTestId("onboarding-next"));
    expect(push).toHaveBeenCalledWith("/");
    expect(getProfile().onboardingDone).toBe(true);
  });

  it("back goes to the previous step", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow />);
    expect(screen.queryByRole("button", { name: "חזרה" })).not.toBeInTheDocument();
    await user.click(screen.getByTestId("onboarding-next"));
    await user.click(screen.getByRole("button", { name: "חזרה" }));
    expect(screen.getByTestId("step-count")).toHaveTextContent("שלב 1 מתוך 3");
  });
});
