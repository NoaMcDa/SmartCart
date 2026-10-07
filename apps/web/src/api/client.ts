/**
 * Typed API client. Types come from src/api/types.ts, generated from src/api/openapi.json by
 * `npm run gen:api` (openapi-typescript); never edit types.ts by hand.
 *
 * Use the helpers (parseList, compare, optimize, search, ...) from both server and client
 * components. They throw ApiError on non-2xx. `api` is the raw openapi-fetch client for anything
 * the helpers do not cover.
 */
import createClient, { type Client } from "openapi-fetch";
import { API_BASE_URL, API_MOCK } from "./config";
import type { components, paths } from "./types";

export type Schemas = components["schemas"];
type Opt<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type ParseListRequest = Schemas["ParseListRequest"];
export type ParseListResponse = Schemas["ParseListResponse"];
export type ParsedRow = Schemas["ParsedRow"];
export type CanonicalRef = Schemas["CanonicalRef"];
export type BasketItem = Schemas["BasketItem"];
export type CompareRequest = Schemas["CompareRequest"];
export type CompareResponse = Schemas["CompareResponse"];
export type StoreResult = Schemas["StoreResult"];
export type PricedItem = Schemas["PricedItem"];
export type AttributeTag = Schemas["AttributeTag"];
export type OptimizeRequest = Schemas["OptimizeRequest"];
export type OptimizeResponse = Schemas["OptimizeResponse"];
export type Plan = Schemas["Plan"];
export type SavingBreakdown = Schemas["SavingBreakdown"];
export type SearchResponse = Schemas["SearchResponse"];
export type SearchHit = Schemas["SearchHit"];
export type GapReportRequest = Schemas["GapReportRequest"];
export type SubstitutionFeedbackRequest = Opt<
  Schemas["SubstitutionFeedbackRequest"],
  "source" | "list_item_id" | "flex_level" | "match_confidence"
>;
export type Ack = Schemas["Ack"];
export type StoreRef = Schemas["StoreRef"];
export type FlexLevel = NonNullable<BasketItem["flex_level"]>;

// Phase 2 (history, alerts, push, shared lists, barcode, swaps)
export type PriceHistoryResponse = Schemas["PriceHistoryResponse"];
export type PricePoint = Schemas["PricePoint"];
export type PromoWindow = Schemas["PromoWindow"];
export type PriceAlert = Schemas["PriceAlert"];
export type PriceAlertInput = Opt<Schemas["PriceAlertIn"], "flex_level" | "radius_m" | "active">;
export type PushSubscriptionInput = Schemas["PushSubscriptionIn"];
export type ShareInvite = Schemas["ShareInvite"];
export type ShareRole = Schemas["ShareRequest"]["role"];
export type ListMember = Schemas["ListMember"];
export type ShoppingList = Schemas["ShoppingList"];
export type ListItemInput = Opt<
  Schemas["ListItemIn"],
  "confirmed" | "flex_level" | "quantity" | "checked"
>;
export type ShoppingListInput = Omit<Schemas["ShoppingListIn"], "items"> & {
  items: ListItemInput[];
};
export type BarcodeLookupResponse = Schemas["BarcodeLookupResponse"];
export type StorePrice = Schemas["StorePrice"];
export type SwapSuggestion = Schemas["SwapSuggestion"];
export type SwapSuggestionResponse = Schemas["SwapSuggestionResponse"];

/*
 * Request inputs. openapi-typescript marks every field that has a server-side default as required;
 * for requests those fields are optional (FastAPI fills the default), so the helpers accept these.
 */
export type BasketItemInput = Opt<BasketItem, "flex_level">;
export type LocationInput = Opt<Schemas["Location"], "radius_m">;
export type TravelInput = Partial<Schemas["TravelSettings"]>;
export type CompareInput = Opt<Omit<CompareRequest, "items" | "location">, "include_online"> & {
  items: BasketItemInput[];
  location: LocationInput;
};
export type OptimizeInput = Opt<
  Omit<OptimizeRequest, "items" | "location" | "travel">,
  "include_online" | "max_stores" | "min_split_saving" | "candidate_stores" | "solver"
> & {
  items: BasketItemInput[];
  location: LocationInput;
  travel?: TravelInput;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(`SmartCart API error ${status}`);
    this.name = "ApiError";
  }
}

