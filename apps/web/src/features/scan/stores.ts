"use client";

/**
 * The store the shopper is standing in: nearest store of each chain from `/stores/nearest`, the
 * shopper's home store pre-selected when it is among them, and the last choice remembered.
 */
import { useEffect, useMemo, useState } from "react";
import { nearestStore, type StoreRef } from "@/api/client";
import { useT } from "@/i18n/LocaleProvider";
import type { Locale } from "@/i18n/locales";
import { formatStoreDistance } from "@/lib/format";
import { chainLabel, storeLabel as localizedStoreName } from "@/lib/storeName";
import { scanMessages } from "@/i18n/messages/scan";
import { readJson, writeJson } from "@/state/storage";
import type { ShopperContext } from "@/state/shopper";

export const SCAN_STORE_KEY = "sc-scan-store-v1";

/** GS1 chain ids as the transparency files carry them (the first three are the mock's). */
export const SCAN_CHAIN_IDS: ReadonlyArray<string> = [
  "7290027600007", // שופרסל
  "7290058140886", // רמי לוי
  "7290103152017", // אושר עד
  "7290803800003", // יוחננוף
  "7290696200003", // ויקטורי
  "7290055700007", // יינות ביתן / קרפור
  "7290700100008", // חצי חינם
  "7290873255550", // טיב טעם
];

export type ScanStoreOption = {
  storeId: number;
  label: string;
  ref: StoreRef | null;
};

export function storeLabel(s: StoreRef): string {
  return `${s.chain_name} · ${s.store_name}`;
}

/**
 * What the store choice shows for an option: the chain and store in the UI language and the
 * distance, marked approximate when the store is only placed at its town centre. An option with no
 * store behind it ("my store") is just its label. `label` itself stays the Hebrew data (the gap
 * report sends it).
 */
export function scanOptionText(option: ScanStoreOption, locale: Locale): string {
  const ref = option.ref;
  if (!ref) return option.label;
  const name = `${chainLabel(ref.chain_name, locale)} · ${localizedStoreName(ref.store_name, locale)}`;
  return ref.distance_m != null ? `${name} · ${formatStoreDistance(ref, locale)}` : name;
}

/** Pure choice of the pre-selected store: remembered, then the home store, then the nearest. */
export function pickStore(
  options: ReadonlyArray<ScanStoreOption>,
  remembered: number | null,
  homeStoreId: number | null,
): number | null {
  const has = (id: number | null) => id !== null && options.some((o) => o.storeId === id);
  if (has(remembered)) return remembered;
  if (has(homeStoreId)) return homeStoreId;
  const nearest = [...options].sort(
    (a, b) => (a.ref?.distance_m ?? Infinity) - (b.ref?.distance_m ?? Infinity),
  )[0];
  return nearest?.storeId ?? null;
}

export function useScanStores(shopper: ShopperContext | null) {
  const t = useT(scanMessages);
  const [refs, setRefs] = useState<StoreRef[] | null>(null);
  const [chosen, setChosen] = useState<number | null>(() =>
    readJson<number | null>(SCAN_STORE_KEY, null),
  );
  const lat = shopper?.lat;
  const lon = shopper?.lon;
  const home = shopper?.homeStoreId ?? null;

  useEffect(() => {
    if (lat === undefined || lon === undefined) return;
    let cancelled = false;
    void Promise.all(SCAN_CHAIN_IDS.map((id) => nearestStore(id, lat, lon).catch(() => null))).then(
      (all) => {
        if (cancelled) return;
        const seen = new Set<number>();
        const found: StoreRef[] = [];
        for (const ref of all) {
          if (!ref || seen.has(ref.store_id)) continue;
          seen.add(ref.store_id);
          found.push(ref);
        }
        setRefs(found.sort((a, b) => (a.distance_m ?? 1e9) - (b.distance_m ?? 1e9)));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [lat, lon]);

  const options = useMemo<ScanStoreOption[]>(() => {
    const list: ScanStoreOption[] = (refs ?? []).map((ref) => ({
      storeId: ref.store_id,
      label: storeLabel(ref),
      ref,
    }));
    if (home !== null && refs !== null && !list.some((o) => o.storeId === home)) {
      list.unshift({ storeId: home, label: t("myStore"), ref: null });
    }
    return list;
  }, [refs, home, t]);

  const storeId = refs === null ? null : pickStore(options, chosen, home);
  const selected = options.find((o) => o.storeId === storeId) ?? null;

  return {
    loading: refs === null,
    options,
    storeId,
    selected,
    choose(id: number) {
      setChosen(id);
      writeJson(SCAN_STORE_KEY, id);
    },
  };
}
