/**
 * Pure helpers for the cart handoff (issue #72). Everything here builds text or an address the
 * user's browser opens; nothing is fetched. See docs/cart-transfer.md.
 */
import type { ChainOnline, PricedItem } from "@/api/client";

export type HandoffItem = { name: string; quantity: string };

/** "2.000" -> "2", "0.500" -> "0.5". Anything that is not a plain number is kept as it came. */
export function tidyQuantity(q: string | number): string {
  const n = Number(q);
  if (!Number.isFinite(n)) return String(q);
  return String(Math.round(n * 1000) / 1000);
}

/** A line item as the handoff needs it: the display name and a tidy quantity. */
export function handoffItems(
  items: readonly Pick<PricedItem, "display_name_he" | "quantity">[],
): HandoffItem[] {
  return items.map((i) => ({ name: i.display_name_he, quantity: tidyQuantity(i.quantity) }));
}

/** `https:` addresses only, so a bad value in the database can never become a `javascript:` link. */
export function httpsUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

/** The chain's site-search address for one item, or null when the chain has no usable template. */
export function searchUrl(template: string | null | undefined, name: string): string | null {
  if (!template || !template.includes("{q}")) return null;
  return httpsUrl(template.split("{q}").join(encodeURIComponent(name)));
}

/** The chain's entry when its handoff is switched on and it has a usable online address. */
export function enabledChain(
  chains: readonly ChainOnline[] | null | undefined,
  chainId: string,
): ChainOnline | null {
  const chain = chains?.find((c) => c.chain_id === chainId);
  return chain && chain.enabled && httpsUrl(chain.online_url) ? chain : null;
}

/** One line per item, ready to paste into a note or a message. */
export function listText(items: readonly HandoffItem[], line: (item: HandoffItem) => string) {
  return items.map(line).join("\n");
}