/** In-process mock transport: resolves the request against the MSW handlers, no network. */
async function mockFetch(request: Request): Promise<Response> {
  const [{ getResponse }, { handlers }] = await Promise.all([
    import("msw"),
    import("@/mocks/handlers"),
  ]);
  const response = await getResponse(handlers, request);
  return (
    response ??
    new Response(
      JSON.stringify({ detail: `No mock handler for ${request.method} ${request.url}` }),
      {
        status: 501,
        headers: { "content-type": "application/json" },
      },
    )
  );
}

export const api = createClient<paths>({
  baseUrl: API_BASE_URL,
  fetch: API_MOCK ? mockFetch : (request) => globalThis.fetch(request),
});

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined || !result.response.ok) {
    throw new ApiError(result.response.status, result.error);
  }
  return result.data;
}

export async function parseList(body: ParseListRequest): Promise<ParseListResponse> {
  return unwrap(await api.POST("/parse-list", { body }));
}

export async function compare(body: CompareInput): Promise<CompareResponse> {
  return unwrap(await api.POST("/compare", { body: body as CompareRequest }));
}

export async function optimize(body: OptimizeInput): Promise<OptimizeResponse> {
  return unwrap(await api.POST("/optimize", { body: body as OptimizeRequest }));
}

export async function search(q: string, limit = 10): Promise<SearchResponse> {
  return unwrap(await api.GET("/search", { params: { query: { q, limit } } }));
}

export async function reportGap(body: GapReportRequest): Promise<Ack> {
  return unwrap(await api.POST("/feedback/gap", { body }));
}

export async function substitutionFeedback(body: SubstitutionFeedbackRequest): Promise<Ack> {
  return unwrap(
    await api.POST("/feedback/substitution", { body: { source: "substitution_card", ...body } }),
  );
}

export async function health() {
  return unwrap(await api.GET("/health"));
}

// ---------------------------------------------------------------------------------------------
// Phase 2 routes (P2-E): history, alerts, push subscriptions, shared lists, barcode, swaps.

function expectOk(result: { error?: unknown; response: Response }): void {
  if (!result.response.ok) throw new ApiError(result.response.status, result.error);
}

/** `GET /history/{id}`: `storeId` null or omitted is the chain base price series. */
export async function priceHistory(
  canonicalId: number,
  opts: { storeId?: number | null; days?: number } = {},
): Promise<PriceHistoryResponse> {
  return unwrap(
    await api.GET("/history/{canonical_id}", {
      params: {
        path: { canonical_id: canonicalId },
        query: { store_id: opts.storeId ?? undefined, days: opts.days ?? 90 },
      },
    }),
  );
}

export async function listAlerts(): Promise<PriceAlert[]> {
  return unwrap(await api.GET("/me/alerts"));
}

export async function createAlert(body: PriceAlertInput): Promise<PriceAlert> {
  return unwrap(await api.POST("/me/alerts", { body: body as Schemas["PriceAlertIn"] }));
}

export async function deleteAlert(alertId: number): Promise<void> {
  expectOk(await api.DELETE("/me/alerts/{alert_id}", { params: { path: { alert_id: alertId } } }));
}

/** `PUT /me/alerts/{id}`: edit the target, level or radius, or pause with `active: false`. */
export async function updateAlert(alertId: number, body: PriceAlertInput): Promise<PriceAlert> {
  return unwrap(
    await api.PUT("/me/alerts/{alert_id}", {
      params: { path: { alert_id: alertId } },
      body: body as Schemas["PriceAlertIn"],
    }),
  );
}

/** `DELETE /me/push-subscriptions?endpoint=`: this device stops receiving alerts. */
export async function deletePushSubscription(endpoint: string): Promise<void> {
  expectOk(await api.DELETE("/me/push-subscriptions", { params: { query: { endpoint } } }));
}

export async function addPushSubscription(body: PushSubscriptionInput): Promise<Ack> {
  return unwrap(await api.POST("/me/push-subscriptions", { body }));
}

function listBody(body: ShoppingListInput): Schemas["ShoppingListIn"] {
  return {
    ...body,
    items: body.items.map((it) => ({ checked: false, ...it })) as Schemas["ListItemIn"][],
  };
}

export async function createList(body: ShoppingListInput): Promise<ShoppingList> {
  return unwrap(await api.POST("/me/lists", { body: listBody(body) }));
}

export async function getList(listId: number): Promise<ShoppingList> {
  return unwrap(await api.GET("/me/lists/{list_id}", { params: { path: { list_id: listId } } }));
}

