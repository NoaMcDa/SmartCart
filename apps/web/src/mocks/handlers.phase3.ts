/**
 * MSW handlers for the phase 3 routes of the unblock round: spend tracking (#70) and recipe to
 * list (#71). They follow services/api (`routes/spend.py`, `routes/recipe.py`):
 *
 *   POST /me/spend          SpendEntryIn (no id)                -> 201 SpendEntry (numeric `id`)
 *   GET  /me/spend?month=   `YYYY-MM`, default the current one  -> { month, entries, total, budget }
 *   POST /parse-recipe      { text?, url?, servings? }          -> { title, servings, items, unresolved }
 *
 * Money is a string with two decimals. The spend store is in memory and shared by every caller of
 * the handlers in one process; `resetPhase3Mock()` clears it. `budget` is always null here: the
 * budget travels with the profile (`monthly_budget` on `PUT /me/profile`, see handlers.ts).
 */
import { delay, http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type {
  ParseRecipeRequest,
  ParseRecipeResponse,
  ParsedRow,
  SpendEntry,
  SpendMonth,
  ChainOnline,
  ParseImageResponse,
} from "@/api/client";
import { parseRow } from "./parseRow";

const url = (path: string) => `${API_BASE_URL}${path}`;
const latency = () => delay(process.env.NODE_ENV === "test" ? 0 : 250);

const spend = new Map<number, SpendEntry>();
let nextId = 1;

/** Test hook: forget every spend entry the mock holds. */
export function resetPhase3Mock(): void {
  spend.clear();
  nextId = 1;
}

/** Test hook: what `POST /me/spend` stored, oldest first. */
export function mockSpendEntries(): SpendEntry[] {
  return [...spend.values()];
}

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

type SpendBody = {
  date: string;
  store_id: number;
  store_name: string;
  total: number | string;
  item_count: number;
  plan: "single" | "split";
};

function validSpend(body: unknown): body is SpendBody {
  if (typeof body !== "object" || body === null) return false;
  const e = body as Record<string, unknown>;
  return (
    typeof e.date === "string" &&
    DATE.test(e.date) &&
    typeof e.store_id === "number" &&
    typeof e.store_name === "string" &&
    Number.isFinite(Number(e.total)) &&
    Number(e.total) >= 0 &&
    typeof e.item_count === "number" &&
    (e.plan === "single" || e.plan === "split")
  );
}

// --- recipes ------------------------------------------------------------------------------------

/** A recipe line like "500 גרם פסטה" is priced as a pack, so the mock drops the amount and unit. */
const LEADING_AMOUNT =
  /^\s*[\d½¼¾./]+\s*(?:גרם|ג'|גר'|ק"ג|קילו|כוסות|כוס|כפות|כף|כפיות|כפית|ליטר|מ"ל|חבילות|חבילה)\s+(?:של\s+)?/u;
const BULLET = /^[\s\-–•*·]+/u;

function scaleQuantity(row: ParsedRow, factor: number): ParsedRow {
  const q = Number.parseFloat(row.quantity) * factor;
  return { ...row, quantity: String(Math.round(q * 100) / 100) };
}

function recipeFromText(text: string, servings: number | null | undefined): ParseRecipeResponse {
  const lines = text
    .split(/\n+/u)
    .map((l) => l.replace(BULLET, "").trim())
    .filter(Boolean);
  const own = /(\d+)\s*מנות/u.exec(text);
  const recipeServings = own?.[1] ? Number(own[1]) : 4;
  // Mock heuristic: the first line is the title when it has no amount and is a short phrase
  // ("פסטה ברוטב עגבניות"), not a one-word ingredient. The real parser decides on its own.
  const first = lines[0];
  const firstIsTitle =
    lines.length > 1 &&
    first !== undefined &&
    !/^\d/u.test(first) &&
    first.split(/\s+/u).length >= 3;
  const title = firstIsTitle && first ? first.replace(/:$/u, "") : null;
  const body = (firstIsTitle ? lines.slice(1) : lines).filter(
    (l) => !/:$/u.test(l) && !/מנות/u.test(l) && !/^(מצרכים|אופן ההכנה)/u.test(l),
  );
  const items: ParsedRow[] = [];
  const unresolved: string[] = [];
  for (const line of body) {
    const row = parseRow(line.replace(LEADING_AMOUNT, ""));
    // Like the real route: every item has a product, a line without one is left to the person.
    if (row.not_found) unresolved.push(line);
    else items.push({ ...row, input_text: line });
  }
  return finish(title, recipeServings, items, unresolved, servings);
}

/** What the mock "finds" at any URL: a fixed pasta recipe, so the flow can be built and tested. */
function recipeFromUrl(servings: number | null | undefined): ParseRecipeResponse {
  const items = ["פסטה", "2 רסק עגבניות", "עגבניות", "שמן זית כתית מעולה", "3 ביצים"].map((l) =>
    parseRow(l),
  );
  return finish("פסטה ברוטב עגבניות", 4, items, ["חופן בזיליקום", "מלח"], servings);
}

function finish(
  title: string | null,
  recipeServings: number,
  items: ParsedRow[],
  unresolved: string[],
  wanted: number | null | undefined,
): ParseRecipeResponse {
  // `servings` in the request asks for scaling; the response says what the quantities are for.
  const target = wanted && wanted > 0 ? wanted : recipeServings;
  const factor = target / recipeServings;
  return {
    title,
    servings: target,
    items: factor === 1 ? items : items.map((r) => scaleQuantity(r, factor)),
    unresolved,
  };
}

// --- photos (receipts #61, handwritten lists #68) -------------------------------------------------

/** The server's limit (`Body_parse_image_parse_image_post`): JPEG, PNG or WebP, 8 MB. */
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const IMAGE_MAX_BYTES = 8 * 1024 * 1024;

/** A file part of the form. Not `instanceof File`: Node and jsdom each have their own `File`. */
function isUpload(value: FormDataEntryValue | null): value is File {
  return typeof value === "object" && value !== null;
}

/**
 * Magic file names stand in for server conditions, so a test picks the case with the name of the
 * file it uploads: `…-413.jpg` too large, `…-415.jpg` unsupported type, `…-429.jpg` monthly cap,
 * `…-503.jpg` no OCR provider, `…-500.jpg` failure, `empty…` nothing read, `slow…` waits 1.5 s.
 * The real limits (a type that is not JPEG, PNG or WebP, over 8 MB) answer 415 and 413 as well.
 * A missing `X-Image-Consent: 1` header is a 403 whatever the name.
 */
function imageRefusal(
  image: FormDataEntryValue | null,
  name: string,
): { status: number; detail: string } | null {
  if (!isUpload(image)) return { status: 422, detail: "image is required" };
  if (name.includes("-413") || image.size > IMAGE_MAX_BYTES) {
    return { status: 413, detail: "image is larger than 8 MB" };
  }
  if (name.includes("-415") || (image.type !== "" && !IMAGE_TYPES.has(image.type))) {
    return { status: 415, detail: "only JPEG, PNG or WebP" };
  }
  if (name.includes("-429")) return { status: 429, detail: "the monthly image cap is reached" };
  if (name.includes("-503")) return { status: 503, detail: "no OCR provider is configured" };
  if (name.includes("-500")) return { status: 500, detail: "internal error" };
  return null;
}

/**
 * What the mock "reads": a fixed handwritten list or receipt, with one uncertain match
 * (`שמן זית`, the amber confirmation) and lines it could not match (`unresolved`).
 */
function imageResult(kind: "receipt" | "list", name: string): ParseImageResponse {
  if (name.includes("empty")) {
    return {
      kind,
      provider: "fake",
      items: [],
      unresolved: [],
      receipt:
        kind === "receipt" ? { chain_hint: null, store_hint: null, total: null, lines: [] } : null,
      deleted: true,
    };
  }
  if (kind === "list") {
    return {
      kind,
      provider: "fake",
      items: ["חלב", "2 רסק עגבניות", "שמן זית"].map((l) => parseRow(l)),
      unresolved: ["חופן בזיליקום", "סבון כלים"],
      receipt: null,
      deleted: true,
    };
  }
  return {
    kind,
    provider: "fake",
    items: ["חלב", "3 פסטה", "עגבניות", "שמן זית"].map((l) => parseRow(l)),
    unresolved: ["הנחת מועדון", "מע״מ 17%"],
    receipt: {
      chain_hint: "7290027600007",
      store_hint: "שופרסל דיל מודיעין",
      total: "187.40",
      lines: [
        { text: "חלב 3% 1 ליטר", price: "6.90", quantity: "1" },
        { text: "פסטה ספגטי 500 גרם", price: "14.70", quantity: "3" },
        { text: "עגבניות", price: "9.80", quantity: "1.2" },
        { text: "שמן זית", price: "38.90", quantity: "1" },
        { text: "הנחת מועדון", price: "-5.00", quantity: null },
        { text: "מע״מ 17%", price: null, quantity: null },
      ],
    },
    deleted: true,
  };
}

/**
 * The mock for `GET /chains/online` (#72), which follows services/api `routes/chains.py`: every chain row, `enabled` only when the chain is
 * in CART_HANDOFF_CHAINS and has an address. The addresses are placeholders on a reserved
 * `.example` host (never requested); the chain ids are the ones the mock stores use (fixtures.ts).
 * `shufersal` carries a referral so the label is visible in the demo; `victory` has an address
 * but is not enabled, `osher_ad` has no site search, and the numeric id has no address.
 */
const MOCK_SHOP = "https://chain-shop.example";
const MOCK_CHAINS_ONLINE: ChainOnline[] = [
  {
    chain_id: "rami_levy",
    chain_name: "רמי לוי",
    online_url: `${MOCK_SHOP}/rami`,
    search_url_template: `${MOCK_SHOP}/rami/search?q={q}`,
    enabled: true,
    referral: false,
  },
  {
    chain_id: "shufersal",
    chain_name: "שופרסל",
    online_url: `${MOCK_SHOP}/shufersal`,
    search_url_template: `${MOCK_SHOP}/shufersal/search?text={q}`,
    enabled: true,
    referral: true,
  },
  {
    chain_id: "osher_ad",
    chain_name: "אושר עד",
    online_url: `${MOCK_SHOP}/osherad`,
    search_url_template: null,
    enabled: true,
    referral: false,
  },
  {
    chain_id: "victory",
    chain_name: "ויקטורי",
    online_url: `${MOCK_SHOP}/victory`,
    search_url_template: `${MOCK_SHOP}/victory/search?q={q}`,
    enabled: false,
    referral: false,
  },
  {
    chain_id: "7290027600007",
    chain_name: "שופרסל",
    online_url: null,
    search_url_template: null,
    enabled: false,
    referral: false,
  },
];

export const phase3Handlers = [
  http.post(url("/parse-image"), async ({ request }) => {
    const form = await request.formData();
    const image = form.get("image");
    const name = isUpload(image) ? image.name : "";
    // "slow" keeps the progress state on screen long enough to test it.
    await (name.includes("slow") ? delay(1500) : latency());
    if (request.headers.get("X-Image-Consent") !== "1") {
      return HttpResponse.json({ detail: "receipt processing needs consent" }, { status: 403 });
    }
    const refusal = imageRefusal(image, name);
    if (refusal) return HttpResponse.json({ detail: refusal.detail }, { status: refusal.status });
    return HttpResponse.json(
      imageResult(form.get("kind") === "receipt" ? "receipt" : "list", name),
    );
  }),

  http.get(url("/chains/online"), async () => {
    await latency();
    return HttpResponse.json(MOCK_CHAINS_ONLINE);
  }),

  http.post(url("/me/spend"), async ({ request }) => {
    const body: unknown = await request.json();
    await latency();
    if (!validSpend(body)) {
      return HttpResponse.json({ detail: "invalid spend entry" }, { status: 422 });
    }
    const stored: SpendEntry = { ...body, id: nextId, total: Number(body.total).toFixed(2) };
    nextId += 1;
    spend.set(stored.id, stored);
    return HttpResponse.json(stored, { status: 201 });
  }),

  http.get(url("/me/spend"), async ({ request }) => {
    const asked = new URL(request.url).searchParams.get("month");
    const month = asked ?? new Date().toISOString().slice(0, 7);
    await latency();
    if (!MONTH.test(month)) {
      return HttpResponse.json({ detail: "month must be YYYY-MM" }, { status: 422 });
    }
    const entries = [...spend.values()]
      .filter((e) => e.date.startsWith(`${month}-`))
      .sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
    const total = Math.round(entries.reduce((acc, e) => acc + Number(e.total) * 100, 0)) / 100;
    return HttpResponse.json({
      month,
      entries,
      total: total.toFixed(2),
      budget: null,
    } satisfies SpendMonth);
  }),

  http.post(url("/parse-recipe"), async ({ request }) => {
    const body = (await request.json()) as ParseRecipeRequest;
    await latency();
    const text = body.text?.trim() || undefined;
    const link = body.url?.trim() || undefined;
    // Exactly one of the two, like the real route.
    if ((text === undefined) === (link === undefined)) {
      return HttpResponse.json({ detail: "send text or url, not both" }, { status: 422 });
    }
    if (link && !/^https?:\/\/\S+$/iu.test(link)) {
      return HttpResponse.json({ detail: "url must be http or https" }, { status: 422 });
    }
    return HttpResponse.json(
      text ? recipeFromText(text, body.servings) : recipeFromUrl(body.servings),
    );
  }),
];
