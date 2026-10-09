import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { getBetaMembership } from "@/api/client";
import { mockBetaFeedback, resetBetaMock, setBetaMockMember } from "@/mocks/handlers.beta";
import { server } from "@/mocks/node";
import { getTrackingConsent, resetTrackingForTests } from "@/features/seo/track";
import { BetaFeedbackEntry } from "./BetaFeedback";
import { BetaJoin } from "./BetaJoin";
import { getBetaState, resetBetaState } from "./betaState";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const auth = vi.hoisted(() => ({
  value: {
    status: "signed-out" as "loading" | "signed-in" | "signed-out",
    email: null as string | null,
    configured: false,
    openSignIn: () => {},
    signOut: async () => {},
  },
}));
vi.mock("@/features/auth/AuthProvider", () => ({ useAuth: () => auth.value }));

beforeAll(() => server.listen({ onUnhandledFrame: "bypass" }));
afterAll(() => server.close());

beforeEach(() => {
  auth.value = {
    status: "signed-out",
    email: null,
    configured: false,
    openSignIn: vi.fn(),
    signOut: async () => {},
  };
  localStorage.clear();
  resetTrackingForTests();
  resetBetaMock();
  resetBetaState();
});

afterEach(() => {
  server.resetHandlers();
  vi.unstubAllEnvs();
  Reflect.deleteProperty(navigator, "doNotTrack");
});