export async function updateList(listId: number, body: ShoppingListInput): Promise<ShoppingList> {
  return unwrap(
    await api.PUT("/me/lists/{list_id}", {
      params: { path: { list_id: listId } },
      body: listBody(body),
    }),
  );
}

export async function shareList(listId: number, role: ShareRole = "editor"): Promise<ShareInvite> {
  return unwrap(
    await api.POST("/me/lists/{list_id}/share", {
      params: { path: { list_id: listId } },
      body: { role },
    }),
  );
}

export async function listMembers(listId: number): Promise<ListMember[]> {
  return unwrap(
    await api.GET("/me/lists/{list_id}/members", { params: { path: { list_id: listId } } }),
  );
}

export async function acceptShare(token: string): Promise<ShoppingList> {
  return unwrap(await api.POST("/lists/accept/{token}", { params: { path: { token } } }));
}

export async function lookupBarcode(
  barcode: string,
  where: { lat: number; lon: number; radiusM?: number; storeId?: number | null },
): Promise<BarcodeLookupResponse> {
  return unwrap(
    await api.GET("/items/barcode/{barcode}", {
      params: {
        path: { barcode },
        query: {
          lat: where.lat,
          lon: where.lon,
          radius_m: where.radiusM,
          store_id: where.storeId ?? undefined,
        },
      },
    }),
  );
}

/** `POST /optimize/swaps?store_id=`: swaps that cheapen the list at one store, biggest first. */
export async function swapSuggestions(
  storeId: number,
  body: CompareInput,
): Promise<SwapSuggestionResponse> {
  return unwrap(
    await api.POST("/optimize/swaps", {
      params: { query: { store_id: storeId } },
      body: body as CompareRequest,
    }),
  );
}

/** `DELETE /me/lists/{id}/share/{token}`: owner only; the invite is revoked and its member loses access. */
export async function revokeShare(listId: number, token: string): Promise<void> {
  expectOk(
    await api.DELETE("/me/lists/{list_id}/share/{token}", {
      params: { path: { list_id: listId, token } },
    }),
  );
}

/**
 * `DELETE /me/lists/{list_id}/shares/{share_id}`: owner only. Revokes a pending invite, or removes
 * a member, by the `list_shares` row id that `ListMember.share_id` carries. The route is added by
 * services/api in the same round as `share_id`; until `src/api/types.ts` is regenerated with it,
 * the path is typed here. It goes through the same `api` instance, so auth and the mock apply.
 */
type RevokeSharePaths = {
  "/me/lists/{list_id}/shares/{share_id}": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get?: never;
    put?: never;
    post?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
    delete: {
      parameters: {
        query?: never;
        header?: never;
        path: { list_id: number; share_id: number };
        cookie?: never;
      };
      requestBody?: never;
      responses: { 204: { headers: { [name: string]: unknown }; content?: never } };
    };
  };
};

export async function revokeShareById(listId: number, shareId: number): Promise<void> {
  const client = api as unknown as Client<RevokeSharePaths>;
  expectOk(
    await client.DELETE("/me/lists/{list_id}/shares/{share_id}", {
      params: { path: { list_id: listId, share_id: shareId } },
    }),
  );
}

/** `DELETE /me/lists/{id}/members/{user_id}`: owner only; the member loses access at once. */
export async function removeMember(listId: number, memberId: string): Promise<void> {
  expectOk(
    await api.DELETE("/me/lists/{list_id}/members/{member_id}", {
      params: { path: { list_id: listId, member_id: memberId } },
    }),
  );
}

/** `GET /me/shared-lists`: lists other people shared with me (accepted invites). */
export async function sharedWithMe(): Promise<ShoppingList[]> {
  return unwrap(await api.GET("/me/shared-lists"));
}

/**
 * DELETE /me: removes the signed-in user's `profiles` row and the Supabase auth user (issues #30
 * and #55). Needs the bearer token (`ensureApiAuth()` installs it). Throws ApiError on failure.
 */
export async function deleteMe(): Promise<Ack> {
  return unwrap(await api.DELETE("/me"));
}

/** GET /stores/nearest: the nearest store of a chain to a point (the home store lookup). */
export async function nearestStore(chainId: string, lat: number, lon: number): Promise<StoreRef> {
  return unwrap(
    await api.GET("/stores/nearest", { params: { query: { chain_id: chainId, lat, lon } } }),
  );
}
