/**
 * A delete or a correction made while an entry is on its way to the account (issue #70): the
 * account must end up with what the person did, not with the entry as it was when the request left.
 */
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { resetPhase3Mock } from "@/mocks/handlers.phase3";
import { server } from "@/mocks/node";
import { loadSpend, mergeServerEntries, recordSpend, removeSpendRow } from "./spendState";
import { correctSpend, pushPendingSpend } from "./sync";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  window.localStorage.clear();
  resetPhase3Mock();
});

const shop = () =>
  recordSpend({
    storeId: 101,
    storeName: "store",
    total: 371.4,
    itemCount: 9,
    plan: "single",
    now: new Date("2026-10-08T09:00:00Z"),
    pending: true,
  });

function accepted(id: number, row: ReturnType<typeof shop>) {
  return {
    id,
    date: row.date,
    store_id: row.store_id,
    store_name: row.store_name,
    total: "371.40",
    item_count: row.item_count,
    plan: row.plan,
    client_id: row.client_id,
  };
}

describe("a delete or a correction made while the entry is being sent", () => {
  it("a shop deleted during the POST is deleted on the account too, and never comes back", async () => {
    const row = shop();
    const deleted: string[] = [];
    server.use(
      http.post(`${API_BASE_URL}/me/spend`, () => {
        removeSpendRow(row.id); // the person deletes it while the request is on its way
        return HttpResponse.json(accepted(7, row), { status: 201 });
      }),
      http.delete(`${API_BASE_URL}/me/spend/:id`, ({ params }) => {
        deleted.push(String(params.id));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await pushPendingSpend();
    expect(deleted).toEqual(["7"]);
    expect(loadSpend().entries).toEqual([]);
    // Even if that delete had failed, the account's copy must not reappear on this device.
    expect(mergeServerEntries([accepted(7, row)])).toBe(0);
    expect(loadSpend().entries).toEqual([]);
  });

  it("a total corrected during the POST reaches the account with a PUT", async () => {
    const row = shop();
    const puts: Array<{ id: string; total: string }> = [];
    server.use(
      http.post(`${API_BASE_URL}/me/spend`, () => {
        void correctSpend(row.id, "400", true); // the correction lands before the response
        return HttpResponse.json(accepted(5, row), { status: 201 });
      }),
      http.put(`${API_BASE_URL}/me/spend/:id`, async ({ params, request }) => {
        const body = (await request.json()) as { total: string };
        puts.push({ id: String(params.id), total: body.total });
        return HttpResponse.json({ ...accepted(5, row), total: body.total });
      }),
    );
    await pushPendingSpend();
    expect(puts).toEqual([{ id: "5", total: "400.00" }]);
    const stored = loadSpend().entries[0]!;
    expect(stored.total).toBe(400);
    expect(stored.server_id).toBe(5);
  });
});
