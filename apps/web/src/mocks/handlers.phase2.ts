/**
 * MSW handlers for the phase 2 routes (issues #13, #23, #28, #34, #39, #45, #90). Minimal but
 * realistic fixtures so the web workstreams can build before services/api implements them.
 * Numbers follow the documented mock set (home store שופרסל דיל 103, רמי לוי 101).
 */
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type { Schemas } from "@/api/client";
import { canonicalRef, HOME_STORE_ID, PRICES_UPDATED_AT } from "./fixtures";

type StoreRef = Schemas["StoreRef"];
type PriceAlert = Schemas["PriceAlert"];
type PriceAlertIn = Schemas["PriceAlertIn"];
type PriceHistoryResponse = Schemas["PriceHistoryResponse"];
type BarcodeLookupResponse = Schemas["BarcodeLookupResponse"];
type SwapSuggestionResponse = Schemas["SwapSuggestionResponse"];
type ShareInvite = Schemas["ShareInvite"];
type ListMember = Schemas["ListMember"];
type ShoppingList = Schemas["ShoppingList"];
type Ack = Schemas["Ack"];

const url = (path: string) => `${API_BASE_URL}${path}`;

const STORE_REFS: Record<number, StoreRef> = {
  101: {
    store_id: 101,
    chain_id: "7290058140886",
    chain_name: "רמי לוי",
    store_name: "מודיעין",
    city: "מודיעין",
    distance_m: 4200,
    lat: 31.9,
    lon: 35.01,
    channel: "physical",
  },
  102: {
    store_id: 102,
    chain_id: "7290103152017",
    chain_name: "אושר עד",
    store_name: "מודיעין",
    city: "מודיעין",
    distance_m: 5100,
    lat: 31.905,
    lon: 35.0,
    channel: "physical",
  },
  103: {
    store_id: 103,
    chain_id: "7290027600007",
    chain_name: "שופרסל דיל",
    store_name: "מודיעין",
    city: "מודיעין",
    distance_m: 1100,
    lat: 31.898,
    lon: 35.008,
    channel: "physical",
  },
  104: {
    store_id: 104,
    chain_id: "7290803800003",
    chain_name: "יוחננוף",
    store_name: "מודיעין",
    city: "מודיעין",
    distance_m: 3600,
    lat: 31.9,
    lon: 35.02,
    channel: "physical",
  },
  105: {
    store_id: 105,
    chain_id: "7290696200003",
    chain_name: "ויקטורי",
    store_name: "מודיעין",
    city: "מודיעין",
    distance_m: 2400,
    lat: 31.896,
    lon: 35.015,
    channel: "physical",
  },
};

let alerts: PriceAlert[] = [];
let nextAlertId = 1;
/** Pending and accepted shares per list; `token` is the invite token, kept out of `ListMember`. */
let shares: Record<number, Array<ListMember & { token: string }>> = {};
let nextShareId = 1;
let nextMemberId = 1;

const publicMember = ({ token: _token, ...member }: ListMember & { token: string }): ListMember =>
  member;

/** Deterministic 90-day history: a slow drift plus two promo dips. */
function historyFixture(
  canonicalId: number,
  storeId: number | null,
  days: number,
): PriceHistoryResponse {
  const end = new Date(PRICES_UPDATED_AT);
  const base = 650 + (canonicalId % 7) * 40; // agorot per unit
  const points = [];
  for (let d = days; d >= 0; d -= 3) {
    const date = new Date(end.getTime() - d * 86_400_000);
    const promo = d % 42 < 6; // a promo window about every six weeks
    const price = promo ? Math.round(base * 0.8) : base + Math.round(Math.sin(d / 9) * 20);
    points.push({
      date: date.toISOString(),
      unit_price: (price / 100).toFixed(2),
      shelf_price: ((price * 10) / 100).toFixed(2),
      store_id: storeId,
      promo_description: promo ? "1+1 על המוצר" : null,
    });
  }
  return {
    canonical_id: canonicalId,
    store_id: storeId,
    days,
    points,
    promos: [
      {
        starts_at: new Date(end.getTime() - 48 * 86_400_000).toISOString(),
        ends_at: new Date(end.getTime() - 42 * 86_400_000).toISOString(),
        description: "1+1 על המוצר",
      },
      {
        starts_at: new Date(end.getTime() - 6 * 86_400_000).toISOString(),
        ends_at: end.toISOString(),
        description: "1+1 על המוצר",
      },
    ],
    generated_at: end.toISOString(),
  };
}

