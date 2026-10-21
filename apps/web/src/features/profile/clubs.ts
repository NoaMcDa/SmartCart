/**
 * The clubs a person can be a member of, per chain (`GET /chains/clubs`), and how a promo's club
 * name is shown.
 *
 * The profile stores club ids (`ramilevy:club`, the API's stable ids) in `clubs`; /compare,
 * /optimize and the barcode lookup take the same ids. The list comes from the API because it is
 * data: only clubs seen in the chains' real transparency files, with the exact names the files use.
 * A chain with no club of that kind has no entry here and no club promo we could attribute.
 *
 * A promo's `club_name` is the club's name, or a rule over names the ingest wrote: `A | B` (any of),
 * `A & B` (all of), brackets. `clubRuleText` shows it in words. `אחר` is the API's "a club we cannot
 * name": shown as a plain "club promo".
 */
import { api, type ChainClubs, type ClubChoice } from "@/api/client";
import { DEFAULT_LOCALE, type Locale } from "@/i18n/locales";
import { translate } from "@/i18n/messages";
import { profileMessages } from "@/i18n/messages/profile";
import { createResourceCache } from "@/state/resource";
import { readJson, writeJson } from "@/state/storage";
import { CHAINS, chainName, type Chain } from "./chains";

export type { ChainClubs, ClubChoice };

/** The shape of a club id (`<chain slug>:<club>`); anything else in a stored profile is dropped. */
const CLUB_ID = /^[a-z0-9_]{1,40}:[a-z0-9_]{1,40}$/;

export function isClubId(value: unknown): value is string {
  return typeof value === "string" && CLUB_ID.test(value);
}

/**
 * Profiles saved before the per-chain list held chain names ("רמי לוי") in `clubs`. They do not
 * name a club, would not show in the picker and could not be removed there, so they are dropped.
 */
export function clubIdsOnly(values: ReadonlyArray<string>): string[] {
  return values.filter(isClubId);
}

// --- the list ----------------------------------------------------------------------------------

/** Not personal data: the last list the API sent, so the picker still works offline. */
const CACHE_KEY = "sc-chain-clubs-v1";

function isChainClubs(value: unknown): value is ChainClubs[] {
  return (
    Array.isArray(value) &&
    value.every(
      (row) =>
        row &&
        typeof row.chain_id === "string" &&
        Array.isArray(row.clubs) &&
        row.clubs.every(
          (c: ClubChoice) => isClubId(c?.id) && typeof c.label === "string" && c.label !== "",
        ),
    )
  );
}

const cache = createResourceCache<true, ChainClubs[]>(async () => {
  try {
    const { data, response } = await api.GET("/chains/clubs");
    if (data === undefined || !response.ok) throw new Error(`chains/clubs ${response.status}`);
    writeJson(CACHE_KEY, data);
    return data;
  } catch (error) {
    const stored = readJson<unknown>(CACHE_KEY, null);
    if (isChainClubs(stored)) return stored;
    throw error;
  }
});

const KEY = "chains-clubs";

export type ClubsResource =
  | { status: "loading" }
  | { status: "error"; reload: () => void }
  | { status: "success"; chains: ChainClubs[] };

export function useChainClubs(): ClubsResource {
  const resource = cache.useResource(KEY, true);
  if (resource.status === "success") return { status: "success", chains: resource.data };
  if (resource.status === "error") return { status: "error", reload: resource.reload };
  return { status: "loading" };
}

export function clearChainClubsCache() {
  cache.clear();
}

/** The API's club rows of a web chain, matched by the chain id the API stores. */
export function clubsOfChain(chain: Chain, rows: ReadonlyArray<ChainClubs>): ClubChoice[] {
  return rows.find((r) => r.chain_id === chain.apiId)?.clubs ?? [];
}

/** Chains that have clubs, in the order of `CHAINS`; rows of a chain the web does not list last. */
export type ChainWithClubs = { key: string; name: (locale: Locale) => string; clubs: ClubChoice[] };

export function chainsWithClubs(rows: ReadonlyArray<ChainClubs>): ChainWithClubs[] {
  const out: ChainWithClubs[] = [];
  for (const chain of CHAINS) {
    const clubs = clubsOfChain(chain, rows);
    if (clubs.length > 0)
      out.push({ key: chain.id, name: (locale) => chainName(chain, locale), clubs });
  }
  for (const row of rows) {
    if (row.clubs.length === 0 || CHAINS.some((c) => c.apiId === row.chain_id)) continue;
    out.push({ key: row.chain_id, name: () => row.chain_name, clubs: row.clubs });
  }
  return out;
}

/** The chains of `CHAINS` that no club of the list belongs to. */
export function chainsWithoutClubs(rows: ReadonlyArray<ChainClubs>): Chain[] {
  return CHAINS.filter((c) => clubsOfChain(c, rows).length === 0);
}

export function toggleClubId(clubs: ReadonlyArray<string>, id: string): string[] {
  return clubs.includes(id) ? clubs.filter((c) => c !== id) : [...clubs, id];
}

// --- showing a promo's club --------------------------------------------------------------------

/** The API's marker for a club restriction nobody can be a member of as far as it can tell. */
export const UNKNOWN_CLUB = "אחר";

export type ClubRulePart = { text: string; name: boolean };

/**
 * The club of a promo as pieces: the club names (`name: true`, Hebrew as the clubs write them) and
 * the words between them, with " | " read "or" and " & " read "and" (`(A | B) & C` is "(A או B)
 * וגם C"). Null when there is no name to show (none, or the API's unknown marker): the caller shows
 * the plain "club promo".
 */
export function clubRuleParts(
  rule: string | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): ClubRulePart[] | null {
  const text = (rule ?? "").trim();
  if (!text || text === UNKNOWN_CLUB) return null;
  const or = translate(profileMessages, locale, "clubRuleOr");
  const and = translate(profileMessages, locale, "clubRuleAnd");
  return text
    .split(/( \| | & |[()])/)
    .filter((part) => part !== "")
    .map((part) =>
      part === " | "
        ? { text: or, name: false }
        : part === " & "
          ? { text: and, name: false }
          : { text: part, name: part !== "(" && part !== ")" },
    );
}

/**
 * `clubRuleParts` as one string, for places that cannot hold markup (a chart tooltip). Names stay
 * Hebrew in both languages (they are the clubs' own names; Hebrew and Arabic are both right to
 * left, so they sit inside an Arabic sentence as they are).
 */
export function clubRuleText(rule: string | null | undefined, locale: Locale = DEFAULT_LOCALE) {
  const parts = clubRuleParts(rule, locale);
  return parts === null ? null : parts.map((p) => p.text).join("");
}
