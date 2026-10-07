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
  ParsedRow,
  SearchResponse,
  Schemas,
} from "@/api/client";
import { CATALOG, canonicalRef, compareFixture, HOME_STORE_ID, optimizeFixture } from "./fixtures";
import { phase2Handlers } from "./handlers.phase2";

type Profile = Schemas["Profile"];
type ProfileUpdate = Schemas["ProfileUpdate"];
type ShoppingList = Schemas["ShoppingList"];
type ShoppingListIn = Schemas["ShoppingListIn"];

const url = (path: string) => `${API_BASE_URL}${path}`;

/** Simulated latency so loading states are visible in dev; zero under tests. */
const latency = () => delay(process.env.NODE_ENV === "test" ? 0 : 250);

const HEBREW_NUMBERS: Record<string, number> = {
  אחד: 1,
  אחת: 1,
  שניים: 2,
  שתיים: 2,
  שני: 2,
  שתי: 2,
  שלוש: 3,
  שלושה: 3,
  ארבע: 4,
  ארבעה: 4,
};

/** "2 רסק עגבניות" -> { quantity: "2", name: "רסק עגבניות" }. */
function splitQuantity(raw: string): { quantity: string; name: string } {
  const text = raw.trim();
  const lead = /^(\d+(?:\.\d+)?)\s*(?:x|×)?\s+(.+)$/u.exec(text);
  if (lead?.[1] && lead[2]) return { quantity: lead[1], name: lead[2].trim() };
  const trail = /^(.+?)\s*(?:x|×)\s*(\d+(?:\.\d+)?)$/u.exec(text);
  if (trail?.[1] && trail[2]) return { quantity: trail[2], name: trail[1].trim() };
  const [first, ...rest] = text.split(/\s+/);
  if (first && HEBREW_NUMBERS[first] && rest.length)
    return { quantity: String(HEBREW_NUMBERS[first]), name: rest.join(" ") };
  return { quantity: "1", name: text };
}

export function parseRow(input: string, flexDefaults: Record<string, string> = {}): ParsedRow {
  const { quantity, name } = splitQuantity(input);
  const matches = Object.values(CATALOG).filter((c) => c.keywords.some((k) => name.includes(k)));
  // Prefer the item whose keyword is the longest match ("רסק עגבניות" over "עגבניות").
  matches.sort(
    (a, b) =>
      Math.max(...b.keywords.filter((k) => name.includes(k)).map((k) => k.length)) -
      Math.max(...a.keywords.filter((k) => name.includes(k)).map((k) => k.length)),
  );
  const best = matches[0];
  if (!best) {
    return {
      input_text: input,
      canonical: null,
      confidence: 0,
      needs_confirmation: true,
      not_found: true,
      candidates: [],
      quantity,
      flex_level: "any_brand",
      is_weighed: false,
    };
  }
  const ambiguous = matches.filter((m) => m.taxonomy_id === best.taxonomy_id);
  // "שמן זית" alone is ambiguous: ask, like the artboard's amber confirmation.
  const needsConfirmation = ambiguous.length > 1 && !/כתית|מעולה|\d/.test(name);
  const flex = flexDefaults[best.taxonomy_id];
  return {
    input_text: input,
    canonical: canonicalRef(best.canonical_id),
    confidence: needsConfirmation ? 0.62 : 0.95,
    needs_confirmation: needsConfirmation,
    not_found: false,
    candidates: needsConfirmation ? ambiguous.map((m) => canonicalRef(m.canonical_id)) : [],
    quantity,
    flex_level:
      flex === "exact" || flex === "close" || flex === "any_brand"
        ? flex
        : best.canonical_id === 1002 || best.canonical_id === 1005
          ? "exact"
          : "any_brand",
    is_weighed: Boolean(best.weighed),
  };
}

export const handlers = [
  ...phase2Handlers,
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
      compareFixture(body.home_store_id === undefined ? HOME_STORE_ID : body.home_store_id),
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
      optimizeFixture({
        homeStoreId: body.home_store_id === undefined ? HOME_STORE_ID : body.home_store_id,
        extraStopValue:
          body.travel?.extra_stop_value === undefined
            ? undefined
            : Number(body.travel.extra_stop_value),
        minSplitSaving:
          body.min_split_saving === undefined ? undefined : Number(body.min_split_saving),
      }),
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
    const res: SearchResponse = {
      query: q,
      hits: hits.map((h) => ({ ...h, matched_by: [...h.matched_by] })),
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

  http.put(url("/me/lists/:id"), async ({ params, request }) => {
    const body = (await request.json()) as ShoppingListIn;
    await latency();
    const idx = meLists.findIndex((l) => l.id === Number(params.id));
    if (idx < 0) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const next = toShoppingList(Number(params.id), body);
    meLists[idx] = next;
    return HttpResponse.json(next);
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

function toShoppingList(id: number, body: ShoppingListIn): ShoppingList {
  const now = new Date().toISOString();
  return {
    id,
    name: body.name,
    is_recurring: body.is_recurring ?? false,
    items: (body.items ?? []).map((item, i) => ({
      id: id * 1000 + i + 1,
      sort: i,
      canonical_id: item.canonical_id ?? null,
      confirmed: item.confirmed ?? true,
      flex_level: item.flex_level ?? "any_brand",
      input_text: item.input_text ?? null,
      quantity: String(item.quantity ?? "1"),
    })),
    created_at: now,
    updated_at: now,
  };
}

/** Test hook: forget the signed-in user's profile and lists. */
export function resetMeMock(): void {
  meProfile = null;
  meLists = [];
  meNextListId = 1;
}
