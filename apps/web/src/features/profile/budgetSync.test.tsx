/**
 * The monthly budget travels with the profile (#70): `PUT /me/profile` carries `monthly_budget`
 * only when the person changed it (omitted keeps the stored value, null clears it), and the
 * account's budget is adopted on a device that has none.
 */
import { render, waitFor } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { clearBudget, loadBudget, saveBudget } from "@/features/budget/budgetState";
import { resetMeMock } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { ProfileSync } from "./ProfileSync";
import { pushServerProfile, toProfileUpdate } from "./profileApi";
import { getProfile, resetProfileCache, updateProfile } from "./profileState";

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    status: "signed-in",
    email: "a@b.co",
    configured: true,
    openSignIn: () => {},
    signOut: async () => {},
  }),
}));

type Put = Record<string, unknown>;
const puts: Put[] = [];

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
  resetMeMock();
  puts.length = 0;
  server.events.on("request:start", async ({ request }) => {
    if (request.method === "PUT" && request.url.endsWith("/me/profile")) {
      puts.push((await request.clone().json()) as Put);
    }
  });
});

function mount() {
  return render(
    <ThemeProvider>
      <ProfileSync />
    </ThemeProvider>,
  );
}

/** The account already has a profile (with or without a budget). */
async function seedAccount(budget?: number | null) {
  const body = toProfileUpdate(getProfile());
  await pushServerProfile(budget === undefined ? body : { ...body, monthly_budget: budget });
  puts.length = 0;
}

describe("budget and the profile", () => {
  it("adopts the account's budget on a device that has none, without writing it back", async () => {
    await seedAccount(1800);
    mount();
    await waitFor(() => expect(loadBudget()).toBe(1800));
    await new Promise((r) => setTimeout(r, 1200)); // longer than the save debounce
    expect(puts).toEqual([]);
  });

  it("the account's budget replaces a different one on this device", async () => {
    await seedAccount(1800);
    saveBudget(2500);
    mount();
    await waitFor(() => expect(loadBudget()).toBe(1800));
  });

  it("offers the device's budget once when the account has none", async () => {
    await seedAccount(null);
    saveBudget(2500);
    mount();
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toMatchObject({ monthly_budget: 2500 });
  });

  it("a first save of a new account includes the budget, and none when there is none", async () => {
    saveBudget(2500);
    mount();
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toMatchObject({ monthly_budget: 2500 });
  });

  it("sends monthly_budget when it is changed or cleared, and omits it for other changes", async () => {
    await seedAccount(1800);
    mount();
    await waitFor(() => expect(loadBudget()).toBe(1800));

    saveBudget(2200);
    await waitFor(() => expect(puts).toHaveLength(1), { timeout: 4000 });
    expect(puts[0]).toMatchObject({ monthly_budget: 2200 });

    updateProfile({ radiusKm: 7 });
    await waitFor(() => expect(puts).toHaveLength(2), { timeout: 4000 });
    expect(puts[1]).toMatchObject({ radius_m: 7000 });
    expect("monthly_budget" in puts[1]!).toBe(false); // omitted keeps the stored value

    clearBudget();
    await waitFor(() => expect(puts).toHaveLength(3), { timeout: 4000 });
    expect(puts[2]).toHaveProperty("monthly_budget", null); // explicit null clears it
  });
});