export const phase2Handlers = [
  http.delete(url("/me"), () => HttpResponse.json({ ok: true, id: null } satisfies Ack)),

  http.get(url("/stores/nearest"), ({ request }) => {
    // One fixture store per chain, as the compare fixtures have; any other chain has none (404,
    // like the API for a chain without a physical store).
    const chainId = new URL(request.url).searchParams.get("chain_id");
    const hit = Object.values(STORE_REFS).find((s) => s.chain_id === chainId);
    if (!hit) {
      return HttpResponse.json({ detail: "no physical store of this chain" }, { status: 404 });
    }
    return HttpResponse.json(hit);
  }),

  http.get(url("/history/:canonicalId"), ({ params, request }) => {
    const q = new URL(request.url).searchParams;
    const storeId = q.get("store_id") ? Number(q.get("store_id")) : null;
    const days = Number(q.get("days") ?? 90);
    return HttpResponse.json(historyFixture(Number(params.canonicalId), storeId, days));
  }),

  http.get(url("/me/alerts"), () => HttpResponse.json(alerts)),
  http.post(url("/me/alerts"), async ({ request }) => {
    const body = (await request.json()) as PriceAlertIn;
    const alert: PriceAlert = {
      id: nextAlertId++,
      canonical_id: body.canonical_id,
      threshold_unit_price: String(body.threshold_unit_price),
      flex_level: body.flex_level ?? "any_brand",
      radius_m: body.radius_m ?? 5000,
      active: true,
      last_fired_at: null,
      created_at: new Date().toISOString(),
    };
    alerts = [...alerts, alert];
    return HttpResponse.json(alert, { status: 201 });
  }),
  http.delete(url("/me/alerts/:id"), ({ params }) => {
    alerts = alerts.filter((a) => a.id !== Number(params.id));
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(url("/me/push-subscriptions"), () =>
    HttpResponse.json({ ok: true, id: 1 } satisfies Ack, { status: 201 }),
  ),

  http.post(url("/me/lists/:listId/share"), async ({ params, request }) => {
    const body = (await request.json().catch(() => ({}))) as { role?: "editor" | "viewer" };
    const listId = Number(params.listId);
    const token = `inv-${listId}-${Math.random().toString(36).slice(2, 10)}`;
    shares[listId] = [
      ...(shares[listId] ?? []),
      {
        user_id: null,
        role: body.role ?? "editor",
        accepted_at: null,
        is_owner: false,
        share_id: nextShareId++,
        token,
      },
    ];
    const invite: ShareInvite = {
      list_id: listId,
      token,
      url: `/lists/accept/${token}`,
      role: body.role ?? "editor",
    };
    return HttpResponse.json(invite, { status: 201 });
  }),
  http.get(url("/me/lists/:listId/members"), ({ params }) => {
    const listId = Number(params.listId);
    const members: ListMember[] = [
      {
        user_id: "me",
        role: "editor",
        accepted_at: PRICES_UPDATED_AT,
        is_owner: true,
        share_id: null,
      },
      ...(shares[listId] ?? []).map(publicMember),
    ];
    return HttpResponse.json(members);
  }),
  // Revoke a pending invite or remove a member by the list_shares id (`ListMember.share_id`).
  http.delete(url("/me/lists/:listId/shares/:shareId"), ({ params }) => {
    const listId = Number(params.listId);
    const shareId = Number(params.shareId);
    const before = shares[listId] ?? [];
    if (!before.some((m) => m.share_id === shareId)) {
      return HttpResponse.json({ detail: "share not found" }, { status: 404 });
    }
    shares[listId] = before.filter((m) => m.share_id !== shareId);
    return new HttpResponse(null, { status: 204 });
  }),
  // The older owner routes: cancel by token, remove a member by user id.
  http.delete(url("/me/lists/:listId/share/:token"), ({ params }) => {
    const listId = Number(params.listId);
    shares[listId] = (shares[listId] ?? []).filter((m) => m.token !== params.token);
    return new HttpResponse(null, { status: 204 });
  }),
  http.delete(url("/me/lists/:listId/members/:memberId"), ({ params }) => {
    const listId = Number(params.listId);
    shares[listId] = (shares[listId] ?? []).filter((m) => m.user_id !== params.memberId);
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(url("/lists/accept/:token"), ({ params }) => {
    const listId = Number(String(params.token).split("-")[1] ?? 1);
    // The invite becomes a member (the owner then sees "remove" instead of "revoke").
    shares[listId] = (shares[listId] ?? []).map((m) =>
      m.token === params.token && m.user_id === null
        ? { ...m, user_id: `member-${nextMemberId++}`, accepted_at: new Date().toISOString() }
        : m,
    );
    const now = new Date().toISOString();
    const list: ShoppingList = {
      id: listId,
      name: "הקנייה השבועית (משותפת)",
      is_recurring: true,
      items: [
        {
          id: listId * 1000 + 1,
          sort: 0,
          canonical_id: 1001,
          confirmed: true,
          flex_level: "any_brand",
          input_text: null,
          quantity: "2",
          checked: false,
        },
        {
          id: listId * 1000 + 2,
          sort: 1,
          canonical_id: 1004,
          confirmed: true,
          flex_level: "any_brand",
          input_text: null,
          quantity: "1",
          checked: false,
        },
      ],
      created_at: now,
      updated_at: now,
      shared: true,
      role: "editor",
    };
    return HttpResponse.json(list);
  }),

  http.get(url("/items/barcode/:barcode"), ({ params, request }) => {
    const q = new URL(request.url).searchParams;
    const storeId = q.get("store_id") ? Number(q.get("store_id")) : null;
    const barcode = String(params.barcode);
    const found = /^\d{8,14}$/.test(barcode) && !barcode.endsWith("0000");
    const canonical = found ? canonicalRef(1004) : null; // רסק עגבניות
    const price = (store: number, agorot: number) => ({
      store: (STORE_REFS[store] ?? STORE_REFS[HOME_STORE_ID]) as StoreRef,
      item_id: store * 100 + 4,
      display_name_he: store === 101 ? "רסק עגבניות שופרסל 260 ג'" : "רסק עגבניות אסם 260 ג'",
      shelf_price: (agorot / 100).toFixed(2),
      unit_price: (agorot / 260).toFixed(2),
      uom: "100g",
      price_valid_from: PRICES_UPDATED_AT,
    });
    const body: BarcodeLookupResponse = {
      barcode,
      found,
      display_name_he: found ? "רסק עגבניות אסם 260 ג'" : null,
      canonical,
      here: found && storeId ? price(storeId, 1490) : null,
      cheapest_nearby: found ? price(102, 1150) : null,
      cheaper_substitute: found ? price(101, 890) : null,
      generated_at: new Date().toISOString(),
      disclaimer_he: "המחיר הקובע הוא בקופה.",
    };
    return HttpResponse.json(body);
  }),

  http.post(url("/optimize/swaps"), ({ request }) => {
    const storeId = Number(new URL(request.url).searchParams.get("store_id") ?? 101);
    const raw: SwapSuggestionResponse["swaps"] = [
      {
        canonical_id: 1004,
        from_item_id: storeId * 100 + 4,
        to_item_id: storeId * 100 + 44,
        to_display_name_he: "רסק עגבניות שופרסל 260 ג'",
        flex_level: "any_brand",
        saving: "4.80",
        confidence: 0.96,
        tags: [
          { key: "product_type", value: "רסק עגבניות", status: "matched" },
          { key: "pack_size", value: "260 ג'", status: "matched" },
          { key: "brand", value: "מותג פרטי", status: "differs" },
        ],
      },
      {
        canonical_id: 1001,
        from_item_id: storeId * 100 + 1,
        to_item_id: storeId * 100 + 41,
        to_display_name_he: "חלב טרי 3% יטבתה 1 ל'",
        flex_level: "any_brand",
        saving: "1.20",
        confidence: 0.93,
        tags: [
          { key: "fat_pct", value: "3%", status: "matched" },
          { key: "brand", value: "יטבתה", status: "differs" },
        ],
      },
      {
        canonical_id: 1002,
        from_item_id: storeId * 100 + 2,
        to_item_id: storeId * 100 + 42,
        to_display_name_he: "משקה סויה ללא סוכר, מותג פרטי, 1 ל'",
        flex_level: "close",
        saving: "5.00",
        confidence: 0.88,
        tags: [
          { key: "base", value: "סויה", status: "matched" },
          { key: "brand", value: "מותג פרטי", status: "differs" },
        ],
      },
    ];
    const swaps = [...raw].sort((a, b) => Number(b.saving) - Number(a.saving));
    const total = swaps.reduce((s, x) => s + Number(x.saving), 0);
    const body: SwapSuggestionResponse = {
      store_id: storeId,
      swaps,
      top_swap: swaps[0] ?? null,
      total_saving: total.toFixed(2),
      generated_at: new Date().toISOString(),
    };
    return HttpResponse.json(body);
  }),
];

/** Test hook. */
export function resetPhase2Mock(): void {
  alerts = [];
  nextAlertId = 1;
  shares = {};
  nextShareId = 1;
  nextMemberId = 1;
}
