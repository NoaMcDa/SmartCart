// @vitest-environment node
/**
 * The mock `POST /parse-image` (receipts #61, handwritten lists #68): list and receipt fixtures,
 * and the refusals the magic file names stand in for. Node environment, so `File` and `FormData`
 * are the runtime's own and the file name survives the trip.
 */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { API_BASE_URL } from "@/api/config";
import { server } from "./node";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterAll(() => server.close());

async function post(
  name: string,
  kind: string,
  options: { consent?: boolean; type?: string; bytes?: number } = {},
) {
  const form = new FormData();
  form.append("kind", kind);
  form.append(
    "image",
    new File([new Uint8Array(options.bytes ?? 100)], name, { type: options.type ?? "image/jpeg" }),
  );
  return fetch(`${API_BASE_URL}/parse-image`, {
    method: "POST",
    body: form,
    headers: options.consent === false ? {} : { "X-Image-Consent": "1" },
  });
}

describe("POST /parse-image (mock)", () => {
  it("answers 403 without the consent header, whatever the file", async () => {
    const res = await post("fine.jpg", "list", { consent: false });
    expect(res.status).toBe(403);
  });

  it("reads a handwritten list: resolved rows, one needing confirmation, unresolved lines", async () => {
    const res = await post("list.jpg", "list");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({ kind: "list", provider: "fake", receipt: null, deleted: true });
    expect(body.items).toHaveLength(3);
    expect(
      body.items.filter((r: { needs_confirmation: boolean }) => r.needs_confirmation),
    ).toHaveLength(1);
    expect(body.unresolved).toEqual(["חופן בזיליקום", "סבון כלים"]);
  });

  it("reads a receipt: the same rows plus the chain, the printed total and the lines", async () => {
    const body = await (await post("receipt.jpg", "receipt")).json();
    expect(body.kind).toBe("receipt");
    expect(body.receipt).toMatchObject({
      chain_hint: "7290027600007",
      store_hint: "שופרסל דיל מודיעין",
      total: "187.40",
    });
    expect(body.receipt.lines).toHaveLength(6);
    expect(body.items.length).toBeGreaterThan(0);
    expect(body.deleted).toBe(true);
  });

  it("returns an empty read for 'empty' names", async () => {
    const body = await (await post("empty-1.jpg", "receipt")).json();
    expect(body).toMatchObject({ items: [], unresolved: [], deleted: true });
    expect(body.receipt).toMatchObject({ lines: [] });
  });

  it.each([
    ["x-413.jpg", 413],
    ["x-415.jpg", 415],
    ["x-429.jpg", 429],
    ["x-503.jpg", 503],
    ["x-500.jpg", 500],
  ])("answers %s with %i", async (name, status) => {
    expect((await post(name, "list")).status).toBe(status);
  });

  it("enforces the real limits: 8 MB and JPEG, PNG or WebP", async () => {
    expect((await post("big.jpg", "list", { bytes: 8 * 1024 * 1024 + 1 })).status).toBe(413);
    expect((await post("a.gif", "list", { type: "image/gif" })).status).toBe(415);
    expect((await post("a.png", "list", { type: "image/png" })).status).toBe(200);
    expect((await post("a.webp", "list", { type: "image/webp" })).status).toBe(200);
  });

  it("needs the image part", async () => {
    const form = new FormData();
    form.append("kind", "list");
    const res = await fetch(`${API_BASE_URL}/parse-image`, {
      method: "POST",
      body: form,
      headers: { "X-Image-Consent": "1" },
    });
    expect(res.status).toBe(422);
  });
});
