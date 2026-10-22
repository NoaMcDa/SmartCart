/**
 * MSW request handlers for every endpoint in src/api/openapi.json. They are the contract W4b and
 * W5 build against until services/api is deployed. Enabled by NEXT_PUBLIC_API_MOCK=1 (see
 * src/api/client.ts) and usable in unit tests through src/mocks/node.ts.
 */
import { delay, http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type {
  Ack,
  CompareRequest,
  OptimizeRequest,
  ParseListRequest,
  ParseListResponse,
  SearchResponse,
  Schemas,
} from "@/api/client";
import { CATALOG, canonicalRef, compareFixture, HOME_STORE_ID, optimizeFixture } from "./fixtures";
import { applyAllowToCompare, applyAllowToOptimize } from "./allow";
import { betaHandlers } from "./handlers.beta";
import {
  applyKosherToCompare,
  applyKosherToOptimize,
  kosherActive,
  kosherHitLabel,
} from "./kosher";
import { phase2Handlers } from "./handlers.phase2";
import { personalHandlers } from "./handlers.personal";
import { phase3Handlers } from "./handlers.phase3";
import { applyPacksToCompare } from "./packs";
import { parseRow } from "./parseRow";

export { parseRow };

type Profile = Schemas["Profile"];
type ProfileUpdate = Schemas["ProfileUpdate"];
type ShoppingList = Schemas["ShoppingList"];
type ShoppingListIn = Schemas["ShoppingListIn"];
type ListItem = Schemas["ListItem"];
type ListItemIn = Schemas["ListItemIn"];
type ListItemPatch = Schemas["ListItemPatch"];

const url = (path: string) => `${API_BASE_URL}${path}`;

/** Simulated latency so loading states are visible in dev; zero under tests. */
const latency = () => delay(process.env.NODE_ENV === "test" ? 0 : 250);

export const handlers = [
  ...betaHandlers,
  ...phase2Handlers,
  ...phase3Handlers,
  ...personalHandlers,
  http.get(url("/health"), () =>
    HttpResponse.json({ status: "ok" as const, version: "0.1.0-mock" }),
  ),

  http.post(url("/parse-list"), async ({ request }) => {
    const body = (await request.json()) as ParseListRequest;
    await latency();
    const rows = body.text
      .split(/[,\n،]+/u)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => parseRow(s, (body.flex_defaults ?? {}) as Record<string, string>));
    const res: ParseListResponse = { rows, generated_at: new Date().toISOString() };
    return HttpResponse.json(res);
  }),

  http.post(url("/compare"), async ({ request }) => {
    const body = (await request.json()) as CompareRequest;
    await latency();
    if (!body.items?.length) {
      return HttpResponse.json(
        {
          detail: [
            { loc: ["body", "items"], msg: "List should have at least 1 item", type: "too_short" },
          ],
        },
        { status: 422 },
      );
    }
    return HttpResponse.json(
      applyKosherToCompare(
        applyPacksToCompare(
          applyAllowToCompare(
            compareFixture(body.home_store_id === undefined ? HOME_STORE_ID : body.home_store_id),
            body.items,
          ),
          body.items,
        ),
        body.kosher,
      ),
    );
  }),

  http.post(url("/optimize"), async ({ request }) => {
    const body = (await request.json()) as OptimizeRequest;
    await latency();
    if (!body.items?.length) {
      return HttpResponse.json(
        {
          detail: [
            { loc: ["body", "items"], msg: "List should have at least 1 item", type: "too_short" },
          ],
        },
        { status: 422 },
      );
    }
    return HttpResponse.json(
      applyKosherToOptimize(
        applyAllowToOptimize(
          optimizeFixture({
            homeStoreId: body.home_store_id === undefined ? HOME_STORE_ID : body.home_store_id,
            extraStopValue:
              body.travel?.extra_stop_value === undefined
                ? undefined
                : Number(body.travel.extra_stop_value),
            minSplitSaving:
              body.min_split_saving === undefined ? undefined : Number(body.min_split_saving),
          }),
          body.items,
        ),
        body.kosher,
      ),
    );
  }),

  http.get(url("/search"), async ({ request }) => {
    const params = new URL(request.url).searchParams;
    const q = (params.get("q") ?? "").trim();
    const limit = Number(params.get("limit") ?? 10);
    await latency();
    const hits = Object.values(CATALOG)
      .map((c) => {
        const exact = c.display_name_he.includes(q);
        const kw = c.keywords.some((k) => q.includes(k) || k.includes(q));
        const score = exact ? 0.92 : kw ? 0.78 : 0;
        return { c, score, exact };
      })
      .filter((h) => q.length > 0 && h.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(({ c, score, exact }) => ({
        canonical: canonicalRef(c.canonical_id),
        score,
        matched_by: exact ? (["trigram", "fts"] as const) : (["vector"] as const),
      }));
    // The kosher filter (docs/api.md): a label per hit; a hit nothing can be offered for goes last
    const kosher: Schemas["KosherFilter"] = {
      level: (params.get("kosher") as Schemas["KosherFilter"]["level"]) ?? null,
      passover: params.get("kosher_passover") === "true",
      only_stated: params.get("kosher_only_stated") === "true",
    };
    const chains = compareFixture(null).stores;
    const labelled = hits.map((h) => ({
      ...h,
      matched_by: [...h.matched_by],
      ...(kosherActive(kosher)
        ? {
            kosher: kosherHitLabel(
              h.canonical.canonical_id,
              chains
                .filter((s) => s.items.some((i) => i.canonical_id === h.canonical.canonical_id))
                .map((s) => s.chain_id),
              kosher,
            ),
          }
        : {}),
    }));
    const res: SearchResponse = {
      query: q,
      hits: kosherActive(kosher)
        ? [
            ...labelled.filter((h) => h.kosher?.status !== "none"),
            ...labelled.filter((h) => h.kosher?.status === "none"),
          ]
        : labelled,
    };
    return HttpResponse.json(res);
  }),

  http.post(url("/feedback/gap"), async () => {
    await latency();
    return HttpResponse.json({ ok: true, id: 1 } satisfies Ack);
  }),

  http.post(url("/feedback/substitution"), async () => {
    await latency();
    return HttpResponse.json({ ok: true, id: 1 } satisfies Ack);
  }),

  // ---- Signed-in user routes (/me/*). In memory, per mock instance; the Authorization header is
  // ignored (the real API verifies the Supabase JWT, see docs/api.md). Added by W5.

  http.get(url("/me/profile"), async () => {
    await latency();
    return HttpResponse.json(meProfile ?? defaultProfile());
  }),

  http.put(url("/me/profile"), async ({ request }) => {
    const body = (await request.json()) as ProfileUpdate;
    await latency();
    const hasLocation =
      body.neighborhood_lat !== null &&
      body.neighborhood_lat !== undefined &&
      body.neighborhood_lon !== null &&
      body.neighborhood_lon !== undefined;
    if (hasLocation && !body.consent_location) {
      return HttpResponse.json(
        { detail: "consent_location is required to store a neighborhood location" },
        { status: 422 },
      );
    }
    const round3 = (n: number | null | undefined) =>
      n === null || n === undefined ? null : Math.round(n * 1000) / 1000;
    meProfile = {
      ...defaultProfile(),
      ...body,
      cost_per_km: String(body.cost_per_km ?? "1.2"),
      extra_stop_value: String(body.extra_stop_value ?? "25"),
      neighborhood_lat: round3(body.neighborhood_lat),
      neighborhood_lon: round3(body.neighborhood_lon),
      // Like the API (#70): an omitted budget keeps the stored one, null clears it.
      monthly_budget:
        body.monthly_budget === undefined
          ? (meProfile?.monthly_budget ?? null)
          : body.monthly_budget === null
            ? null
            : Number(body.monthly_budget).toFixed(2),
      exists: true,
    };
    return HttpResponse.json(meProfile);
  }),

  http.get(url("/me/lists"), async () => {
    await latency();
    return HttpResponse.json(meLists);
  }),

  http.post(url("/me/lists"), async ({ request }) => {
    const body = (await request.json()) as ShoppingListIn;
    await latency();
    const list = toShoppingList(meNextListId++, body);
    meLists.push(list);
    return HttpResponse.json(list, { status: 201 });
  }),

  http.get(url("/me/lists/:id"), async ({ params }) => {
    await latency();
    const list = meLists.find((l) => l.id === Number(params.id));
    return list
      ? HttpResponse.json(list)
      : HttpResponse.json({ detail: "not found" }, { status: 404 });
  }),

  // Id-stable like the API: an item with the id of one of the list's items keeps its row (and its
  // version unless something changed), the others are added, the ones not named are removed.
  http.put(url("/me/lists/:id"), async ({ params, request }) => {
    const body = (await request.json()) as ShoppingListIn;
    await latency();
    const idx = meLists.findIndex((l) => l.id === Number(params.id));
    if (idx < 0) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const next = toShoppingList(Number(params.id), body, meLists[idx]);
    meLists[idx] = next;
    return HttpResponse.json(next);
  }),

  // Per-item writes (owner and editors; the mock has one signed-in user). `updated_at` is the
  // item's version: PATCH and DELETE with a stale `expected_updated_at` answer 409 with the row.
  http.post(url("/me/lists/:id/items"), async ({ params, request }) => {
    const body = (await request.json()) as ListItemIn;
    await latency();
    const list = meLists.find((l) => l.id === Number(params.id));
    if (!list) return HttpResponse.json({ detail: "list not found" }, { status: 404 });
    if (list.items.length >= 200) {
      return HttpResponse.json({ detail: "a list has at most 200 items" }, { status: 403 });
    }
    // Idempotent per (list, client_id) like the API: a repeat answers with the stored row.
    const stored = body.client_id
      ? list.items.find((i) => i.client_id === body.client_id)
      : undefined;
    if (stored) return HttpResponse.json(stored, { status: 200 });
    const sort = list.items.reduce((max, i) => Math.max(max, i.sort), -1) + 1;
    const row = itemRow(nextItemId(list), sort, body);
    list.items.push(row);
    touchList(list);
    return HttpResponse.json(row, { status: 201 });
  }),

  http.patch(url("/me/lists/:id/items/:itemId"), async ({ params, request }) => {
    const body = (await request.json()) as ListItemPatch;
    await latency();
    const found = findItem(params.id, params.itemId);
    if (!found) return HttpResponse.json({ detail: "item not found" }, { status: 404 });
    if (isStale(found, body.expected_updated_at)) return itemConflict(found);
    const changes: Partial<ListItem> = {};
    if ("canonical_id" in body) changes.canonical_id = body.canonical_id ?? null;
    if ("input_text" in body) changes.input_text = body.input_text ?? null;
    if (body.quantity != null) changes.quantity = String(body.quantity);
    if (body.flex_level != null) changes.flex_level = body.flex_level;
    if (body.confirmed != null) changes.confirmed = body.confirmed;
    if (body.checked != null) changes.checked = body.checked;
    const changed = Object.entries(changes).some(
      ([k, v]) => String(found[k as keyof ListItem]) !== String(v),
    );
    Object.assign(found, changes);
    if (changed) {
      found.updated_at = stamp();
      touchList(meLists.find((l) => l.id === Number(params.id)));
    }
    return HttpResponse.json(found);
  }),

  http.delete(url("/me/lists/:id/items/:itemId"), async ({ params, request }) => {
    await latency();
    const found = findItem(params.id, params.itemId);
    if (!found) return HttpResponse.json({ detail: "item not found" }, { status: 404 });
    const expected = new URL(request.url).searchParams.get("expected_updated_at");
    if (isStale(found, expected)) return itemConflict(found);
    const list = meLists.find((l) => l.id === Number(params.id))!;
    list.items = list.items.filter((i) => i.id !== found.id);
    touchList(list);
    return new HttpResponse(null, { status: 204 });
  }),

  http.delete(url("/me/lists/:id"), async ({ params }) => {
    await latency();
    const idx = meLists.findIndex((l) => l.id === Number(params.id));
    if (idx < 0) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    meLists.splice(idx, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];

// ---------------------------------------------------------------------------------------------
// In-memory state behind /me/*

const MOCK_USER_ID = "00000000-0000-4000-8000-000000000001";

function defaultProfile(): Profile {
  return {
    user_id: MOCK_USER_ID,
    exists: false,
    clubs: [],
    consent_location: false,
    cost_per_km: "1.2",
    diet_flags: [],
    extra_stop_value: "25",
    flex_defaults: {},
    home_store_id: null,
    kosher_level: null,
    max_stores: 2,
    neighborhood_lat: null,
    neighborhood_lon: null,
    radius_m: 5000,
    theme: "system",
    travel_mode: "car",
  };
}

let meProfile: Profile | null = null;
let meLists: ShoppingList[] = [];
let meNextListId = 1;

/** The last item id handed out per list, so a deleted item's id is never reused. */
const lastItemId = new Map<number, number>();

function nextItemId(list: Pick<ShoppingList, "id" | "items">): number {
  const last =
    lastItemId.get(list.id) ?? list.items.reduce((m, i) => Math.max(m, i.id), list.id * 1000);
  lastItemId.set(list.id, last + 1);
  return last + 1;
}

let stampSeq = 0;
/**
 * A strictly increasing `updated_at` with microseconds, like the API's. The microsecond digits are
 * a counter, so two writes in the same millisecond still have different versions to the API, while
 * a client that kept only the milliseconds (a `Date`) still matches, as it does against the API.
 */
function stamp(): string {
  stampSeq += 1;
  const ms = new Date().toISOString().slice(0, -1);
  return `${ms}${String(stampSeq % 1000).padStart(3, "0")}Z`;
}

function itemRow(id: number, sort: number, item: ListItemIn): ListItem {
  return {
    id,
    sort,
    canonical_id: item.canonical_id ?? null,
    confirmed: item.confirmed ?? true,
    flex_level: item.flex_level ?? "any_brand",
    input_text: item.input_text ?? null,
    quantity: String(item.quantity ?? "1"),
    checked: item.checked ?? false,
    client_id: item.client_id ?? null,
    updated_at: stamp(),
  };
}

/** An item was added, changed or removed: the list's own `updated_at` moves, like the API's trigger. */
function touchList(list: ShoppingList | undefined): void {
  if (list) list.updated_at = new Date().toISOString();
}

const SAME_FIELDS = [
  "canonical_id",
  "confirmed",
  "flex_level",
  "input_text",
  "quantity",
  "checked",
  "sort",
] as const;

function toShoppingList(id: number, body: ShoppingListIn, previous?: ShoppingList): ShoppingList {
  const now = new Date().toISOString();
  const draft = { id, items: previous?.items ?? [] };
  const before = new Map(draft.items.map((i) => [i.id, i]));
  const used = new Set<number>();
  const items = (body.items ?? []).map((item, i) => {
    const old = item.id != null && !used.has(item.id) ? before.get(item.id) : undefined;
    if (old) used.add(old.id);
    // PUT ignores the idempotency key: a kept item keeps its own, a new one has none.
    const row = itemRow(old?.id ?? nextItemId(draft), i, { ...item, client_id: old?.client_id });
    if (!old) return row;
    // Unchanged: the same version, as the trigger keeps it.
    const same = SAME_FIELDS.every((k) => String(old[k]) === String(row[k]));
    return same ? old : row;
  });
  return {
    id,
    name: body.name,
    is_recurring: body.is_recurring ?? false,
    items,
    created_at: previous?.created_at ?? now,
    updated_at: now,
    shared: false,
    role: "owner",
  };
}

function findItem(listId: unknown, itemId: unknown): ListItem | undefined {
  return meLists.find((l) => l.id === Number(listId))?.items.find((i) => i.id === Number(itemId));
}

/** Versions match to the millisecond, like the API's check. */
function isStale(item: ListItem, expected: string | null | undefined): boolean {
  return !!expected && Date.parse(expected) !== Date.parse(item.updated_at);
}

function itemConflict(item: ListItem) {
  return HttpResponse.json(
    { detail: "the item changed since you read it", current: item },
    { status: 409 },
  );
}

/** Test hook: forget the signed-in user's profile and lists. */
export function resetMeMock(): void {
  meProfile = null;
  meLists = [];
  meNextListId = 1;
  lastItemId.clear();
}
