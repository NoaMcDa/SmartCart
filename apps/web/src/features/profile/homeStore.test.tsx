/**
 * "הסופר שלי" resolves to a concrete store (issue #101): picking a chain asks
 * `GET /stores/nearest` for the chain's nearest store to the profile's location, stores its id as
 * `homeStoreId`, and the comparison reads it as `home_store_id` (the baseline of the net saving, D7).
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { server } from "@/mocks/node";
import { readShopper, shopperRequestFields } from "@/state/shopper";
import { CHAINS, chainById } from "./chains";
import { ChainControls } from "./controls/ChainControls";
import {
  adoptHomeStore,
  adoptNearestHomeStore,
  getProfile,
  resetProfileCache,
  useResolveHomeStore,
  setLocation,
  updateProfile,
} from "./profileState";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  server.events.removeAllListeners();
});
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetProfileCache();
});

/** The queries `/stores/nearest` received. */
function recordNearest() {
  const seen: Array<{ chain_id: string | null; lat: string | null; lon: string | null }> = [];
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    if (url.pathname === "/stores/nearest") {
      seen.push({
        chain_id: url.searchParams.get("chain_id"),
        lat: url.searchParams.get("lat"),
        lon: url.searchParams.get("lon"),
      });
    }
  });
  return seen;
}

describe("chain ids", () => {
  it("every chain has the API id of the transparency files, and they are all different", () => {
    for (const chain of CHAINS) expect(chain.apiId).toMatch(/^7290\d{9}$/);
    expect(new Set(CHAINS.map((c) => c.apiId)).size).toBe(CHAINS.length);
    expect(chainById("rami_levy")?.apiId).toBe("7290058140886");
  });
});

describe("adoptNearestHomeStore", () => {
  it("asks for the chain's nearest store to the profile's location and stores it as the home store", async () => {
    setLocation({ lat: 31.8971, lon: 35.0099, source: "manual" });
    updateProfile({ homeChainId: "yochananof", homeStoreId: null });
    const seen = recordNearest();
    await expect(adoptNearestHomeStore("yochananof")).resolves.toBe(104);
    expect(seen).toEqual([{ chain_id: "7290803800003", lat: "31.897", lon: "35.01" }]); // rounded
    expect(getProfile().homeStoreId).toBe(104);
    // The comparison reads it: the next /optimize and /compare carry home_store_id 104.
    expect(readShopper().homeStoreId).toBe(104);
    expect(shopperRequestFields(readShopper()).home_store_id).toBe(104);
  });

  it("uses the default city when no location is set", async () => {
    updateProfile({ homeChainId: "rami_levy", homeStoreId: null });
    const seen = recordNearest();
    await expect(adoptNearestHomeStore("rami_levy")).resolves.toBe(101);
    expect(seen[0]).toMatchObject({ lat: "31.898", lon: "35.01" });
  });

  it("does not overwrite the pick when the shopper changed it while the request ran", async () => {
    updateProfile({ homeChainId: "yochananof", homeStoreId: null });
    server.use(
      http.get(`${API_BASE_URL}/stores/nearest`, async () => {
        // The shopper clears the pick before the answer arrives.
        updateProfile({ homeChainId: null, homeStoreId: null });
        return HttpResponse.json({ store_id: 104, chain_id: "7290803800003" });
      }),
    );
    await expect(adoptNearestHomeStore("yochananof")).resolves.toBeNull();
    expect(getProfile()).toMatchObject({ homeChainId: null, homeStoreId: null });
  });

  it("leaves the profile alone when the chain has no store (404) or the call fails, so the compare fallback still works", async () => {
    updateProfile({ homeChainId: "king_store", homeStoreId: null });
    await expect(adoptNearestHomeStore("king_store")).resolves.toBeNull(); // the mock has none
    expect(getProfile().homeStoreId).toBeNull();
    server.use(http.get(`${API_BASE_URL}/stores/nearest`, () => HttpResponse.error()));
    await expect(adoptNearestHomeStore("king_store")).resolves.toBeNull();
    expect(getProfile().homeStoreId).toBeNull();
    // Later, a compare result that lists the chain's stores fills it in.
    const stores = [
      { store_id: 9, chain_id: "king_store", chain_name: "קינג סטור", distance_m: 3000 },
    ];
    expect(adoptHomeStore(stores)).toBe(true);
    expect(getProfile().homeStoreId).toBe(9);
  });

  it("knows no chain it was not given", async () => {
    await expect(adoptNearestHomeStore("not-a-chain")).resolves.toBeNull();
  });
});

