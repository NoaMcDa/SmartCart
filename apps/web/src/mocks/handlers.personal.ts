/**
 * MSW handlers for `/me/personal` (phase 3 personalization), following
 * `services/api/smartcart_api/routes/personal.py`:
 *
 *   GET    /me/personal   -> the stored document with `exists: true`, or the defaults with `exists: false`
 *   PUT    /me/personal   -> replaces the document (422 for a body that is not a version 1 document)
 *   DELETE /me/personal   -> 204
 *
 * One document in memory, shared by every caller of the handlers in the process; `resetPersonalMock()`
 * clears it. `mockPersonal()` is what a test reads to see what would have reached the account.
 */
import { delay, http, HttpResponse } from "msw";
import { API_BASE_URL } from "@/api/config";
import type { PersonalData, PersonalState } from "@/api/client";

const url = (path: string) => `${API_BASE_URL}${path}`;
const latency = () => delay(process.env.NODE_ENV === "test" ? 0 : 250);

let stored: PersonalData | null = null;

export function resetPersonalMock(): void {
  stored = null;
}

/** Test hook: the document the account holds, or null. */
export function mockPersonal(): PersonalData | null {
  return stored;
}

/** Test hook: puts a document on the account, as another device would have. */
export function seedPersonalMock(doc: PersonalData): void {
  stored = doc;
}

const DEFAULTS: PersonalState = {
  version: 1,
  prefs: { learn: true, value_packs: false, updated_at: null },
  refs: [],
  trips: [],
  signals: [],
  dismissals: [],
  exists: false,
};

export const personalHandlers = [
  http.get(url("/me/personal"), async () => {
    await latency();
    return HttpResponse.json(stored ? { ...stored, exists: true } : DEFAULTS);
  }),
  http.put(url("/me/personal"), async ({ request }) => {
    const body = (await request.json()) as PersonalData;
    await latency();
    if (!body || body.version !== 1) {
      return HttpResponse.json(
        { detail: [{ loc: ["body", "version"], msg: "Input should be 1", type: "literal_error" }] },
        { status: 422 },
      );
    }
    stored = body;
    return HttpResponse.json({ ...body, exists: true });
  }),
  http.delete(url("/me/personal"), async () => {
    await latency();
    stored = null;
    return new HttpResponse(null, { status: 204 });
  }),
];