describe("the join page", () => {
  it("explains the beta in plain Hebrew: what is measured, the consent, what is stored, how to leave", async () => {
    render(<BetaJoin code="BETA-KOSHER" />);
    expect(await screen.findByTestId("beta-join")).toBeEnabled();
    const page = document.body;
    expect(page).toHaveTextContent("מה אנחנו מודדים");
    expect(page).toHaveTextContent("לא תחליף טוב");
    expect(page).toHaveTextContent("אירועי שימוש והסכמה");
    expect(page).toHaveTextContent("אפשר להצטרף גם בלי לאשר");
    expect(page).toHaveTextContent("מה נשמר עליך");
    expect(page).toHaveTextContent("בלי מזהה המשתמש שלך");
    expect(page).toHaveTextContent("איך יוצאים");
    expect(screen.getByRole("link", { name: "למדיניות הפרטיות" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });

  it("joins on a tap, never automatically, and shows the member's group", async () => {
    const user = userEvent.setup();
    render(<BetaJoin code="beta-kosher" />);
    await screen.findByTestId("beta-join");
    expect((await getBetaMembership()).member).toBe(false); // opening the link changed nothing
    await user.click(screen.getByTestId("beta-join"));
    expect(await screen.findByTestId("beta-member")).toHaveTextContent("שומרי כשרות");
    expect(getBetaState()).toMatchObject({ member: true, segment: "kosher" });
    expect(await getBetaMembership()).toEqual({ member: true, segment: "kosher" });
    expect(screen.queryByTestId("beta-join")).toBeNull();
  });

  it.each([
    ["NOPE-00000", "קוד ההזמנה לא מוכר"],
    ["BETA-EXPIRED", "פג תוקף או שכבר נוצלו"],
    ["BETA-FULL", "פג תוקף או שכבר נוצלו"],
  ])("a code that does not work (%s) says why and does not join", async (code, message) => {
    const user = userEvent.setup();
    render(<BetaJoin code={code} />);
    await user.click(await screen.findByTestId("beta-join"));
    expect(await screen.findByTestId("beta-error")).toHaveTextContent(message);
    expect(getBetaState().member).toBe(false);
    expect(screen.getByTestId("beta-join")).toBeEnabled();
  });

  it("signed out (Supabase configured) it asks to sign in first and offers no join button", async () => {
    auth.value = { ...auth.value, configured: true, status: "signed-out" };
    const user = userEvent.setup();
    render(<BetaJoin code="BETA-KOSHER" />);
    expect(screen.queryByTestId("beta-join")).toBeNull();
    await user.click(await screen.findByTestId("beta-sign-in"));
    expect(auth.value.openSignIn).toHaveBeenCalled();
    expect(getBetaState().member).toBe(false);
  });

  it("without a code (/beta) it says the beta is by invitation", async () => {
    render(<BetaJoin />);
    expect(await screen.findByTestId("beta-no-invite")).toHaveTextContent("בהזמנה");
    expect(screen.queryByTestId("beta-join")).toBeNull();
  });
});

describe("the events consent is part of joining", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1"));

  it("shows the consent screen before joining; accepting stores 1 and then joins", async () => {
    const user = userEvent.setup();
    render(<BetaJoin code="BETA-FAMILY" />);
    await user.click(await screen.findByTestId("beta-join"));
    const dialog = await screen.findByRole("dialog", { name: "עוזרות לנו לבדוק את ההחלפות?" });
    expect(dialog).toHaveTextContent("מה לא נשמר");
    expect(getBetaState().member).toBe(false); // not joined until the question is answered
    expect(localStorage.getItem("sc-events-consent")).toBeNull();
    await user.click(within(dialog).getByRole("button", { name: "אני מסכימה" }));
    expect(localStorage.getItem("sc-events-consent")).toBe("1");
    expect(await screen.findByTestId("beta-member")).toHaveTextContent("משפחות גדולות");
    expect(screen.getByTestId("beta-state")).toHaveTextContent("אירועי השימוש מופעלים");
  });

  it("declining the events still joins, with events off", async () => {
    const user = userEvent.setup();
    render(<BetaJoin code="BETA-PERIPHERY" />);
    await user.click(await screen.findByTestId("beta-join"));
    await user.click(await screen.findByRole("button", { name: "לא, תודה" }));
    expect(localStorage.getItem("sc-events-consent")).toBe("0");
    expect(await screen.findByTestId("beta-member")).toHaveTextContent("תושבי הפריפריה");
    expect(screen.getByTestId("beta-state")).toHaveTextContent("אירועי השימוש כבויים");
  });

  it("is not asked again when the question was already answered", async () => {
    localStorage.setItem("sc-events-consent", "1");
    const user = userEvent.setup();
    render(<BetaJoin code="BETA-GENERAL" />);
    await user.click(await screen.findByTestId("beta-join"));
    expect(await screen.findByTestId("beta-member")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("leaving the beta", () => {
  it("asks first, then deletes the membership and turns events off", async () => {
    vi.stubEnv("NEXT_PUBLIC_BETA_EVENTS", "1");
    localStorage.setItem("sc-events-consent", "1");
    setBetaMockMember("kosher");
    const user = userEvent.setup();
    render(<BetaJoin code="BETA-KOSHER" />);
    await user.click(await screen.findByTestId("beta-leave"));
    expect(screen.getByRole("group", { name: "יציאה מהבטא" })).toHaveTextContent(
      "הרישום שלך יימחק ואירועי השימוש ייכבו",
    );
    expect((await getBetaMembership()).member).toBe(true); // nothing happens on the first tap
    await user.click(screen.getByTestId("beta-leave-confirm"));
    await screen.findByTestId("beta-left");
    expect(screen.getByRole("heading", { name: "יצאת מהבטא" })).toBeInTheDocument();
    expect(await getBetaMembership()).toEqual({ member: false, segment: null });
    expect(getTrackingConsent()).toBe("declined");
    expect(localStorage.getItem("sc-events-consent")).toBe("0");
    expect(screen.queryByTestId("beta-member")).toBeNull();
    expect(
      within(screen.getByTestId("beta-state")).getByRole("link", { name: "לפרופיל" }),
    ).toHaveAttribute("href", "/profile");
  });

  it("cancelling the question keeps the membership", async () => {
    setBetaMockMember("general");
    const user = userEvent.setup();
    render(<BetaJoin />);
    await user.click(await screen.findByTestId("beta-leave"));
    await user.click(screen.getByRole("button", { name: "ביטול" }));
    expect(screen.queryByTestId("beta-leave-confirm")).toBeNull();
    expect(screen.getByTestId("beta-member")).toBeInTheDocument();
    expect((await getBetaMembership()).member).toBe(true);
  });
});

/** Paths the mock server was asked for while `fn` runs. */
async function requestedPaths(fn: () => Promise<void>): Promise<string[]> {
  const paths: string[] = [];
  const onStart = ({ request }: { request: Request }) => paths.push(new URL(request.url).pathname);
  server.events.on("request:start", onStart);
  try {
    await fn();
  } finally {
    server.events.removeListener("request:start", onStart);
  }
  return paths;
}

describe("the feedback entry", () => {
  beforeEach(() => {
    auth.value = { ...auth.value, status: "signed-in", email: "a@example.com" };
  });

  it("is invisible to anyone who is not a member", async () => {
    render(<BetaFeedbackEntry />);
    await waitFor(() => expect(getBetaState().status).toBe("ready"));
    expect(screen.queryByTestId("beta-feedback-entry")).toBeNull();
  });

  it("signed out in a build that cannot sign in, it renders nothing and never calls /me/beta", async () => {
    auth.value = { ...auth.value, configured: false, status: "signed-out", email: null };
    setBetaMockMember("kosher"); // even a mock that would say "member"
    const paths = await requestedPaths(async () => {
      render(<BetaFeedbackEntry />);
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(screen.queryByTestId("beta-feedback-entry")).toBeNull();
    expect(paths.filter((p) => p.includes("/me/"))).toEqual([]);
    expect(getBetaState().status).toBe("unknown");
  });

  it("does not show an earlier answer once the session is gone", async () => {
    setBetaMockMember("kosher");
    const { rerender } = render(<BetaFeedbackEntry />);
    expect(await screen.findByTestId("beta-feedback-entry")).toBeInTheDocument();
    auth.value = { ...auth.value, status: "signed-out", email: null };
    rerender(<BetaFeedbackEntry />);
    expect(screen.queryByTestId("beta-feedback-entry")).toBeNull();
    await waitFor(() => expect(getBetaState().status).toBe("unknown"));
  });

  it("is invisible while signed out with Supabase configured, without asking the API", async () => {
    auth.value = { ...auth.value, configured: true, status: "signed-out" };
    setBetaMockMember("kosher");
    render(<BetaFeedbackEntry />);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId("beta-feedback-entry")).toBeNull();
    expect(getBetaState().status).toBe("unknown");
  });

  it("members get 'משוב על הבטא'; a rating is required, then rating and text are sent", async () => {
    setBetaMockMember("periphery");
    const user = userEvent.setup();
    render(<BetaFeedbackEntry />);
    await user.click(await screen.findByRole("button", { name: "משוב על הבטא" }));
    const dialog = await screen.findByRole("dialog", { name: "משוב על הבטא" });
    expect(dialog).toHaveTextContent("אל תכתבי שם, טלפון, כתובת");

    await user.click(within(dialog).getByRole("button", { name: "שליחה" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("בחרי דירוג");
    expect(mockBetaFeedback()).toEqual([]);

    await user.click(within(dialog).getByRole("radio", { name: "4 מתוך 5" }));
    expect(within(dialog).queryByRole("alert")).toBeNull();
    await user.type(
      within(dialog).getByLabelText("מה עבד ומה לא? (לא חובה)"),
      "התחליף לגבינה מצוין",
    );
    await user.click(within(dialog).getByRole("button", { name: "שליחה" }));
    expect(await screen.findByTestId("beta-feedback-sent")).toHaveTextContent("בלי מזהה המשתמש");
    expect(mockBetaFeedback()).toEqual([
      { rating: 4, text: "התחליף לגבינה מצוין", segment: "periphery" },
    ]);
  });

  it("limits the text to 1000 characters and shows the count", async () => {
    setBetaMockMember("general");
    const user = userEvent.setup();
    render(<BetaFeedbackEntry />);
    await user.click(await screen.findByTestId("beta-feedback-entry"));
    const box = await screen.findByLabelText("מה עבד ומה לא? (לא חובה)");
    expect(box).toHaveAttribute("maxlength", "1000");
    await user.type(box, "abc");
    expect(screen.getByText("3 מתוך 1000 תווים")).toBeInTheDocument();
  });

  it("a failed send keeps the sheet open with an error", async () => {
    setBetaMockMember("general");
    const user = userEvent.setup();
    render(<BetaFeedbackEntry />);
    await user.click(await screen.findByTestId("beta-feedback-entry"));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("radio", { name: "2 מתוך 5" }));
    resetBetaMock(); // the server no longer knows the member: 403
    await user.click(within(dialog).getByRole("button", { name: "שליחה" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("לא הצלחנו לשלוח");
    expect(screen.queryByTestId("beta-feedback-sent")).toBeNull();
  });

  it("is also reachable from the join page for a member", async () => {
    setBetaMockMember("kosher");
    const user = userEvent.setup();
    render(<BetaJoin />);
    await user.click(await screen.findByTestId("beta-open-feedback"));
    expect(await screen.findByRole("dialog", { name: "משוב על הבטא" })).toBeInTheDocument();
  });
});
