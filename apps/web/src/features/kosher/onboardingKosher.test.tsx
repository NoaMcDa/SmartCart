import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetBetaState, setBetaMembership } from "@/features/beta/betaState";
import { OnboardingFlow } from "@/features/onboarding/OnboardingFlow";
import { getProfile, resetProfileCache } from "@/features/profile/profileState";

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
  resetBetaState();
});

describe("onboarding and the kosher beta segment", () => {
  it("the kosher segment gets a fourth step with the kosher setting; the others do not", async () => {
    const user = userEvent.setup();
    setBetaMembership(true, "kosher");
    render(<OnboardingFlow />);
    expect(screen.getByTestId("step-count")).toHaveTextContent("שלב 1 מתוך 4");
    expect(screen.getByText(/ארבע שאלות קצרות/)).toBeInTheDocument();
    for (let i = 0; i < 3; i += 1) await user.click(screen.getByTestId("onboarding-next"));
    expect(screen.getByRole("heading", { level: 2, name: "כשרות" })).toBeInTheDocument();
    expect(screen.getByLabelText("למה אנחנו שואלים")).toHaveTextContent(
      "ונגיד במפורש כשהכשרות לא ידועה",
    );
    await user.click(screen.getByRole("radio", { name: "מהדרין" }));
    await user.click(screen.getByTestId("onboarding-next")); // finish
    expect(getProfile().diet.kosherLevel).toBe("mehadrin");
    expect(getProfile().onboardingDone).toBe(true);
    expect(push).toHaveBeenCalledWith("/");
  });

  it("a member of another segment keeps the three steps", () => {
    setBetaMembership(true, "large_family");
    render(<OnboardingFlow />);
    expect(screen.getByTestId("step-count")).toHaveTextContent("שלב 1 מתוך 3");
    expect(screen.queryByText(/ארבע שאלות קצרות/)).toBeNull();
  });
});
