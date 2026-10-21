import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetStorageMemoryForTests } from "@/state/storage";
import { STORAGE_KEYS } from "@/features/profile/storage";
import {
  clearSession,
  loadSession,
  sanitizeSession,
  saveSession,
  setChecked,
  type ShopItem,
  type ShoppingSession,
} from "./session";

const item = (over: Partial<ShopItem> = {}): ShopItem => ({
  itemId: 1,
  canonicalId: 1001,
  name: "חלב",
  isSubstitute: false,
  confidence: null,
  quantity: "1",
  uom: "unit",
  lineTotal: "6.90",
  shelfPrice: "6.90",
  isEstimated: false,
  promo: null,
  priceUpdatedAt: "2026-10-08T03:40:00Z",
  department: "dairy",
  saving: null,
  checked: false,
  ...over,
});

const session = (over: Partial<ShoppingSession> = {}): ShoppingSession => ({
  version: 1,
  storeId: 101,
  storeName: "רמי לוי",
  chainName: "רמי לוי",
  listName: null,
  startedAt: "2026-10-08T05:00:00Z",
  expiresAt: "2999-01-01T00:00:00Z",
  pricesUpdatedAt: "2026-10-08T03:40:00Z",
  missingCount: 0,
  overhead: 0,
  departmentsResolved: true,
  items: [item()],
  ...over,
});

beforeEach(() => {
  window.localStorage.clear();
  resetStorageMemoryForTests();
  clearSession();
});
afterEach(() => vi.restoreAllMocks());

describe("the in-store session read back from storage", () => {
  it("drops items the checklist cannot draw, keeps the rest", () => {
    const damaged = session({
      items: [
        item(),
        null as unknown as ShopItem,
        { itemId: "x" } as unknown as ShopItem,
        item({ itemId: 2, lineTotal: "abc" }),
        item({ itemId: 3, checked: "yes" as unknown as boolean }),
      ],
    });
    expect(sanitizeSession(damaged)?.items.map((i) => i.itemId)).toEqual([1]);
  });

  it("a session whose items are all damaged, or that is not a session, is no session", () => {
    expect(sanitizeSession(session({ items: [null as unknown as ShopItem] }))).toBeNull();
    expect(sanitizeSession(session({ storeId: "101" as unknown as number }))).toBeNull();
    expect(sanitizeSession(session({ expiresAt: undefined as unknown as string }))).toBeNull();
    for (const raw of [null, 5, "x", [], { version: 2 }]) expect(sanitizeSession(raw)).toBeNull();
    // An empty checklist is a session (a store with nothing to buy), not damage.
    expect(sanitizeSession(session({ items: [] }))?.items).toEqual([]);
  });

  it("loadSession never throws on garbage and does not render damaged items", () => {
    window.localStorage.setItem(
      STORAGE_KEYS.shopping,
      JSON.stringify(session({ items: [null as unknown as ShopItem, item({ itemId: 9 })] })),
    );
    expect(loadSession()?.items.map((i) => i.itemId)).toEqual([9]);
    window.localStorage.setItem(STORAGE_KEYS.shopping, "{broken");
    expect(loadSession()).toBeNull();
  });
});

describe("the in-store session when storage refuses writes", () => {
  it("the checklist still works for this page view: start, tick, read back", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    saveSession(session());
    expect(loadSession()?.items).toHaveLength(1);
    setChecked(1, true);
    expect(loadSession()?.items[0]?.checked).toBe(true);
  });
});