describe("the results page keeps the home store resolved", () => {
  function Probe({ stores }: { stores?: Parameters<typeof useResolveHomeStore>[0] }) {
    useResolveHomeStore(stores);
    return null;
  }

  it("looks the chain up when the profile has a chain and no store (first results page already has a baseline)", async () => {
    updateProfile({ homeChainId: "victory", homeStoreId: null });
    const seen = recordNearest();
    render(<Probe />);
    await waitFor(() => expect(getProfile().homeStoreId).toBe(105));
    expect(readShopper().homeStoreId).toBe(105);
    expect(seen).toHaveLength(1);
  });

  it("asks once per chain, not on every render", async () => {
    updateProfile({ homeChainId: "king_store", homeStoreId: null });
    const seen = recordNearest();
    const view = render(<Probe />);
    await waitFor(() => expect(seen).toHaveLength(1));
    view.rerender(<Probe />);
    view.rerender(<Probe />);
    await new Promise((r) => setTimeout(r, 30));
    expect(seen).toHaveLength(1);
  });

  it("falls back to the stores of the result on screen when the lookup finds none", async () => {
    updateProfile({ homeChainId: "king_store", homeStoreId: null });
    const stores = [
      { store_id: 9, chain_id: "king_store", chain_name: "קינג סטור", distance_m: 3000 },
      { store_id: 3, chain_id: "shufersal", chain_name: "שופרסל", distance_m: 500 },
    ];
    render(<Probe stores={stores} />);
    await waitFor(() => expect(getProfile().homeStoreId).toBe(9));
  });

  it("does nothing without a chain, and never replaces a store that is already set", async () => {
    updateProfile({ homeChainId: null, homeStoreId: null });
    const seen = recordNearest();
    const view = render(<Probe />);
    await new Promise((r) => setTimeout(r, 30));
    expect(seen).toHaveLength(0);
    expect(getProfile().homeStoreId).toBeNull();
    view.unmount();
    updateProfile({ homeChainId: "victory", homeStoreId: 777 });
    render(
      <Probe
        stores={[{ store_id: 5, chain_id: "victory", chain_name: "ויקטורי", distance_m: 1 }]}
      />,
    );
    await new Promise((r) => setTimeout(r, 30));
    expect(getProfile().homeStoreId).toBe(777);
  });
});

describe("picking the chain in the controls", () => {
  it("resolves the store after the tap, replaces it when another chain is picked, clears it with the chain", async () => {
    const user = userEvent.setup();
    render(<ChainControls />);
    await user.click(screen.getByRole("button", { name: "הסופר שלי: יוחננוף" }));
    expect(getProfile().homeChainId).toBe("yochananof");
    await waitFor(() => expect(getProfile().homeStoreId).toBe(104));
    expect(readShopper().homeStoreId).toBe(104);

    // Another chain: the old store is dropped at once, then the new one arrives.
    await user.click(screen.getByRole("button", { name: "הסופר שלי: ויקטורי" }));
    expect(getProfile()).toMatchObject({ homeChainId: "victory" });
    await waitFor(() => expect(getProfile().homeStoreId).toBe(105));

    // Tapping the selected chain again unselects it and leaves no store (no baseline, D7).
    await user.click(screen.getByRole("button", { name: "הסופר שלי: ויקטורי" }));
    expect(getProfile()).toMatchObject({ homeChainId: null, homeStoreId: null });
    expect(readShopper().homeStoreId).toBeNull();
  });

  it("a chain the API has no store for stays selected without a store and says no saving is shown", async () => {
    const user = userEvent.setup();
    render(<ChainControls />);
    await user.click(screen.getByRole("button", { name: "הסופר שלי: קינג סטור" }));
    await waitFor(() => expect(getProfile().homeChainId).toBe("king_store"));
    expect(getProfile().homeStoreId).toBeNull();
    expect(readShopper().homeStoreId).toBeNull();
  });
});
