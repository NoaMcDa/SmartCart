import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { deletePersonal, getPersonal, putPersonal, type PersonalData } from "@/api/client";
import { mockPersonal, resetPersonalMock } from "./handlers.personal";
import { server } from "./node";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => resetPersonalMock());

const NOW = "2026-10-22T08:30:00Z";
const doc: PersonalData = {
  version: 1,
  prefs: { learn: true, value_packs: true, updated_at: NOW },
  refs: [],
  trips: [
    { id: "trip-000001", at: NOW, kind: "finished", lines: [{ canonical_id: 1001, quantity: 2 }] },
  ],
  signals: [],
  dismissals: [],
};

describe("/me/personal mock", () => {
  it("answers the defaults with exists false before anything is stored", async () => {
    const got = await getPersonal();
    expect(got.exists).toBe(false);
    expect(got.prefs).toEqual({ learn: true, value_packs: false, updated_at: null });
    expect(got.trips).toEqual([]);
  });

  it("stores the document and reads it back", async () => {
    const put = await putPersonal(doc);
    expect(put.exists).toBe(true);
    const got = await getPersonal();
    expect(got.exists).toBe(true);
    expect(got.trips).toHaveLength(1);
    expect(mockPersonal()).toEqual(doc);
  });

  it("refuses a document that is not version 1, like the API", async () => {
    await expect(
      putPersonal({ ...doc, version: 2 } as unknown as PersonalData),
    ).rejects.toMatchObject({
      status: 422,
    });
    expect(mockPersonal()).toBeNull();
  });

  it("deletes it", async () => {
    await putPersonal(doc);
    await deletePersonal();
    expect(mockPersonal()).toBeNull();
    expect((await getPersonal()).exists).toBe(false);
  });
});
