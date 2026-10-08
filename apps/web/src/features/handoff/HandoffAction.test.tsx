import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { ResultsContent } from "@/features/compare/ResultsView";
import { optimizeFixture } from "@/mocks/fixtures";
import { server } from "@/mocks/node";
import { HandoffAction } from "./HandoffAction";
import { clearChainsOnlineCache } from "./useChainsOnline";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  clearChainsOnlineCache();
  window.localStorage.clear();
});

const NAMES = new Map<number, string>();

function renderResults() {
  return render(<ResultsContent res={optimizeFixture()} names={NAMES} onReportGap={() => {}} />);
}

const ACTION = "המשך באתר הרשת";

describe("cart handoff on the results cards", () => {
  it("shows the action only for enabled chains and opens the sheet", async () => {
    const user = userEvent.setup();
    renderResults();
    const single = screen.getByTestId("plan-single");
    const open = await within(single).findByRole("button", { name: /המשך באתר של רמי לוי/ });
    expect(open).toHaveTextContent(ACTION);
    // The split plan has rami_levy and osher_ad (both enabled in the mock), the home store shufersal.
    expect(await within(screen.getByTestId("plan-split")).findAllByText(ACTION)).toHaveLength(2);
    expect(
      await within(screen.getByTestId("plan-minimum_effort")).findAllByText(ACTION),
    ).toHaveLength(1);

    await user.click(open);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("הרשימה שלך ברמי לוי");
    // The disclaimer is always visible: online prices, availability, delivery fees, checkout governs.
    const disclaimer = within(dialog).getByTestId("handoff-disclaimer");
    expect(disclaimer).toHaveTextContent("המחירים, הזמינות ודמי המשלוח");
    expect(disclaimer).toHaveTextContent("המחיר הקובע הוא בקופה");
    expect(within(dialog).queryByTestId("handoff-referral-label")).toBeNull();
  });

  it("links to the chain's site and to its search for each item, safely", async () => {
    const user = userEvent.setup();
    renderResults();
    await user.click(
      await within(screen.getByTestId("plan-single")).findByRole("button", {
        name: /המשך באתר של רמי לוי/,
      }),
    );
    const dialog = await screen.findByRole("dialog");
    const site = within(dialog).getByTestId("handoff-site");
    expect(site).toHaveAttribute("href", "https://chain-shop.example/rami");
    expect(site).toHaveAttribute("target", "_blank");
    expect(site).toHaveAttribute("rel", "noopener noreferrer");

    const links = within(dialog).getAllByTestId("handoff-item-link");
    expect(links.length).toBeGreaterThan(3);
    const text = (within(dialog).getByTestId("handoff-text") as HTMLTextAreaElement).value;
    const lines = text.split("\n");
    expect(lines).toHaveLength(links.length);
    for (const [i, link] of links.entries()) {
      const href = link.getAttribute("href")!;
      expect(href.startsWith("https://chain-shop.example/rami/search?q=")).toBe(true);
      expect(href).not.toMatch(/[\s֐-׿]/); // Hebrew and spaces are percent-encoded
      const name = lines[i]!.split(" × ")[0]!;
      expect(new URL(href).searchParams.get("q")).toBe(name);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      expect(link).toHaveTextContent("חיפוש באתר");
    }
  });

  it("labels the links as partner links when the chain has a referral", async () => {
    const user = userEvent.setup();
    renderResults();
    await user.click(
      await within(screen.getByTestId("plan-minimum_effort")).findByRole("button", {
        name: /המשך באתר של שופרסל/,
      }),
    );
    const dialog = await screen.findByRole("dialog");
    const labels = within(dialog).getAllByTestId("handoff-referral-label");
    // One next to the site link and one next to every item link.
    expect(labels).toHaveLength(1 + within(dialog).getAllByTestId("handoff-item-link").length);
    expect(labels[0]).toHaveTextContent("קישור שותפים");
    expect(within(dialog).getByTestId("handoff-referral-note")).toHaveTextContent(
      "לא משפיע על הדירוג",
    );
  });

  it("has no per-item links when the chain has no site search", async () => {
    const user = userEvent.setup();
    renderResults();
    const split = screen.getByTestId("plan-split");
    await user.click(await within(split).findByRole("button", { name: /המשך באתר של אושר עד/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("handoff-site")).toHaveAttribute(
      "href",
      "https://chain-shop.example/osherad",
    );
    expect(within(dialog).queryByTestId("handoff-item-link")).toBeNull();
    expect(within(dialog).getByTestId("handoff-text")).toBeInTheDocument();
  });

  it("copies the list for that store, name × quantity per line", async () => {
    const user = userEvent.setup();
    renderResults();
    await user.click(
      await within(screen.getByTestId("plan-single")).findByRole("button", {
        name: /המשך באתר של רמי לוי/,
      }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByTestId("handoff-copy"));
    await within(dialog).findByTestId("handoff-copied");
    const copied = await navigator.clipboard.readText();
    expect(copied).toBe((within(dialog).getByTestId("handoff-text") as HTMLTextAreaElement).value);
    expect(copied.split("\n").every((l) => /^.+ × [\d.]+$/.test(l))).toBe(true);
  });

  it("selects the text for a manual copy when the clipboard is refused", async () => {
    const user = userEvent.setup();
    renderResults();
    await user.click(
      await within(screen.getByTestId("plan-single")).findByRole("button", {
        name: /המשך באתר של רמי לוי/,
      }),
    );
    const dialog = await screen.findByRole("dialog");
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    Object.defineProperty(document, "execCommand", { value: () => false, configurable: true });
    await user.click(within(dialog).getByTestId("handoff-copy"));
    expect(await within(dialog).findByTestId("handoff-copy-failed")).toBeInTheDocument();
    expect(within(dialog).queryByTestId("handoff-copied")).toBeNull();
  });

  it("offers the phone's share sheet only when the browser has one", async () => {
    const user = userEvent.setup();
    const share = vi.fn().mockResolvedValue(undefined);
    renderResults();
    await user.click(
      await within(screen.getByTestId("plan-single")).findByRole("button", {
        name: /המשך באתר של רמי לוי/,
      }),
    );
    expect(screen.queryByTestId("handoff-share")).toBeNull();
    await user.click(screen.getByRole("button", { name: "סגירה" }));

    Object.defineProperty(navigator, "share", { value: share, configurable: true });
    try {
      await user.click(
        within(screen.getByTestId("plan-single")).getByRole("button", {
          name: /המשך באתר של רמי לוי/,
        }),
      );
      await user.click(await screen.findByTestId("handoff-share"));
      expect(share).toHaveBeenCalledOnce();
      expect(share.mock.calls[0]![0].text).toContain(" × ");
    } finally {
      delete (navigator as unknown as Record<string, unknown>).share;
    }
  });

  it("shows nothing for a chain that is disabled or unknown", async () => {
    const store = { store_id: 1, chain_id: "victory", chain_name: "ויקטורי" };
    const { container } = render(<HandoffAction store={store} items={[]} />);
    // The list loaded (victory is in it, but disabled): still nothing.
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    render(<HandoffAction store={{ ...store, chain_id: "nope" }} items={[]} />);
    expect(screen.queryByText(ACTION)).toBeNull();
  });

  it("hides the action and leaves the results alone when /chains/online fails", async () => {
    const totals = () =>
      ["single", "split", "minimum_effort"].map(
        (k) => screen.getByTestId(`plan-${k}-total`).textContent,
      );
    const savings = () =>
      ["single", "split"].map((k) => screen.getByTestId(`plan-${k}-saving`).textContent);

    renderResults();
    await within(screen.getByTestId("plan-single")).findByText(ACTION);
    const withHandoff = { totals: totals(), savings: savings() };
    document.body.innerHTML = "";

    clearChainsOnlineCache();
    server.use(
      http.get(`${API_BASE_URL}/chains/online`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderResults();
    await waitFor(() => expect(screen.getByTestId("plan-single")).toBeInTheDocument());
    // Give the failed request time to settle, then check that nothing was added.
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(ACTION)).toBeNull();
    expect({ totals: totals(), savings: savings() }).toEqual(withHandoff);
  });
});
