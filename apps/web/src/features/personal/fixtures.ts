/**
 * Test builders for the personalization documents: products from the mock catalog and trips a
 * given number of days before a fixed "now".
 */
import type { CanonicalRef } from "@/api/client";
import { canonicalRef } from "@/mocks/fixtures";
import {
  EMPTY_DOC,
  type Dismissal,
  type PersonalDoc,
  type Signal,
  type Trip,
  type TripKind,
} from "./personalDoc";

/** Noon in Israel on Thursday 22 October 2026. */
export const NOW = new Date("2026-10-22T09:00:00Z");

export const MILK = canonicalRef(1001);
export const COTTAGE = canonicalRef(1002);
export const PASTA = canonicalRef(1006);
export const TOMATOES = canonicalRef(1007);
export const EGGS = canonicalRef(1009);

export const daysAgo = (n: number, from: Date = NOW): string =>
  new Date(from.getTime() - n * 86_400_000).toISOString();

let counter = 0;
export const id = (prefix: string) => `${prefix}-${String(++counter).padStart(6, "0")}`;

export function trip(
  ago: number,
  lines: Array<[CanonicalRef | number, number?]>,
  kind: TripKind = "finished",
  from: Date = NOW,
): Trip {
  return {
    id: id("trip"),
    at: daysAgo(ago, from),
    kind,
    lines: lines.map(([ref, quantity]) => ({
      canonical_id: typeof ref === "number" ? ref : ref.canonical_id,
      quantity: quantity ?? 1,
    })),
  };
}

export function signal(
  ago: number,
  taxonomyId: string,
  kind: Signal["kind"] = "kept_brand",
  from: Date = NOW,
): Signal {
  return { id: id("sig"), at: daysAgo(ago, from), taxonomy_id: taxonomyId, kind };
}

export function dismissal(
  ago: number,
  kind: Dismissal["kind"],
  key: string,
  from: Date = NOW,
): Dismissal {
  return { kind, key, at: daysAgo(ago, from) };
}

export function doc(parts: Partial<PersonalDoc> = {}, refs: CanonicalRef[] = []): PersonalDoc {
  return { ...EMPTY_DOC, refs, ...parts };
}

/**
 * Milk every 7 days for five weeks (quantity 2, last bought 3 days ago), cottage cheese every 10
 * days (last bought 10 days ago, so its usual gap has just passed).
 */
export function regularDoc(from: Date = NOW): PersonalDoc {
  return doc(
    {
      trips: [
        trip(31, [[MILK, 2]], "finished", from),
        trip(30, [[COTTAGE]], "finished", from),
        trip(24, [[MILK, 2]], "finished", from),
        trip(20, [[COTTAGE]], "finished", from),
        trip(17, [[MILK, 2]], "finished", from),
        trip(10, [[MILK, 2], [COTTAGE]], "finished", from),
        trip(3, [[MILK, 2]], "finished", from),
      ],
    },
    [MILK, COTTAGE],
  );
}
