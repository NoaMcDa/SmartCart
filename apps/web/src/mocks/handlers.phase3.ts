/**
 * MSW handlers for the phase 3 routes built in the unblock round: spend tracking (#70) and recipe
 * to list (#71). Written before services/api has them; the shapes are the agreed contract:
 *
 *   POST /me/spend          body SpendEntry                   -> SpendEntry (idempotent on `id`)
 *   GET  /me/spend?month=   month `YYYY-MM`                   -> { month, entries, total, budget }
 *   POST /parse-recipe      { text?, url?, servings? }        -> { title, servings, items, unresolved }
 *
 * Types are in src/api/client.ts ("until types.ts is regenerated"). The spend store is in memory
 * and shared by every caller of the handlers in one process; `resetPhase3Mock()` clears it.
 */
import { delay, http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type {
  ParseRecipeRequest,
  ParseRecipeResponse,
  ParsedRow,
  SpendEntry,
  SpendMonthResponse,
} from "@/api/client";
import { parseRow } from "./parseRow";

const url = (path: string) => `${API_BASE_URL}${path}`;
const latency = () => delay(process.env.NODE_ENV === "test" ? 0 : 250);

const spend = new Map<string, SpendEntry>();

/** Test hook: forget every spend entry the mock holds. */
export function resetPhase3Mock(): void {
  spend.clear();
}

/** Test hook: what `POST /me/spend` stored, oldest first. */
export function mockSpendEntries(): SpendEntry[] {
  return [...spend.values()];
}

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function validSpend(body: unknown): body is SpendEntry {
  if (typeof body !== "object" || body === null) return false;
  const e = body as Record<string, unknown>;
  return (
    typeof e.id === "string" &&
    e.id.length > 0 &&
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

function recipeFromText(text: string, servings: number | undefined): ParseRecipeResponse {
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
  const title = firstIsTitle && first ? first.replace(/:$/u, "") : "מתכון";
  const body = (firstIsTitle ? lines.slice(1) : lines).filter(
    (l) => !/:$/u.test(l) && !/מנות/u.test(l) && !/^(מצרכים|אופן ההכנה)/u.test(l),
  );
  const items: ParsedRow[] = [];
  const unresolved: string[] = [];
  for (const line of body) {
    const row = parseRow(line.replace(LEADING_AMOUNT, ""));
    if (row.not_found) unresolved.push(line);
    else items.push(row);
  }
  return finish(title, recipeServings, items, unresolved, servings);
}

/** What the mock "finds" at any URL: a fixed pasta recipe, so the flow can be built and tested. */
function recipeFromUrl(servings: number | undefined): ParseRecipeResponse {
  const items = ["פסטה", "2 רסק עגבניות", "עגבניות", "שמן זית כתית מעולה", "3 ביצים"].map((l) =>
    parseRow(l),
  );
  return finish("פסטה ברוטב עגבניות", 4, items, ["חופן בזיליקום", "מלח"], servings);
}

function finish(
  title: string,
  recipeServings: number,
  items: ParsedRow[],
  unresolved: string[],
  wanted: number | undefined,
): ParseRecipeResponse {
  // `servings` in the request asks the server to scale; the response says what the quantities are for.
  const target = wanted && wanted > 0 ? wanted : recipeServings;
  const factor = target / recipeServings;
  return {
    title,
    servings: target,
    items: factor === 1 ? items : items.map((r) => scaleQuantity(r, factor)),
    unresolved,
  };
}

export const phase3Handlers = [
  http.post(url("/me/spend"), async ({ request }) => {
    const body: unknown = await request.json();
    await latency();
    if (!validSpend(body)) {
      return HttpResponse.json({ detail: "invalid spend entry" }, { status: 422 });
    }
    const stored: SpendEntry = { ...body, total: Number(body.total) };
    spend.set(stored.id, stored); // same id again replaces: the POST is idempotent
    return HttpResponse.json(stored);
  }),

  http.get(url("/me/spend"), async ({ request }) => {
    const month = new URL(request.url).searchParams.get("month") ?? "";
    await latency();
    if (!MONTH.test(month)) {
      return HttpResponse.json({ detail: "month must be YYYY-MM" }, { status: 422 });
    }
    const entries = [...spend.values()]
      .filter((e) => e.date.startsWith(`${month}-`))
      .sort((a, b) => a.date.localeCompare(b.date));
    const total = Math.round(entries.reduce((acc, e) => acc + Number(e.total) * 100, 0)) / 100;
    return HttpResponse.json({ month, entries, total, budget: null } satisfies SpendMonthResponse);
  }),

  http.post(url("/parse-recipe"), async ({ request }) => {
    const body = (await request.json()) as ParseRecipeRequest;
    await latency();
    const text = body.text?.trim();
    const link = body.url?.trim();
    if (!text && !link) {
      return HttpResponse.json({ detail: "send text or url" }, { status: 422 });
    }
    if (link && !/^https?:\/\/\S+$/iu.test(link)) {
      return HttpResponse.json({ detail: "url must be http or https" }, { status: 422 });
    }
    return HttpResponse.json(
      text ? recipeFromText(text, body.servings) : recipeFromUrl(body.servings),
    );
  }),
];
